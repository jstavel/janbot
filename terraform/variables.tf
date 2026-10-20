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

variable "firestore_database_name" {
  type        = string
  description = "Firestore native database id used by the guardrail counters."
  default     = "janbot"
}

variable "rate_limit" {
  type        = number
  description = "Requests allowed per client IP per rate window."
  default     = 10
}

variable "rate_window_seconds" {
  type        = number
  description = "Per-IP fixed rate window in seconds."
  default     = 600
}

variable "daily_quota" {
  type        = number
  description = "Hard global model-call quota per UTC day."
  default     = 500
}

variable "max_question_chars" {
  type        = number
  description = "Maximum accepted question length in characters."
  default     = 2000
}

variable "max_body_bytes" {
  type        = number
  description = "Maximum accepted /chat request body in bytes."
  default     = 8192
}
