---
title: 'Containerize and deploy an authenticated Cloud Run spike'
type: 'feature'
ticket: 1
created: '2026-10-16'
status: 'draft'
baseline_revision: '3927d71'
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

**Problem:** Milestone 4 needs the running `/chat` service on GCP for recruiters (`epic-gcp-deploy`). The deployment target was a long-standing spec Open Question (L92), and the pre-recruiter-deployment guardrails gate (spec L77/L86) is unresolved — so the first step must prove the container/Cloud Run mechanics with **~zero cost exposure** before anything is exposed or hardened.

**Approach:** **the authenticated spike.** Containerize the service (python 3.12 + uv; the corpus, the built vector index and the embedding model **baked in at build time** — no ingest at startup) and deploy it to **Cloud Run in the EU region as `--no-allow-unauthenticated`**, then prove `GET /health` = ok and `POST /chat` answers with citations **through a verified `gcloud` identity token**. The acceptance is an authenticated URL, not a public one. Guardrails (E2) and going public (E3) are later entries; Terraform (E4) comes after.

## Boundaries & Constraints

**Always:** the `/chat` contract and the AI core are unchanged (backlog 3's boundary; AD-1/AD-2/AD-7); `JANBOT_MODEL_MODE=production`; `OPENROUTER_API_KEY` is supplied from **Secret Manager** at runtime and is never baked, committed, or printed; `JANBOT_PROGRAM_PATH` stays **unset** (the compiled program was REJECTed by the pre-registered gate — `epic-evaluation/gate-rule.md` "## Verdict record" entry 14 — so the baseline ships); the index is built **at image-build time** and `JANBOT_INDEX_PATH` points at the baked path; Cloud Run runs in an **EU region** with `--min-instances=0`, a **hard `--max-instances` cap** and low `--concurrency` (the DSPy program is per-instance shared state), with `--memory`/`--timeout` sized for the MiniLM + Chroma cold start; a **GCP budget + alert** is the financial backstop; the existing `GET /health` is the Cloud Run probe; the deploy is **hitl** (owner's GCP account + approval).

**Never:** no change to the `/chat` contract or the AI core; no public (unauthenticated) access in this entry; no ingest at startup; no compiled/optimized program shipped; the key is never baked into the image, committed, echoed, or logged; no Terraform in this entry (E4 owns IaC); no new server capability beyond what `/chat` and `/health` already provide.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY detection | authenticated `GET /health` | `{"status":"ok"}` | none |
| HAPPY answer | authenticated `POST /chat`, in-corpus question | 200 `answered`, ≥1 citation | none |
| DECLINE | authenticated `POST /chat`, out-of-corpus/personal question | 200 `insufficient`, empty citations, `reason` set | no error (graceful decline) |
| UNAUTHENTICATED | no token, any route | request **not served** (403) | refused by Cloud Run IAM |
| COLD START | first request after scale-to-zero | served within the configured `--timeout` | a timeout sized for MiniLM+Chroma load |
| KEY EXPOSURE | any response body / log line | never contains `OPENROUTER_API_KEY` | n/a (must not occur) |

</frozen-after-approval>

## Code Map

