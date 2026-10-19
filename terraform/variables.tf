variable "project" {
  type        = string
  description = "GCP project id (personal project)."
  default     = "janbot-deploy-2026-10"
}

variable "region" {
  type        = string
  description = "GCP region (ADR-007: europe-central2)."
  default     = "europe-central2"
}

variable "service_name" {
  type        = string
  description = "Cloud Run service name (real stack)."
  default     = "janbot-api"
}

variable "repo_name" {
  type        = string
  description = "Artifact Registry repository id."
  default     = "janbot"
}

variable "runtime_sa_id" {
  type        = string
  description = "Account id of the least-privilege Cloud Run runtime service account."
  default     = "janbot-run"
}

variable "image_tag" {
  type        = string
  description = "Tag to build/push the image under (e.g. the git sha). The tag IS load-bearing: it is the resource name and is ForceNew, so changing it replaces the resource. The deployed image is still referenced by DIGEST."
  default     = "dev"
}

variable "registry_auth_file" {
  type        = string
  description = "Path to the Docker-format auth config the docker provider reads (a PATH, never a token)."
  default     = "~/.docker/config.json"
}
