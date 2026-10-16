# E1 deploy log — the authenticated Cloud Run spike (M4)

**Date:** 2026-10-16 · **Owner:** stavel.jan@gmail.com (personal account) · **Project:**
`janbot-deploy-2026-10` (number `436042949490`) · **Billing:** `01F9B3-809CD7-82262E`,
billingEnabled true · **Region:** `europe-central2`. This entry is **authenticated-only**
(`--no-allow-unauthenticated`); the service is **not public**. No Terraform (E4 owns IaC).

## Part A — the container (local)

- Files committed with this log: `Containerfile` + `.dockerignore` (repo root).
  Build (filename explicit — nothing auto-detects a missing Dockerfile):
  `podman build -f Containerfile -t janbot:local .`
- `python -m janbot.ingest` at build printed **291** chunks (the reference index size); the
  **79.3 MB** ONNX `all-MiniLM-L6-v2` was downloaded into the image. **Image size: 1.62 GB.**
- Local cold start (measured): container start → `/health` ready **2.76 s**; → first served
  `/chat` **18.4 s** (ONNX model load + Chroma open + LM). Warm `/chat` ≈ 8 s (LM latency).

## Containerfile honour check (E1 acceptance-relevant finding)

**Finding — the CLI does NOT honour a `Containerfile` for `--source`.** `gcloud run deploy`
has **no `--dockerfile` flag**; its `--source` help says it builds with "a Dockerfile [that]
is present in the source code directory, otherwise … Google Cloud buildpacks" — i.e. it only
ever looks for a file literally named `Dockerfile`. Therefore `--source` cannot build our
`Containerfile`.
**Path used (the prescribed fallback):** build locally with podman, push, deploy by image
reference. `gcloud run deploy --image=<ref>`. (A Cloud Build config naming `Containerfile`
would also work; the local-build fallback was chosen as the simpler, already-proven path.)

## Registry, image, secret

- Artifact Registry repo: **`janbot`** (docker, `europe-central2`).
  `gcloud artifacts repositories create janbot --repository-format=docker --location=europe-central2`
- Image (tagged with the git sha): **`europe-central2-docker.pkg.dev/janbot-deploy-2026-10/janbot/api:7725a4b`**
  `gcloud auth configure-docker europe-central2-docker.pkg.dev`
  `podman tag janbot:local <ref>` ; `podman push <ref>`
- Secret: **`OPENROUTER_API_KEY`** (Secret Manager, version **1**), value piped from the
  environment (`printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets create … --data-file=-`) —
  never echoed, never committed, never baked. Runtime SA
  `436042949490-compute@developer.gserviceaccount.com` granted
  `roles/secretmanager.secretAccessor`.
- Extra API enabled for the budget: `billingbudgets.googleapis.com` (not in the precondition
  list; needed by `gcloud billing budgets`).

## Deploy

```
gcloud run deploy janbot-api --region=europe-central2 \
  --image=europe-central2-docker.pkg.dev/janbot-deploy-2026-10/janbot/api:7725a4b \
  --no-allow-unauthenticated --min-instances=0 --max-instances=2 \
  --concurrency=1 --memory=2Gi --cpu=1 --timeout=60 \
  --set-secrets=OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest \
  --set-env-vars=JANBOT_MODEL_MODE=production
```

- **Service:** `janbot-api` — **URL `https://janbot-api-kafmnjtk3a-lm.a.run.app`**
- **Revision:** `janbot-api-00001-hpg` (100% traffic)
- Sizing from the Part A cold start (measured, not guessed): `--memory=2Gi`,
  `--timeout=60`, `--cpu=1`, `--max-instances=2`, `--concurrency=1`, `--min-instances=0`.

## Budget + alert