- `pyproject.toml` — `requires-python >=3.12`; deps include `fastapi`, `uvicorn`, `dspy`, `chromadb`, `orgparse`; the image installs from `uv.lock` (reproducible).
- `src/janbot/api/main.py:116-118` — `GET /health` → `{"status":"ok"}` (the Cloud Run probe); `:120-129` `POST /chat` (+ the decline mapping) — the two routes to prove.
- `src/janbot/config.py:68-85,243-251` — the `JANBOT_*` surface: `JANBOT_MODEL_MODE`, `JANBOT_INDEX_PATH` (default `chroma_db`), `JANBOT_CORPUS_PATH` (default `public_profile_org`), `JANBOT_PROGRAM_PATH` (must stay unset).
- `src/janbot/store/chroma.py:155-166` — `default_embedder()` uses Chroma's `DefaultEmbeddingFunction` (ONNX `all-MiniLM-L6-v2`); the model must be **pre-downloaded/baked** or the container cold start fetches it.
- `src/janbot/ingest/__main__.py` — `python -m janbot.ingest` builds the index from the corpus; run **at image build** to bake the index.
- `public_profile_org/` (~280K) + the built index — copied/built into the image; `JANBOT_INDEX_PATH` → the baked path.
- `Containerfile` + `.dockerignore` — **new** (none exists today): multi-stage python 3.12-slim + uv, install from `uv.lock`, bake the index and the ONNX model, `CMD` uvicorn. Named **`Containerfile`** (OCI-standard, identical syntax; matches the owner's Red Hat/Podman-buildah workflow), so every build passes `-f Containerfile` explicitly (see the task).
- `tests/test_smoke.py` — existing `/health` coverage; `tests/e2e/` — keyed e2e (not run in this entry).
- `_bmad-output/initiative-janbot/epic-gcp-deploy/` — the epic, its `tickets.toml`, and this plan; the deploy runbook/evidence land here.

## Tasks & Acceptance

**Execution:**
- [ ] `Containerfile` — new multi-stage image: python 3.12-slim + uv, deps from `uv.lock`; copy `src/` and `public_profile_org/`; run `python -m janbot.ingest` at build to bake the index; pre-download Chroma's ONNX MiniLM model; set `JANBOT_MODEL_MODE=production`, `JANBOT_INDEX_PATH`/`JANBOT_CORPUS_PATH` to the baked paths; `CMD` uvicorn on `$PORT`. No key, no startup ingest. **Every build invocation is explicit so nothing auto-detects a missing `Dockerfile`:** `podman build -f Containerfile` / `buildah bud -f Containerfile` / `docker build -f Containerfile`; for Cloud Run/Cloud Build pin the path explicitly (`gcloud run deploy --source . --dockerfile=Containerfile`, or a Cloud Build config naming it).
- [ ] `.dockerignore` — exclude `.git`, `.venv`, `tests/`, `mlruns/`, `mlflow.db`, `eval/compiled_*.json`, `__pycache__`, and the local `chroma_db/` (rebuilt in-image). Keep the **neutral name** `.dockerignore` — Podman reads `.containerignore` first then falls back to `.dockerignore`, and Docker reads `.dockerignore`, so one file serves both.
- [ ] Build + push to Artifact Registry and deploy to Cloud Run (`--no-allow-unauthenticated`, region `europe-central2`, `--min-instances=0`, hard `--max-instances`, low `--concurrency`, sized `--memory`/`--timeout`), mounting `OPENROUTER_API_KEY` from Secret Manager (hitl).
- [ ] Attach a **GCP budget + alert** as the financial backstop.
- [ ] `_bmad-output/initiative-janbot/epic-gcp-deploy/run-e1-deploy.md` — a short runbook + the evidence: the image digest, the revision, the region, and the authenticated probe transcript (hitl).

**Acceptance Criteria:**
- Given a verified `gcloud` identity token, when `GET /health`, then `{"status":"ok"}`.
- Given a verified token, when `POST /chat` with an in-corpus question, then 200 `answered` with ≥1 citation.
- Given a verified token, when `POST /chat` with an out-of-corpus question, then 200 `insufficient` (a graceful decline).
- Given **no** token, when either route is requested, then the request is not served (403).
- Given the deploy, then the run's `program` marker is `baseline` (`JANBOT_PROGRAM_PATH` unset) — no compiled program ships.
- Given the deployed revision and a cold start, then the first authenticated `POST /chat` is served within the configured `--timeout`.
- Given any response body or log line from the spike, then it contains no `OPENROUTER_API_KEY` material.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Design Notes

- **Why bake the index and the model** (not fetch at startup): the eval discipline pins every run to a locked dataset/snapshot; a baked index is the deploy analogue — the served index is exactly the tested one, with no ingest drift and no external bucket. It also makes the cold start self-contained (one ONNX model load, no network fetch).
- **Why authenticated first:** an unauthenticated Cloud Run endpoint with a live OpenRouter key is a cost/abuse surface; the spike proves the container, the baked index, the Secret Manager wiring and the `/chat` path at ~zero exposure before ADR-009's controls exist.
- **Sizing is measured, not guessed:** `--memory`/`--timeout` are settled by watching the first cold-start `/chat` (MiniLM load + Chroma open + one retrieve+answer).
- **Depends on two DRAFT ADRs:** this plan pins `europe-central2` and the guardrail posture from **ADR-007**/**ADR-009**, which are **DRAFT, awaiting owner sign-off**. The entry is `hitl` + `plan_checkpoint`, so both ADRs must be signed off before the build starts; if the owner changes the region or the guardrail scope, the affected Constraints here are superseded.

## Verification

**Commands:**
- `ulimit -n 16384 && uv run pytest -q` -- expected: green (the full suite needs a raised file-descriptor limit; the default soft limit 1024 makes the store tests fail with EMFILE — see README "Development").
- Containerfile honour check (hitl — **measure, do not assume**): `gcloud run deploy --help`, and a `--source`/Cloud Build run probing how the current CLI picks the build file (e.g. `gcloud run deploy <svc> --source . --dockerfile=Containerfile` / a Cloud Build config naming `Containerfile`). **Record the flag or config that makes it use `Containerfile`.** If the current CLI does **not** honour a Containerfile path, **record that finding in this plan** and fall back to `podman build -f Containerfile` + push, then `gcloud run deploy --image <ref>`.
- Authenticated probe (hitl): `curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" https://<url>/health` → `{"status":"ok"}`; `POST /chat` → a cited answer.
- Unauthenticated check: `curl -s -o /dev/null -w '%{http_code}' https://<url>/health` → `403`.
- Config check: `gcloud run services describe <svc> --region europe-central2` → min/max instances, concurrency, and the mounted secret as intended; the run's `program` param is `baseline`.
