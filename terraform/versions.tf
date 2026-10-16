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
  }
}
