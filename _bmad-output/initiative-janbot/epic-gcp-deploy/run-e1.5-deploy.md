# E1.5 deploy log — Terraform core (M4)

**Date:** 2026-10-16 · **Owner:** stavel.jan@gmail.com · **Project:** `janbot-deploy-2026-10`
· **Region:** `europe-central2`. Owner decision **option (c)**: **Terraform owns the whole
stack, including the container image** (build + push inside `apply`, `kreuzwerker/docker`).

## What exists now (all Terraform-managed)

- `terraform/` module: `versions.tf` (pinned `hashicorp/google` 6.50.0 + `kreuzwerker/docker`
  3.9.0 in `.terraform.lock.hcl`), `backend.tf` (GCS), `main.tf`, `variables.tf`,
  `outputs.tf`, `README.md` (runbook).
- **Artifact Registry** repo `janbot` (europe-central2), **cleanup policies applied**:
  `keep-5-newest` (KEEP, keepCount 5) + `delete-untagged-7d` (DELETE, untagged, olderThan 604800s).
- **Image by digest:** `europe-central2-docker.pkg.dev/janbot-deploy-2026-10/janbot/api@sha256:1eba28b84699dd96f1f48755dcb0bd7ecd6546e153550991ebc53be407b60ad8` (built + pushed by Terraform; `triggers` over `src/**` + `public_profile_org/**` + `Containerfile`).
- **Cloud Run** `janbot-api`, **authenticated-only**, SA **`janbot-run@janbot-deploy-2026-10.iam.gserviceaccount.com`** (least-privilege, replaces E1's default compute SA), `max_instance_request_concurrency=1`, `max_instance_count=2`, `min_instance_count=0`, `memory=2Gi`, `timeout=60`, secret `OPENROUTER_API_KEY:latest`, `JANBOT_MODEL_MODE=production`, **no `JANBOT_PROGRAM_PATH`**. `deletion_protection=true`. Revision `janbot-api-00001-jms`.
- **Secret container** `OPENROUTER_API_KEY` (value never in state); version 1 added out-of-band.
- **Remote state:** `gs://janbot-tfstate-436042949490` (object versioning **on**), prefix `m4-e1.5`.
- **Protection:** `prevent_destroy` on the AR repo + secret container; Cloud Run `deletion_protection`.

## Build findings (plan-vs-reality; all recorded, none blocking)

1. **Provider auth (the hard one).** The `kreuzwerker/docker` provider resolves registry auth
   **only from a `registry_auth` block** — it does not read the host Docker config on its own
   (provider source `internal/provider/provider.go`; debug showed `provider.AuthConfigs` nil).
   Neither `podman login --authfile` nor a plain `~/.docker/config.json` was picked up.
   **Fix:** a `registry_auth` block naming `config_file = "~/.docker/config.json"` (a **path**,
   no secret → nothing sensitive in config or state) + a Docker-format `auths` entry written
   from a short-lived `gcloud` token. This honours the plan's safeguard (creds never in
   Terraform config/state) via the file route rather than the engine login the plan assumed.
2. **Two applies (secret version is out-of-band).** Cloud Run references the secret version
   `latest`, which is added *after* Terraform creates the container — so the first apply
   creates the base resources and fails at Cloud Run, then the version is added and a second
   apply succeeds. This is inherent to "container managed, version out-of-band"; the runbook
   documents it.
3. **URL is deterministic — not historical.** Recreating `janbot-api` in the same
   project+region yields the **same** URL (`https://janbot-api-kafmnjtk3a-lm.a.run.app`), so
   the E1 log's URL is **not** superseded (the plan expected it to change).
4. **Scaling drift (provider 6.50.0 quirk).** The Cloud Run v2 API returns
   `manual_instance_count` (and `min_instance_count: 0`) inside `scaling`, which the schema
   cannot set, so `terraform plan` always shows `0 to add, 1 to change` for the service
   (cosmetic; `max_instance_count=2` is applied). `ignore_changes` on `template.*.scaling` did
   not suppress it. Follow-up: pin a fixed provider version.
5. **Protection-lift used once.** A failed first Cloud Run create left a tainted resource;
   `deletion_protection=true` blocked the replace, so the documented procedure was used
   (set `false` → apply → untaint → apply → set `true` → apply).

## Replacement proof (teardown → apply from zero → re-verify)

Deleted the hand-made E1 spike with `gcloud` (it was never in state): Cloud Run `janbot-api`,
AR repo `janbot` (and its image), secret `OPENROUTER_API_KEY`. Then `terraform apply` from
zero rebuilt and pushed the image (digest `…1eba28b8`) and recreated the service. Because the
secret version is out-of-band, the version was re-added between the two applies.

## The 7 acceptance criteria (re-verified on the Terraform-managed stack)

| # | Check | Result |
|---|---|---|
| 1 | token `GET /health` | **200 `{"status":"ok"}`** ✓ |
| 2 | token in-corpus `POST /chat` | **200 `answered`**, cites `['cdbazar.org']` ✓ |
| 3 | token out-of-corpus `POST /chat` | **200 `insufficient`**, `reason=personal` ✓ |
| 4 | no token | `GET /health` **403**, `POST /chat` **403** ✓ |
| 5 | `gcloud run services describe` | SA `janbot-run@…`, concurrency 1, maxScale 2, **`JANBOT_PROGRAM_PATH` absent**, image `@sha256:1eba28b8…` ✓ |
| 6 | image reference / repo | `@sha256` digest (not a tag); cleanup policies present ✓ |
| 7 | key leakage + state | key in **state 0 / bodies 0 / logs 0**; state remote + versioned ✓ |

## Boundaries honoured

Authenticated-only; `/chat` contract and AI core untouched; no compiled program
(`JANBOT_PROGRAM_PATH` unset); secret **value** never in config/state/committed/logged;
resources fresh (never `terraform import`ed).
