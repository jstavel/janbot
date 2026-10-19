terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    # The image resource: the Google provider manages only the Artifact Registry
    # *repository*, not the image. This third-party provider builds + pushes the
    # image inside `terraform apply` (owner decision, option (c)) — pinned in
    # `.terraform.lock.hcl`, the same discipline as uv.lock.
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    # Runs the plan-time dirty-build-tree guard (git status) via a data source.
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}