`gcloud billing budgets create --billing-account=01F9B3-809CD7-82262E --display-name=JanBot-deploy --budget-amount=10 --threshold-rule=percent=0.5 --threshold-rule=percent=0.9`
→ created `JanBot-deploy` at 10 CZK, then **updated to 500 CZK**:
`gcloud billing budgets update 3fcb5a77-5170-4a1b-ba05-ee71f6071389 --billing-account=01F9B3-809CD7-82262E --budget-amount=500 --clear-threshold-rules --add-threshold-rule=percent=0.5 --add-threshold-rule=percent=0.9`.
Final: **`JanBot-deploy`, 500 CZK, alerts at 50% and 90%.** (`--budget-amount` must be in the
billing account's own currency — CZK; an explicit `USD`/`EUR` is rejected against a CZK account.)

**Honest framing: a GCP budget is an ALERT, not a cap.** It notifies; it does not stop spend.
The current **real ceiling** is **`--max-instances=2` × `--concurrency=1`** (at most two
concurrent model calls in flight), plus the model provider's own limits. A **hard total
ceiling** — a quota that cannot be exceeded regardless of traffic — arrives with **E2's global
quota** (ADR-009 control 3).

## Close-out details — reviewer-verified plan-vs-reality deltas (not failures)

- **(a) The Cloud Run probe is the DEFAULT TCP startup probe, not `/health`.** Reality:
  `startupProbe = tcpSocket{port:8080}, periodSeconds=240, timeoutSeconds=240, failureThreshold=1`
  (Cloud Run's default). The plan claimed `/health` is the probe — corrected here. **Decision:**
  keep the default TCP probe for E1. It gates on the container **listening on 8080**, and
  uvicorn binds the port only after app startup completes (including the fail-closed index
  check), so it is effectively equivalent to an HTTPS `/health` probe here. An explicit HTTPS
  `/health` probe would only add value if the app bound the port **before** its dependencies
  were ready (it does not); **not worth configuring now** — revisit only if startup becomes lazy.
- **(b) Service naming deviation: the spike deployed as `janbot-api`, not `janbot-spike-*`.** The
  recorded decision wanted the spike stack named `janbot-spike-*` so E4's replacement is
  unambiguous. Reality: the service is `janbot-api`. **Resolution (E1.5):** the real stack keeps
  the meaningful name **`janbot-api`**; E1.5 **destroys** the hand-made spike and applies
  Terraform managing `janbot-api` — fresh, never imported — so after E1.5 there is exactly one
  `janbot-api` (Terraform-managed) and no lingering spike to confuse. The `janbot-spike-*`
  naming intent is superseded by the destroy-and-recreate.
- **(c) IAM policy is EMPTY → authenticated-only, owner/editor can invoke.** Reality: the
  service's IAM policy has **no bindings**. This is the **intended** E1 posture: only the
  owner/editor (project-level permissions) can invoke; no anonymous access. **Mechanism to
  share a demo later:** grant `roles/run.invoker` to a specific principal —
  `gcloud run services add-iam-policy-binding janbot-api --region=europe-central2 --member=… --role=roles/run.invoker`.
- **(d) `startup-cpu-boost=true` was enabled** (Cloud Run default annotation
  `run.googleapis.com/startup-cpu-boost=true`) but was not reported in the first draft. It
  allocates extra CPU during startup and **likely shaped the measured 19.46 s cold start**;
  recorded here for an honest cold-start picture.

## The 7 acceptance criteria — evidence

| # | Criterion / command | Result |
|---|---|---|
| 1 | `curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" $URL/health` | **200 `{"status":"ok"}`** ✓ |
| 2 | token `POST /chat` "What search infrastructure have you built?" | **200 `answered`**, citations `['cdbazar.org']` ✓ |
| 3 | token `POST /chat` "What is your salary expectation?" | **200 `insufficient`**, `reason=personal`, `citations=[]` ✓ |
| 4 | no token → `GET /health` and `POST /chat` | **403 / 403** ✓ |
| 5 | `gcloud run services describe` → env / concurrency / scaling | env `JANBOT_MODEL_MODE=production` + secret `OPENROUTER_API_KEY:latest`; **`JANBOT_PROGRAM_PATH` absent** (baseline ships); `containerConcurrency=1`; `maxScale=2` ✓ |
| 6 | cold start (first authenticated `/chat` after deploy) | **19.46 s** < `--timeout=60` ✓ |
| 7 | key in response bodies / Cloud Run logs | **0 / 0** (17 log lines scanned) ✓ |

## Boundaries honoured

Authenticated-only (no public access); `/chat` contract and AI core unchanged; no compiled
program (`JANBOT_PROGRAM_PATH` unset); key never baked/committed/echoed/logged; no Terraform.
