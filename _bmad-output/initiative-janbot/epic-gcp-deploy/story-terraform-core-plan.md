---
title: 'Terraform core: Artifact Registry + Cloud Run + Secret Manager + remote state'
type: 'feature'
ticket: 5
created: '2026-10-16'
status: 'draft'
baseline_revision: '2384115'
route: 'full'
route_source: 'pinned'
risk: 'high'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** E1 proved the authenticated Cloud Run spike **by hand** (gcloud). Hand-made infrastructure is not repeatable, and **the cost of deferring codification grows with every hand-made change** — E2 adds a resource (Firestore) and new deploy config, E3 flips the service public and adds CORS; codifying at the end means reconstructing several changes from memory. Terraform moves from E4 to here (E1.5); E4 splits, keeping only CI/CD + Firestore IaC.

**Approach:** codify the E1 stack in **Terraform** — Artifact Registry, Cloud Run, the **Secret Manager container**, and a least-privilege service account — with **remote state in a versioned GCS backend**, then prove it by **tearing down the hand-made spike and applying from zero**, re-verifying all 7 acceptance criteria at the new URL.

## Boundaries & Constraints

**Always:** the secret **value never enters Terraform state** — Terraform creates the secret **container** (`google_secret_manager_secret`) only; the version is added **out-of-band** (`gcloud secrets versions add`) as a runbook step, because `google_secret_manager_secret_version` with the value would place the key in **plaintext in the state file**, a **wider exposure** than Secret Manager; **remote state** in a GCS bucket with **object versioning** enabled, bootstrapped **once by hand** (Terraform cannot initialise its own backend); `.gitignore` gains `*.tfstate*`, `.terraform/`, and value-bearing `*.tfvars`, while **`.terraform.lock.hcl` is committed** (it pins provider versions — the same discipline as `uv.lock`); resources are created **fresh, never `terraform import`**; the real-stack **naming** is `janbot-api` (service) and `janbot` (Artifact Registry repo); the service stays **authenticated-only** (E1's posture — E1.5 does **not** go public); `JANBOT_PROGRAM_PATH` stays unset (baseline ships); the `/chat` contract and the AI core are unchanged.

**Never:** the secret value in state/code/committed/echoed/logged; no public (unauthenticated) access; no compiled program; no CI/CD job and no Firestore (both are **E4b**); no change to the `/chat` contract or the AI core; do not `terraform import` the hand-made spike; no `--allow-unauthenticated`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY apply | clean Terraform state, image pushed, secret version present | AR repo + Cloud Run (`janbot-api`, authenticated) + secret container + SA created; token `/health` = ok, `/chat` cited | none |
| REPLACEMENT | hand-made spike deleted, `apply` from zero | new Cloud Run URL; all 7 acceptance criteria re-pass; E1 log URL historical | none |
| ORDERING | Cloud Run apply before the image exists in AR | revision fails to start (no image) | runbook pushes the image **before** the Cloud Run apply (two-phase/`-target`) |
| DESTROY | `terraform destroy` | AR repo (and image) + secret container + service removed | fresh `apply` must **re-push the image** and **re-add the secret version** (runbook) |
| SECRET | state file after apply | contains **no** secret value (grep for the key = 0) | n/a (must not occur) |
| STATE | backend | GCS bucket reachable, **object versioning on** | `terraform init` fails fast if the bucket/versioning is missing |

</frozen-after-approval>

## Code Map

- `_bmad-output/initiative-janbot/epic-gcp-deploy/run-e1-deploy.md` — the exact hand-made resources to codify (project `janbot-deploy-2026-10`, region `europe-central2`, repo `janbot`, service `janbot-api`, secret `OPENROUTER_API_KEY`, runtime SA; config: `--no-allow-unauthenticated --min-instances=0 --max-instances=2 --concurrency=1 --memory=2Gi --timeout=60`).
- `Containerfile` (+ `.dockerignore`) — the image build the runbook uses (`podman build -f Containerfile`).
- **New** `terraform/` — `versions.tf` (required providers: `hashicorp/google` + a pinned version), `backend.tf` (GCS backend), `main.tf` (ARTIFACT REGISTRY repo, Cloud Run service, Secret **container**, least-privilege service account, IAM), `variables.tf` (`project`, `region`, `image`, `service_name`), `outputs.tf` (service URL, repo URL).
- **New** `terraform/README.md` — the runbook: backend bootstrap (once), image build+push, secret-version add, two-phase apply, replacement proof, destroy caveats.
- `.gitignore` — add `*.tfstate*`, `.terraform/`, `*.tfvars` (value-bearing). (Repo `.gitignore` exists.)
- `pyproject.toml` / `uv.lock` — unchanged; not IaC.

## Tasks & Acceptance

**Execution:**
- [ ] Bootstrap the **GCS state bucket** by hand once (create bucket in `europe-central2`, enable **object versioning**), recorded in `terraform/README.md` (Terraform cannot create its own backend).
- [ ] `terraform/backend.tf` + `versions.tf` — GCS backend (bucket/prefix) and pinned `google` provider; produce `.terraform.lock.hcl` (committed).
- [ ] `terraform/main.tf` — the **Artifact Registry repo** `janbot`, the **Cloud Run service** `janbot-api` (authenticated-only: no `allUsers` invoker binding; `min-instances=0`, `max-instances=2`, `concurrency=1`, `memory=2Gi`, `timeout=60`; `JANBOT_MODEL_MODE=production`; secret mounted), the **Secret Manager container** `OPENROUTER_API_KEY` (no version), and a **dedicated least-privilege runtime SA** (`janbot-run`) granted `roles/secretmanager.secretAccessor` — replacing E1's default compute SA.
- [ ] `terraform/variables.tf` + `outputs.tf` — parameterise project/region/image/service-name; output the service URL and repo URL.
- [ ] `.gitignore` — `*.tfstate*`, `.terraform/`, `*.tfvars`; ensure `.terraform.lock.hcl` is tracked.
- [ ] `terraform/README.md` — the **runbook**: (1) `podman build -f Containerfile` + push to `<repo>/api:<sha>`; (2) `gcloud secrets versions add OPENROUTER_API_KEY`; (3) `terraform init && terraform apply` (two-phase/`-target` so the image exists before Cloud Run); (4) the **replacement proof**; (5) the **destroy caveat** (re-push image + re-add version after a fresh apply).
- [ ] **Two-phase ordering** — the plan settles it: `apply -target=google_artifact_registry_repository.janbot` first, push the image, then the full `apply` (documented in the runbook) — the image cannot be built by Terraform.
- [ ] **Replacement proof (the point of E1.5)** — delete the hand-made spike (it is **not** in Terraform state, so this is a **`gcloud` teardown**, not `terraform destroy`; the run log names every resource: AR repo `janbot`, Cloud Run `janbot-api`, secret), then `terraform apply` from zero, re-push the image + re-add the secret version, and **re-verify all 7 acceptance criteria at the new URL**.

**Acceptance Criteria:**
- Given a clean project and pushed image, when `terraform apply` from zero, then Artifact Registry + Cloud Run (`janbot-api`, authenticated) + the secret **container** + the least-privilege SA exist and a token `GET /health` = `{"status":"ok"}` and `POST /chat` returns a cited answer.
- Given the hand-made E1 spike deleted, when `terraform apply` from zero, then all **7 acceptance criteria re-pass at the new Cloud Run URL** (the E1 log's URL is recorded as historical).
- Given `terraform state` after apply, when grepped for `OPENROUTER_API_KEY`'s value, then it appears **nowhere** (container only; version added out-of-band).
- Given the backend, then state is **remote** (GCS) with **object versioning** on, and `*.tfstate*`/`.terraform/`/`*.tfvars` are gitignored while `.terraform.lock.hcl` is committed.
- Given `terraform destroy`, then the AR repo (and image) and the secret container are removed, and the runbook's fresh-apply steps (re-push image, re-add secret version) restore the service.
- Given the deployed service, then it is **authenticated-only** (no token → 403), `JANBOT_PROGRAM_PATH` is unset, and `/chat`/health behaviour is unchanged.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Design Notes

- **Why container-not-version for the secret:** `google_secret_manager_secret_version` stores the value in the Terraform state (plaintext), which is a *wider* exposure surface than Secret Manager itself; keeping the version out-of-band (a runbook `gcloud` step) means the state can be shared/versioned safely. This mirrors why the key is never baked or committed.
- **Why versioned remote state:** the state holds resource metadata (not the secret) but is still worth versioning for rollback/audit; the lock file is committed for the same reproducibility reason as `uv.lock`.
- **Ordering trap (settled):** Terraform does not build images, and Cloud Run will not start a revision whose image is absent — so the runbook pushes the image between the `-target` repo apply and the full apply.
- **Naming (resolves the E1 deviation):** the real stack is `janbot-api` / `janbot`; the hand-made spike is **deleted**, so after E1.5 there is exactly one Terraform-managed `janbot-api` (no `janbot-spike-*` left to confuse E4b).
- **Least-privilege:** a dedicated `janbot-run` SA replaces E1's default compute SA.

## Verification

**Commands:**
- `terraform init && terraform validate && terraform plan` -- expected: clean plan from zero; no secret value in the plan.
- `grep -R "$OPENROUTER_API_KEY" terraform/ .terraform/ *.tfstate*` -- expected: no matches (the value is never in state or code).
- `gsutil versioning get gs://<state-bucket>` -- expected: `Enabled: True`.
- token probes at the new URL -- `GET /health` = `{"status":"ok"}`; in-corpus `POST /chat` = cited answer; out-of-corpus = graceful decline.
- no token -- both routes → `403`.
- `gcloud run services describe janbot-api --region europe-central2` -- env without `JANBOT_PROGRAM_PATH`; `containerConcurrency=1`; `maxScale=2`; the `janbot-run` SA.
