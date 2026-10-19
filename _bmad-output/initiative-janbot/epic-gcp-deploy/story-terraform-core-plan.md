---
title: 'Terraform core: image + Artifact Registry + Cloud Run + Secret Manager + remote state'
type: 'feature'
ticket: 5
created: '2026-10-16'
status: 'built'
baseline_revision: 'a0b9b87'
route: 'full'
route_source: 'pinned'
risk: 'high'
review: 'Five lenses ran (adversarial, edge-case-hunter, verification-gap, structure, prose). Owner triaged 2026-10-19 into G1, G2, G5-lite, G4, G3 plus rejected/deferred items. Code, build inputs and docs fixed; apply and phase-2 evidence remain owner-run.'
review_source: ''
lenses_ran: ['adversarial', 'edge-case-hunter', 'verification-gap', 'structure', 'prose']
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** E1 proved the authenticated Cloud Run spike **by hand** (gcloud), and hand-made infrastructure is not repeatable — **the cost of deferring codification grows with every hand-made change** (E2 adds Firestore + deploy config, E3 goes public + CORS). The image itself is also part of the drift surface: if it is built by a runbook or by CI while Terraform owns only the platform, **nothing in Terraform can say which image is deployed**, and two builders reintroduce exactly the drift this project removes.

**Approach (owner decision, option (c)):** **Terraform owns the whole stack INCLUDING the container image** — build and push happen inside `terraform apply` (the `kreuzwerker/docker` provider's `docker_registry_image`), in **one dependency graph and one `apply`**, with the image referenced **by digest**. Then prove it by tearing down the hand-made spike and applying from zero, re-verifying all 7 acceptance criteria at the new URL.

## Boundaries & Constraints

**Always:** **one tool owns the image** — Terraform builds and pushes it; **E4b's CI must NOT build or push** (it only authenticates and runs `terraform apply`), or there are two builders. The image is referenced **by digest, never by tag** (`image = "<repository>/api@<sha256_digest>"`): a tag is a moving target, so Terraform would report "no changes" while a different image ran. Provider **`kreuzwerker/docker`, pinned** in `.terraform.lock.hcl` (it is the image resource; the Google provider manages only the repository) — a **third-party supply-chain dependency**, pinned like `uv.lock`. The build uses the **`Containerfile` explicitly** (`build { context = "../", dockerfile = "Containerfile", platform = "linux/amd64" }`), which also closes E1's finding that `gcloud run deploy --source` could not honour a Containerfile. **`triggers` hash ONLY the real inputs** — `src/**`, `public_profile_org/**`, and the `Containerfile` (via `filesha1`) — **never volatile inputs** (timestamps, `.git`, the whole working dir), or every apply rebuilds. **Engine prereqs (preflight):** a running engine (`systemctl --user enable --now podman.socket`; `export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock`); registry credentials reach the `kreuzwerker/docker` provider through a `registry_auth` block that carries a **path** (`config_file`, default `~/.docker/config.json`), never a token. The credential itself is written to that file out of band, as a Docker-format `auths` entry (mode 0600), inside a throwaway `DOCKER_CONFIG` that is deleted after both plan and apply. The provider resolves registry auth **only** from `registry_auth` and ignores engine logins, so no credential-bearing value enters configuration or state. Verified 2026-10-19: `terraform state pull | grep -cE 'oauth2accesstoken|ya29\\.|Bearer '` = 0. [re-worded by marker item 1] **Artifact Registry cleanup policies** on the repo: **keep the most recent 5** versions, **delete untagged older than 7 days** — with (c) every apply pushes, so unbounded growth is a silent cost; the policy is the guarantee. The **secret value never enters state** — Terraform creates the secret **container** only; the version is added out-of-band (`gcloud secrets versions add`). **Versioned GCS remote state**, bootstrapped once by hand; `.gitignore` gains `*.tfstate*`, `.terraform/`, value-bearing `*.tfvars`, while **`.terraform.lock.hcl` is committed**. **Protection flags:** `prevent_destroy` on the AR repo and the secret container, and Cloud Run `deletion_protection` — the worst case is a redeploy, not data loss. Resources are **fresh, never `terraform import`**; real-stack naming `janbot-api` / `janbot`; service stays **authenticated-only**; `JANBOT_PROGRAM_PATH` stays unset; `/chat` contract and AI core unchanged.

**Never:** the secret value in state/code/committed/echoed/logged; a hardcoded registry token in HCL or state; volatile `triggers` inputs; image referenced by a movable tag; public (unauthenticated) access; a compiled program; CI building/pushing the image (**E4b builds nothing**); Firestore (E4b); a change to the `/chat` contract or the AI core; `terraform import` of the spike; `-target` (one apply, one graph).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY apply | engine running + logged in, state bootstrapped | **one `apply`** builds+pushes the image, creates AR repo + Cloud Run (`janbot-api`, authenticated, digest) + secret container + SA; token `/health` = ok, `/chat` cited | none |
| REPLACEMENT | hand-made spike deleted, `apply` from zero | image rebuilt+re-pushed automatically; new Cloud Run URL; all 7 acceptance criteria re-pass; E1 log URL historical | none |
| TRIGGERS | edit `src/**` or `public_profile_org/**` or `Containerfile` | image rebuild + new digest | none |
| TRIGGERS-NOISE | edit a doc / touch a timestamp | **no rebuild** (deterministic `filesha1` inputs) | n/a (must not occur) |
| DIGEST | Cloud Run reference | `@sha256:…` — the plan shows the deployed image; never a bare tag | n/a |
| DESTROY | `terraform destroy` | repo + image + service + secret container removed; fresh `apply` **rebuilds** the image and only the **secret version** must be re-added | runbook: re-add version after a fresh apply |
| SECRET | state file | contains **no** secret value (grep = 0) | n/a |
| ENGINE | `apply` with no engine / not logged in | image build fails before deploy | preflight: `podman.socket` up + `podman login` |
| STATE | backend | GCS bucket reachable, **object versioning on** | `terraform init` fails fast if missing |

<renegotiated date="2026-10-19" by="owner">
  ITEM 1 — registry credentials (supersedes the "engine credentials, never a
  registry_auth block" clause in §Boundaries & Constraints).
  ATTRIBUTION: mechanically forced by provider behaviour. Accepted by owner
  2026-10-19. Recorded separately from owner-owned choices.

  OLD (verbatim, in force at baseline):
    "registry credentials via the **engine** (`gcloud auth print-access-token |
    podman login -u oauth2accesstoken --password-stdin
    europe-central2-docker.pkg.dev`) — **never a `registry_auth` block** (a token
    would land in the state file in plaintext, and it is short-lived ~1h)"

  NEW:
    "registry credentials reach the `kreuzwerker/docker` provider through a
    `registry_auth` block that carries a **path** (`config_file`, default
    `~/.docker/config.json`), never a token. The credential itself is written to
    that file out of band, as a Docker-format `auths` entry (mode 0600), inside a
    throwaway `DOCKER_CONFIG` that is deleted after both plan and apply. The
    provider resolves registry auth **only** from `registry_auth` and ignores
    engine logins, so no credential-bearing value enters configuration or state.
    Verified 2026-10-19: `terraform state pull | grep -cE
    'oauth2accesstoken|ya29\\.|Bearer '` = 0."

  WHY (two mechanically forced facts, both measured at build time):
    (a) the provider does not read engine logins — `AuthConfigs` is nil without
        a block (provider source `internal/provider/provider.go`);
    (b) `podman login --authfile` writes a non-Docker format the provider cannot
        parse, so the `auths` entry is written directly.
    The safeguard the constraint existed for — no credential in state — still
    holds, by measurement rather than assertion.
</renegotiated>
</frozen-after-approval>

## Code Map

- `_bmad-output/initiative-janbot/epic-gcp-deploy/run-e1-deploy.md` — the hand-made resources and config to codify (project `janbot-deploy-2026-10`, region `europe-central2`, repo `janbot`, service `janbot-api`, secret `OPENROUTER_API_KEY`, sizing `--min-instances=0 --max-instances=2 --concurrency=1 --memory=2Gi --timeout=60`).
- `Containerfile` + `.dockerignore` — the image build input (`dockerfile = "Containerfile"`, context `../`).
- **New** `terraform/` — `versions.tf` (required providers: `hashicorp/google` + `kreuzwerker/docker`, both pinned → `.terraform.lock.hcl`), `backend.tf` (GCS backend), `main.tf` (`google_artifact_registry_repository` **with cleanup_policies**, `docker_registry_image` (build + `triggers`), `google_secret_manager_secret` **container**, dedicated `janbot-run` SA + IAM, `google_cloud_run_v2_service` referencing `@sha256` digest), `variables.tf`, `outputs.tf` (service URL, image digest, repo URL).
- **New** `terraform/README.md` — runbook: engine prereqs, state bootstrap, registry login, secret-version add, replacement proof, destroy caveat, cleanup-policy fallback.
- `.gitignore` — `*.tfstate*`, `.terraform/`, `*.tfvars` (value-bearing); keep `.terraform.lock.hcl` tracked.
- `pyproject.toml` / `uv.lock` — unchanged; not IaC.

## Tasks & Acceptance

**Execution:**
- [ ] Bootstrap the **GCS state bucket** by hand once (create in `europe-central2`, enable **object versioning**), recorded in `terraform/README.md`.
- [ ] `terraform/versions.tf` + `backend.tf` — pin `hashicorp/google` and **`kreuzwerker/docker`**; GCS backend; produce and **commit** `.terraform.lock.hcl`.
- [ ] `terraform/main.tf` — `google_artifact_registry_repository` `janbot` with **cleanup_policies** (keep 5 newest; delete untagged > 7d) + `prevent_destroy`; **`docker_registry_image`** building `../Containerfile` (`platform = "linux/amd64"`) with the pinned `triggers` shape below; `google_secret_manager_secret` **container** + `prevent_destroy`; dedicated **`janbot-run`** SA + `roles/secretmanager.secretAccessor`; `google_cloud_run_v2_service` `janbot-api` referencing the image **`@<sha256>` digest**, `deletion_protection = true`, authenticated-only (no `allUsers`), `min=0/max=2/concurrency=1/memory=2Gi/timeout=60`, secret mounted, `JANBOT_MODEL_MODE=production`, no `JANBOT_PROGRAM_PATH`.

  **The `triggers` shape (pinned — `filesha1` takes ONE file, so each tree needs a deterministic aggregate; exclude `__pycache__`/`*.pyc`, which are volatile):**
  ```hcl
  locals {
    src_files = [for f in fileset("${path.module}/../src", "**")
                 : f if !can(regex("(^|/)__pycache__/|\\.pyc$", f))]
    src_hash  = sha1(join("", [for f in local.src_files
                 : filesha1("${path.module}/../src/${f}")]))

    corpus_files = [for f in fileset("${path.module}/../public_profile_org", "**")
                    : f if !can(regex("\\.pyc$", f))]
    corpus_hash  = sha1(join("", [for f in local.corpus_files
                    : filesha1("${path.module}/../public_profile_org/${f}")]))

    containerfile_sha = filesha1("${path.module}/../Containerfile")
  }

  resource "docker_registry_image" "janbot" {
    name = "${google_artifact_registry_repository.janbot...}/api:${var.git_sha}"
    build { context = "${path.module}/../"  dockerfile = "Containerfile"  platform = "linux/amd64" }
    triggers = {
      src           = local.src_hash
      corpus        = local.corpus_hash
      containerfile = local.containerfile_sha
    }
  }
  ```
  The image is deployed by digest: `image = "${...}/api@${docker_registry_image.janbot.sha256_digest}"`.
- [ ] `terraform/variables.tf` + `outputs.tf` — parameterise project/region/service-name; output the **image digest** and the service URL.
- [ ] `.gitignore` — `*.tfstate*`, `.terraform/`, `*.tfvars`; confirm `.terraform.lock.hcl` is tracked.
- [ ] `terraform/README.md` — the **runbook**: (1) engine prereqs (`podman.socket`, `DOCKER_HOST`) + `podman login` via a piped `gcloud auth print-access-token`; (2) state bootstrap (once); (3) `gcloud secrets versions add OPENROUTER_API_KEY`; (4) `terraform init && terraform apply` (one apply — builds, pushes, deploys); (5) the **replacement proof**; (6) the **destroy caveat + protection-lift procedure** (below); (7) the cleanup-policy fallback if the pinned provider lacks `cleanup_policies` (`gcloud artifacts repositories set-cleanup-policies` + a follow-up to move it into HCL).
- [ ] **Protection-lift procedure (the destroy caveat)** — `prevent_destroy` (AR repo, secret container) and Cloud Run `deletion_protection` **block `terraform destroy` by design**; the first destroy **errors until they are lifted deliberately**. Record the explicit sequence in `terraform/README.md`: **(i)** set the AR repo and secret-container `lifecycle { prevent_destroy = false }` (or comment the block) and Cloud Run `deletion_protection = false`; **(ii)** `terraform apply` (to persist the lift) then `terraform destroy`; **(iii)** *(optionally)* restore the flags and `apply`. A guarantee is only useful if the operator knows how to lift it consciously.
- [ ] **Replacement proof (the point of E1.5)** — delete the hand-made spike (it is **not** in state, so this is a **`gcloud` teardown**, not `terraform destroy`; the run log names every resource), then `terraform apply` from zero (the image is rebuilt and pushed automatically), re-add only the secret version, and **re-verify all 7 acceptance criteria at the new URL**.

**Acceptance Criteria:**
- Given the engine prereqs and a bootstrapped state bucket, when **one** `terraform apply`, then Artifact Registry + the **built-and-pushed image** + Cloud Run (`janbot-api`, authenticated) + the secret **container** + the `janbot-run` SA exist, and a token `GET /health` = `{"status":"ok"}` and `POST /chat` returns a cited answer.
- Given the deployed service, then its image reference is a **`@sha256` digest**, not a tag.
- Given a change to `src/**`/`public_profile_org/**`/`Containerfile`, then the image rebuilds to a new digest; given a change to any other file, then **no rebuild**.
- Given the Artifact Registry repo, then **cleanup policies** (keep 5; delete untagged > 7d) are declared (or the recorded `gcloud` fallback is applied).
- Given `terraform state` after apply, then it contains **no secret value**, and it is remote + versioned; `*.tfstate*`/`.terraform/`/`*.tfvars` are gitignored while `.terraform.lock.hcl` is committed.
- Given `terraform destroy`, then the repo (and **image**) + secret container are removed, and a fresh `apply` **rebuilds the image** with only the secret **version** re-added by hand.
- Given the hand-made spike deleted, when `terraform apply` from zero, then all **7 acceptance criteria re-pass at the new URL** (the E1 log's URL is recorded as historical).
- Given the deployed service, then it is **authenticated-only** (no token → 403), `JANBOT_PROGRAM_PATH` is unset, and `prevent_destroy`/`deletion_protection` guard the repo, the secret container and the service.

## Implementation Notes

## Plan Change Log

- 2026-10-19 — marker item 1: registry credentials via `registry_auth` (path, no token); mechanically forced.

## Review Triage Log

Triage 2026-10-19, owner-approved. Findings are grouped by fix group; the canonical fields
are recorded for the group, not repeated per finding.

### G1 — missing dependency edges (fixed)

- location: `terraform/main.tf` (`docker_registry_image.janbot`, `google_cloud_run_v2_service.janbot`)
- trigger_condition: the image name is a plain string, so the push has no edge to the repo; the service references only the secret container, so a revision can be created before `secretAccessor` propagates.
- guard_snippet: `depends_on = [google_artifact_registry_repository.janbot]` on the image; `depends_on = [google_secret_manager_secret_iam_member.run_access]` on the service.
- potential_consequence: from-zero applies race repo/IAM propagation and fail intermittently.

### G2 — build trigger must be a function of every build input (fixed)

- location: `terraform/main.tf` triggers/locals, `Containerfile`, `.dockerignore`, `.gitignore`
- trigger_condition: `pyproject.toml`, `uv.lock` and `.dockerignore` were not hashed; tree hashes omitted file names; base images were mutable tags; a dirty tree could be labelled with a clean SHA; `terraform/` and `.env` entered the build context; `*.tfvars.json` was not ignored.
- guard_snippet: add `pyproject`/`uvlock`/`dockerignore` to `triggers`; hash `${f}:${filesha1(...)}`; pin both base images by digest with ARG + OCI labels; plan-time dirty-tree precondition; exclude `terraform/` and `.env`; ignore `*.tfvars.json`.
- potential_consequence: stale dependencies, silent renames, non-reproducible rebuilds, leaked build-context files, and a digest that does not correspond to any commit.

### G5-lite — durable rollback (fixed)

- location: `terraform/main.tf` (`docker_registry_image.janbot`, cleanup policies)
- trigger_condition: `keep_remotely` was unset, replacement deleted the prior image, and only untagged images were cleaned.
- guard_snippet: `keep_remotely = true`; `lifecycle { create_before_destroy = true }`; add `delete-tagged-30d` (2592000s) after the KEEP policy; keep per-SHA tags.
- potential_consequence: rollback revisions cannot pull their image and tagged images accumulate without bound.

### G4 — secret region + registry-token hygiene (fixed; apply owner-run)

- location: `terraform/main.tf` (`google_secret_manager_secret.openrouter`, `registry_auth`), `variables.tf`, `terraform/README.md`
- trigger_condition: `replication { auto {} }` may place the key outside the EU; the preflight overwrote the operator's Docker config with a broad, short-lived token; the secret-region change is ForceNew and destroys versions.
- guard_snippet: `user_managed` replica in `var.region`; `registry_auth_file` variable; throwaway merged `DOCKER_CONFIG` at 0600 with a trap; documented lift → apply → re-add version → restore → apply → force revision sequence; named follow-up for a deployer SA.
- potential_consequence: data-residency violation, credential exposure/expiry mid-apply, and a live revision pinned to a destroyed secret version.

### G3 — documents must stop asserting what the mechanism does not do (fixed)

- location: `terraform/README.md`, `terraform/variables.tf`, plan Design Notes/Verification
- trigger_condition: the runbook claimed one apply and a changed URL, `image_tag` was called non-load-bearing, reversal was called one line, the replacement proof omitted the second apply, the gcloud teardown was not said to bypass protection, ownership was overstated, plan counts/rollback horizon were missing, and the leak check grepped local state while state is remote.
- guard_snippet: one deterministic-URL statement read from `terraform output -raw service_url`; state two applies and why; tag is ForceNew; reversal is a bounded refactor and `ignore_changes` reverses nothing; second apply; protection-is-Terraform-only; scoped ownership claim; full plan counts and `max(5 versions, 30 days)`; `terraform state pull | grep -c`.
- potential_consequence: operators trust a URL/procedure that does not exist, and verification passes without observing the thing it claims.

### Rejected / deferred (recorded so the record is honest)

- **REJECTED — “manage the secret version in Terraform”**: targets the frozen boundary “the value never enters state”. Its limitation (rotation is invisible to plan) is accepted and documented; rotation is “re-add the version + force a revision”.
- **REJECTED as a false positive — lock-file cross-platform claim**: the `zh:` hashes already cover other platforms; no change made.
- **DEFERRED to E2 — protection flags as variables**: needs a committed `terraform.tfvars` template; carried into E2 rather than invented here.

## Design Notes

- **Why Terraform owns the image (option (c)) and why it is reversible only as a bounded refactor:** one tool = one source of truth and **one `plan` that shows which image is deployed**; the deciding anti-drift argument is that E4b's CI then builds nothing (two builders would reintroduce drift). Frequency was examined and does not dominate: an image bump is a one-line plan (`image: sha256:old → sha256:new`, 0/1/0). **Reversal is a bounded refactor, not a one-liner:** replace the digest interpolation with a variable and delete `docker_registry_image`; with `keep_remotely = true` the images survive, so the exit is **safe**. `lifecycle { ignore_changes = [...] }` alone reverses nothing — the image resource keeps building, pushing and replacing.
- **Digest, not tag:** a tag is movable, so tag-based references hide a changed image behind "no changes"; the digest makes the deployed image explicit and the plan honest.
- **`triggers` footgun:** hashing the real build inputs — `src/**`, `public_profile_org/**`, `Containerfile`, `pyproject.toml`, `uv.lock`, `.dockerignore` — means rebuilds happen on real change; hashing the working dir or timestamps would rebuild on every apply. Each tree hash includes the file name, so a rename with identical content rebuilds.
- **Registry auth through a path, not a token:** the provider resolves auth only from `registry_auth`; the block carries a path, and the credential lives in a throwaway `DOCKER_CONFIG` deleted after plan and apply. No credential-bearing value enters config or state (verified: 0 matches in `terraform state pull`). See marker item 1.
- **Cleanup policy = a guarantee, not a nicety:** with every apply pushing an image, an unbounded repository is a silent cost; keep-5 + delete-untagged>7d bounds it while preserving rollback.
- **Protection flags:** `prevent_destroy` (repo, secret container) and Cloud Run `deletion_protection` make the worst case a redeploy, not data loss.
- **Container-not-version for the secret:** `google_secret_manager_secret_version` stores the value in state (plaintext); the version stays out-of-band.
- **Naming:** real stack `janbot-api` / `janbot`; the hand-made spike is deleted, so after E1.5 exactly one Terraform-managed `janbot-api` exists.
- **`triggers` concrete shape (not just prose):** `filesha1` hashes ONE file, so each tree is aggregated deterministically — `sha1(join("", [for f in fileset("<dir>", "**") : filesha1("<dir>/${f}")]))` — with `__pycache__`/`*.pyc` filtered out (they are volatile). Without the concrete aggregate, the build could hash a single file and Terraform would report **"no changes" over a stale image** — the footgun; without the filter, a recompile would trigger a spurious rebuild.
- **Protection flags need a documented lift:** `prevent_destroy` and `deletion_protection` block `terraform destroy` by design, so the runbook records the deliberate sequence (set `prevent_destroy = false` + `deletion_protection = false` → `apply` → `destroy` → optionally restore). The worst case should be a redeploy, not an accidental teardown — but the operator must know how to lift the guard consciously.

## Verification

**Commands:**
- Preflight: `systemctl --user enable --now podman.socket`; `export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock`; `gcloud auth print-access-token | podman login -u oauth2accesstoken --password-stdin europe-central2-docker.pkg.dev`. (superseded by marker item 1)
- `terraform init && terraform validate && terraform plan` -- expected: clean plan from zero; the plan shows an `image = …@sha256:…`.
- `terraform apply` -- expected: builds/pushes the image and deploys in one run.
- `gcloud run services describe janbot-api --region europe-central2 --format='value(spec.template.spec.containers[0].image)'` -- expected: `…/api@sha256:…` (a digest, not a tag).
- token probes at the new URL -- `GET /health` = `{"status":"ok"}`; in-corpus `POST /chat` = cited; out-of-corpus = graceful decline; no token → `403`.
- `grep -R "$OPENROUTER_API_KEY" terraform/ .terraform/ *.tfstate*` -- expected: no matches. (superseded by marker item 1)
- `terraform state pull | grep -c "$OPENROUTER_API_KEY"` -- expected: `0` (state is remote; the old local grep scanned nothing that holds resource values).
- `gsutil versioning get gs://<state-bucket>` -- `Enabled: True`.
- `gcloud artifacts repositories describe janbot --location europe-central2 --format='value(cleanupPolicies)'` -- expected: keep-5 + delete-untagged + delete-tagged (or the recorded fallback).

## Follow-ups

- **Owner `stavel.jan@gmail.com`:** dedicated deployer SA with `roles/artifactregistry.writer` instead of a user-scoped `gcloud auth print-access-token` for the build/push preflight.
