output "service_url" {
  description = "The deployed Cloud Run service URL (public since E3: GET /health and POST /chat are unauthenticated via the Terraform-owned allUsers invoker grant; browser calls allowed only from the Pages CORS origin)."
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

output "firestore_database" {
  description = "The Firestore native database holding the guardrail counters."
  value       = google_firestore_database.janbot.name
}

output "firestore_location" {
  description = "The Firestore database location."
  value       = google_firestore_database.janbot.location_id
}
