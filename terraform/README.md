# Terraform core (M4/E1.5) — runbook

Owner decision **option (c)**: **Terraform owns the whole stack, including the container
image** — build + push happen inside `terraform apply`. One graph; the image is referenced
by **digest**, never a tag. **Terraform owns every deployable resource except the state
bucket bootstrap, the secret value, and invoker grants.**

The deploy takes **two applies**. The secret version is out of band by design (its value
must never enter state), so the first apply creates the container and Cloud Run fails until
the version is added; after the secret-region change (§Secret region and rotation), the
**protection lift** is a second reason a single apply cannot stand the stack up.

Reversal is a **bounded refactor, not a one-liner**: replace the digest interpolation with a
variable and delete `docker_registry_image`. Because `keep_remotely = true`, the images
survive. `lifecycle { ignore_changes = [template[0].containers[0].image] }` alone reverses
nothing — Terraform keeps building, pushing and replacing the image.

## Preflight (the usual failure point)

You need a running engine reachable by the `kreuzwerker/docker` provider, and registry
credentials known **to the provider**.

**Finding (build, 2026-10-16):** the `kreuzwerker/docker` provider resolves registry auth
**only from a `registry_auth` block** — it does *not* read host engine logins
(verified in provider source `internal/provider/provider.go`; a debug run shows
`provider.AuthConfigs` is nil without a block). `main.tf` therefore declares a block that
carries a **path** (`config_file`, default `~/.docker/config.json`), never a token.
The credential itself is written out of band, into a throwaway `DOCKER_CONFIG` directory
that is deleted after **both** plan and apply:

```sh
systemctl --user enable --now podman.socket
export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock

export DOCKER_CONFIG="$(mktemp -d)"
trap 'rm -rf "$DOCKER_CONFIG"' EXIT

python3 - <<'PY'
import base64, json, os, subprocess
cfg = os.path.join(os.environ["DOCKER_CONFIG"], "config.json")
existing = {}
if os.path.exists(cfg):
    with open(cfg) as fh:
        existing = json.load(fh)
auths = existing.setdefault("auths", {})
tok = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
auths.setdefault("europe-central2-docker.pkg.dev", {})["auth"] = base64.b64encode(
    ("oauth2accesstoken:" + tok).encode()).decode()
with open(cfg, "w") as fh:
    json.dump(existing, fh)
os.chmod(cfg, 0o600)
PY
```

The `auths` entry is **merged** into any existing config, never clobbering other logins.
Pass the path explicitly on every plan/apply:

```sh
terraform plan  -var registry_auth_file="$DOCKER_CONFIG/config.json"
terraform apply -var image_tag=$(git rev-parse --short HEAD) \
                -var registry_auth_file="$DOCKER_CONFIG/config.json"
```

**Blast radius, stated honestly:** `gcloud auth print-access-token` produces a
**user-scoped, full-permission** token valid for about **1 hour**. While the file exists,
anyone who can read it inherits the operator's GCP access. Keep it in the throwaway
directory, mode `0600`, and let the `trap` delete it. Follow-up: a dedicated deployer SA
with `roles/artifactregistry.writer` (owner: `stavel.jan@gmail.com`) replaces the user token.

**Dirty-build-tree guard:** `terraform plan` fails when `git status --porcelain` reports
changes in `src/`, `public_profile_org/`, `Containerfile`, `pyproject.toml`, `uv.lock` or
`.dockerignore`. The image is built from the working tree, so this prevents a digest from
carrying changes that do not exist in the repository. Commit or stash those paths first.

## Backend (bootstrapped once by hand — Terraform cannot create its own backend)

```sh
gcloud storage buckets create gs://janbot-tfstate-436042949490 \
  --location=europe-central2 --uniform-bucket-level-access
gcloud storage buckets update gs://janbot-tfstate-436042949490 --versioning
```

Remote state, **object versioning on**. `.gitignore` excludes `*.tfstate*`, `.terraform/`,
value-bearing `*.tfvars`, and `*.tfvars.json`; **`.terraform.lock.hcl` is committed**
(pins provider versions).

## Deploy (two applies because the secret version is out of band)

```sh
cd terraform
terraform init
terraform apply -var image_tag=$(git rev-parse --short HEAD) \
                -var registry_auth_file="$DOCKER_CONFIG/config.json"
```

This **builds** the image from `../Containerfile`, **pushes** `…/janbot/api:<tag>`, creates
the Artifact Registry repo (with cleanup policies), the **secret container**, the
least-privilege `janbot-run` SA + its `secretAccessor`, and the Cloud Run service (by
`@sha256` digest). The build `triggers` hash `src/**`, `public_profile_org/**`,
`Containerfile`, `pyproject.toml`, `uv.lock` and `.dockerignore` (deterministic;
`__pycache__`/`*.pyc` excluded; file names are part of each tree hash, so a rename
rebuilds).

Tags stay **per-SHA** (`name = …/api:${image_tag}`, tag = short SHA): the tag carries the
provenance “which image = which commit”. Do not move to a moving tag.

**Ordering:** Cloud Run references the secret **version** `latest`, which the out-of-band
step adds *after* Terraform creates the container — so the **first** apply creates the base
resources and fails at Cloud Run (`version … was not found`); add the version, then apply
again:

```sh
printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets versions add OPENROUTER_API_KEY --data-file=-
terraform apply -var image_tag=$(git rev-parse --short HEAD) \
                -var registry_auth_file="$DOCKER_CONFIG/config.json"
```

## Secret region and rotation (the protection lift)

`replication` is **ForceNew**. Moving the secret from `auto` to a user-managed replica inside
`europe-central2` **destroys and recreates the secret**, and its versions are lost. Cloud Run
resolves `version = "latest"` at revision-creation time and **pins that version number**, so
an existing revision keeps pointing at a version that no longer exists.

Sequence — owner-run, because the blast radius is a destroyed secret version:

1. set `prevent_destroy = false` on `google_secret_manager_secret.openrouter`;
2. `terraform apply` (recreates the secret; Cloud Run may still fail until the version exists);
3. re-add the version out of band:
   `printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets versions add OPENROUTER_API_KEY --data-file=-`;
4. restore `prevent_destroy = true`;
5. `terraform apply`;
6. **force a new revision** (the version is out of band by design, so Terraform sees no diff
   and will not create one on its own):

```sh
gcloud run services update janbot-api --region europe-central2 \
  --update-secrets=OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest
```

**Secret rotation = re-add the version + force a revision.**

## Known issues (build, 2026-10-16)

- **Scaling drift (google provider 6.50.0):** the Cloud Run v2 API returns
  `manual_instance_count` (and `min_instance_count: 0`) inside `scaling`, which the schema
  cannot set, so `terraform plan` always reports `0 to add, 1 to change, 0 to destroy` for the
  service even though nothing real changes. `max_instance_count = 2` is applied; the phantom
  change is cosmetic. Follow-up: upgrade the pinned provider once a release stops returning
  these fields, or accept the plan noise.
- **URL is deterministic:** recreating `janbot-api` in the same project+region yields the
  **same** URL. Read it from `terraform output -raw service_url`; do not keep a second copy
  in prose.
- A brand-new secret version can take a few seconds to resolve for Cloud Run; retrying the
  apply succeeds.

## Rollback horizon

**Rollback is possible to any revision whose image is among the 5 newest versions or younger
than 30 days (effective horizon = max(5 versions, 30 days)).**

The repository declares three cleanup policies: `keep-5-newest` (KEEP, 5 most recent
versions), `delete-untagged-7d` (DELETE untagged older than 604800s) and
`delete-tagged-30d` (DELETE tagged older than 2592000s). KEEP takes precedence, so the floor
is 5 versions.

## Base-image bump procedure

The `Containerfile` pins both base images by digest. A digest pin is only safe with a bump
procedure; otherwise it becomes staleness with extra steps:

1. resolve the new digests:
   `skopeo inspect --format '{{.Digest}}' docker://docker.io/library/python:3.12-slim`
   and `skopeo inspect --format '{{.Digest}}' docker://ghcr.io/astral-sh/uv:latest`;
2. update both `ARG` defaults and the `org.opencontainers.image.base*` labels in the
   `Containerfile`, in one commit;
3. `terraform plan` — `triggers.containerfile` changes, so the image is replaced; apply.

## Destroy caveat + protection-lift procedure

`prevent_destroy` (Artifact Registry repo, secret container) and Cloud Run
`deletion_protection` **block `terraform destroy` by design** — the first destroy fails until
they are lifted deliberately:

1. set `prevent_destroy = false` on the repo + secret container and
   `deletion_protection = false` on the Cloud Run service;
2. `terraform apply` (persist the lift), then `terraform destroy`;
3. *(optional)* restore the flags and `apply`.

## Cleanup policy fallback

If the pinned provider lacks `cleanup_policies`, apply them out-of-band and move them into
HCL later:

```sh
gcloud artifacts repositories set-cleanup-policies janbot --location=europe-central2 \
  --policy=keep-5.json
```

## Replacement proof

The hand-made E1 spike is **not** in Terraform state, so `terraform destroy` cannot remove
it — delete it with `gcloud`, then `apply` from zero. **This bypasses
`prevent_destroy`/`deletion_protection`: Terraform's protection is Terraform-only.** The
teardown deletes the AR repository and the secret outright.

```sh
gcloud run services delete janbot-api --region=europe-central2 --quiet
gcloud artifacts repositories delete janbot --location=europe-central2 --quiet
gcloud secrets delete OPENROUTER_API_KEY --quiet
terraform apply -var image_tag=$(git rev-parse --short HEAD) \
                -var registry_auth_file="$DOCKER_CONFIG/config.json"
printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets versions add OPENROUTER_API_KEY --data-file=-
terraform apply -var image_tag=$(git rev-parse --short HEAD) \
                -var registry_auth_file="$DOCKER_CONFIG/config.json"
```

Then re-verify all 7 acceptance criteria at the URL from
`terraform output -raw service_url`. The URL is deterministic, so it may equal the E1 URL;
read it, do not assume it changed.

## Named secrets / config

- Service `janbot-api`, region `europe-central2`, **authenticated-only** (no `allUsers`
  binding). To let someone invoke the service for a demo later: `gcloud run services
  add-iam-policy-binding janbot-api --region=europe-central2 --member=… --role=roles/run.invoker`.
- Env: `JANBOT_MODEL_MODE=production`, `OPENROUTER_API_KEY` from Secret Manager.
  `JANBOT_PROGRAM_PATH` stays unset (the image runs the baseline program).
