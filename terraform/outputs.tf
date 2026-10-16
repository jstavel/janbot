output "service_url" {
  description = "The deployed Cloud Run service URL (authenticated-only)."
  value       = google_cloud_run_v2_service.janbot.uri
}

output "image_digest" {
  description = "The pushed image's sha256 digest (the deployed reference)."
  value       = docker_registry_image.janbot.sha256_digest
}

output "repo_url" {
  description = "The Artifact Registry repository URL."
  value       = local.repo_url
}
