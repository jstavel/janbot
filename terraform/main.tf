provider "google" {
  project = var.project
  region  = var.region
}

provider "docker" {
  # The provider resolves registry auth ONLY from `registry_auth` blocks (it never
  # reads the host Docker config on its own). This block contains NO secret — just
  # the path to the client-side config file — so the token stays out of Terraform
  # config and state. The credential itself is written there from a short-lived
  # gcloud token (see terraform/README.md; renegotiated marker item 1).
  registry_auth {
    address     = "${var.region}-docker.pkg.dev"
    config_file = var.registry_auth_file
  }
}

# The docker provider talks to the local engine over DOCKER_HOST (see README preflight).

locals {
  repo_url         = "${var.region}-docker.pkg.dev/${var.project}/${var.repo_name}"
  image_ref_by_tag = "${local.repo_url}/api:${var.image_tag}"

  # Deterministic build triggers: filesha1 takes ONE file, so each tree is
  # aggregated WITH ITS FILE NAME; __pycache__/*.pyc are excluded (volatile). The
  # file name is part of the hash so a pure rename (identical content) still
  # rebuilds; anything volatile here would rebuild on EVERY apply.
  src_files = [
    for f in fileset("${path.module}/../src", "**")
    : f if !can(regex("(^|/)__pycache__/|\\.pyc$", f))
  ]
  src_hash = sha1(join("", [
    for f in local.src_files : "${f}:${filesha1("${path.module}/../src/${f}")}"
  ]))

  corpus_files = [
    for f in fileset("${path.module}/../public_profile_org", "**")
    : f if !can(regex("\\.pyc$", f))
  ]
  corpus_hash = sha1(join("", [
    for f in local.corpus_files : "${f}:${filesha1("${path.module}/../public_profile_org/${f}")}"
  ]))

  containerfile_sha = filesha1("${path.module}/../Containerfile")
}

# --- Dirty-build-tree guard: enforced at plan time, not by discipline ---
# The image is built from the working tree, not from a commit. Refuse to plan when
# any build input has uncommitted changes, so the digest can never carry changes
# that do not exist in the repository.
data "external" "build_inputs_status" {
  program = [
    "bash", "-c",
    "git -C \"$1\" status --porcelain -- src public_profile_org Containerfile pyproject.toml uv.lock .dockerignore | python3 -c 'import sys,json; print(json.dumps({\"changes\": sys.stdin.read()}))'",
    "bash",
    abspath("${path.module}/.."),
  ]
}

resource "terraform_data" "clean_build_tree" {
  input = data.external.build_inputs_status.result.changes

  lifecycle {
    precondition {
      condition     = data.external.build_inputs_status.result.changes == ""
      error_message = "Build inputs have uncommitted changes. Commit or stash them before terraform plan/apply. Dirty paths (git status --porcelain): ${data.external.build_inputs_status.result.changes}"
    }
  }
}

# --- Artifact Registry repository (cleanup: keep 5; delete untagged > 7d; delete tagged > 30d) ---
resource "google_artifact_registry_repository" "janbot" {
  location      = var.region
  repository_id = var.repo_name
  format        = "DOCKER"
  description   = "JanBot container images (M4). Cleanup: keep 5 newest; delete untagged > 7d; delete tagged > 30d."

  cleanup_policies {
    id     = "keep-5-newest"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }

  cleanup_policies {
    id     = "delete-untagged-7d"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s"
    }
  }

  cleanup_policies {
    id     = "delete-tagged-30d"
    action = "DELETE"
    condition {
      tag_state  = "TAGGED"
      older_than = "2592000s"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

# --- The image: built and pushed by Terraform (option (c)) ---
resource "docker_registry_image" "janbot" {
  name          = local.image_ref_by_tag
  keep_remotely = true

  # The repository must exist before the push; the name is a plain string, so
  # without this edge a from-zero apply can race repo creation.
  depends_on = [google_artifact_registry_repository.janbot]

  build {
    context    = "${path.module}/../"
    dockerfile = "Containerfile"
    platform   = "linux/amd64"
  }

  triggers = {
    src           = local.src_hash
    corpus        = local.corpus_hash
    containerfile = local.containerfile_sha
    pyproject     = filesha1("${path.module}/../pyproject.toml")
    uvlock        = filesha1("${path.module}/../uv.lock")
    dockerignore  = filesha1("${path.module}/../.dockerignore")
  }

  lifecycle {
    # `triggers` force replacement; keep the old image until the new one exists.
    create_before_destroy = true
  }
}

# --- Secret container only; the VALUE is added out-of-band (never in state) ---
resource "google_secret_manager_secret" "openrouter" {
  secret_id = "OPENROUTER_API_KEY"

  # User-managed replica inside the declared region; `auto` could replicate the
  # key outside the EU and contradict the deployment's own region claim.
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

# --- Least-privilege runtime service account ---
resource "google_service_account" "run" {
  account_id   = var.runtime_sa_id
  display_name = "JanBot Cloud Run runtime"
}

resource "google_secret_manager_secret_iam_member" "run_access" {
  secret_id = google_secret_manager_secret.openrouter.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.run.email}"
}

# --- Cloud Run service (authenticated-only; no allUsers binding) ---
resource "google_cloud_run_v2_service" "janbot" {
  name                = var.service_name
  location            = var.region
  deletion_protection = true

  # The revision reads the secret; wait for the accessor grant to propagate.
  depends_on = [google_secret_manager_secret_iam_member.run_access]

  template {
    service_account = google_service_account.run.email
    timeout         = "60s"
    # Low concurrency: the DSPy program is per-instance shared state.
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      # Referenced BY DIGEST, never by a movable tag.
      image = "${local.repo_url}/api@${docker_registry_image.janbot.sha256_digest}"

      ports {
        container_port = 8080
      }

      env {
        name  = "JANBOT_MODEL_MODE"
        value = "production"
      }

      env {
        name = "OPENROUTER_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.openrouter.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }
    }
  }

  # No google_cloud_run_v2_service_iam_member for allUsers -> authenticated-only.
}
