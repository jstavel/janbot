terraform {
  # Remote state in a GCS bucket with object versioning, bootstrapped ONCE by
  # hand (Terraform cannot initialise its own backend). See terraform/RUNBOOK.md.
  backend "gcs" {
    bucket = "janbot-tfstate-436042949490"
    prefix = "m4-e1.5"
  }
}
