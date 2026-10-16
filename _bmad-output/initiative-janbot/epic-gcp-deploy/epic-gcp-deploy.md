---
tracker_id: ""
key: ""
type: epic
title: "Deploy JanBot to GCP (a public, recruiter-facing service)"
parent: initiative-janbot
covers: []
after: []
assignee: ""
risk: high
---

# Deploy JanBot to GCP (a public, recruiter-facing service)

## Description

Milestone 4: put the running JanBot service on GCP and expose it to recruiters. The service is containerized (python 3.12 + uv, corpus + index + embedding model baked in) and deployed to Cloud Run in an EU region behind Artifact Registry and Secret Manager, then hardened for public use by a **minimum guardrail layer** before it is opened up. The epic inherits two long-standing gates and resolves them: the spec's deployment/hosting Open Question (L92) and the pre-recruiter-deployment anonymization/guardrails requirement (spec L77/L86). The guardrails layer is the one nobody had scoped — it is the epic's centre of gravity and the reason the work is sequenced private → guarded → public.

## Outcome

A recruiter opens a public URL, asks a question, and receives a cited answer — or a graceful decline — from the shipped baseline `/chat` service, at bounded cost, behind guardrails that make exposing the endpoint safe.

## Requirements

- **E1 (deploy):** an authenticated Cloud Run spike proves the mechanics with ~zero cost exposure — the container bakes the corpus, the built index and the embedding model; `GET /health` = ok and `POST /chat` answers with citations through a verified `gcloud` identity token (not a public URL). (`spec-janbot.md` Open Questions L92; `backlog/story-gcp-deployment-terraform.md` id 3.)
- **E2 (guardrails):** the minimum guardrail/cost layer defined by ADR-009 (answer cache, per-IP rate limit, hard global quota, input bounds, the deterministic over-claiming guard, abuse control) is implemented, each control with its named acceptance test — the layer that makes going public safe.
- **E3 (public):** the service is opened with `--allow-unauthenticated` and the GitHub Pages widget (backlog 4) renders a cited answer, created as a **new public interface** by the superseding AD-1 decision (ADR-008: CORS origin + read-only posture).
- **E4 (IaC):** the deploy is reproducible — Terraform (Artifact Registry, Cloud Run, Secret Manager, a least-privilege service account) plus a GitHub Actions job using Workload Identity Federation.

## Done when

1. An **authenticated** Cloud Run URL answers `GET /health` = `{"status":"ok"}` and `POST /chat` with a real cited answer, proven with a verified gcloud identity token (E1) — not a public URL.
2. The minimum guardrail layer (ADR-009, owner-signed-off) is implemented and **every control has a passing acceptance test**; cost is bounded by a hard global quota plus a GCP budget alert.
3. The service is reachable unauthenticated only at E3, with the Pages widget rendering a cited answer and the CORS decision (ADR-008) in force.
4. `terraform apply` from a clean project provisions Artifact Registry + Cloud Run + Secret Manager + the least-privilege SA, and a GitHub Actions run deploys a revision via Workload Identity Federation with no long-lived key.
5. The `/chat` contract and the AI core are unchanged (backlog 3's boundary): no change to `api/`, `pipeline/`, `store/` semantics.

## Boundaries

Deployment, infrastructure and the guardrail layer. Not the `/chat` contract, not the AI core (`api/`, `pipeline/`, `store/`) — the service ships as built. Not the golden dataset, metrics or optimization (`epic-evaluation`; the compiled program is REJECTed by the gate, so the baseline ships). The widget (E3) is a thin caller with no AI logic (AD-2).

## References

- parent — `../initiative-janbot.md`
- spec — `../spec-janbot/spec-janbot.md`, Open Questions (deployment/hosting target, L92); Constraints ("No anonymization or guardrail layer in Milestone 1 … required only before real recruiter deployment", L77); Assumptions (L86)
- architecture — `../architecture-janbot/architecture-janbot.md`, AD-1 (contract-first port: "No other public interface is created without a superseding decision"), Deferred ("Deployment & hosting — target, infra, and environments not chosen")
- decision — `../spec-janbot/decisions.md`, ADR-007 (deployment target), ADR-008 (widget/CORS — AD-1 supersession), ADR-009 (minimum guardrail layer)
- source tickets — `../../backlog/story-gcp-deployment-terraform.md` (id 3), `../../backlog/story-gh-pages-chat-widget.md` (id 4)
- gate — `../epic-evaluation/gate-rule.md`, "## Verdict record" (entry 14 REJECT) — the baseline program ships, `JANBOT_PROGRAM_PATH` stays unset

## Notes

- **Governing gates (2026-10-16, owner restated):** the owner's goal is a **public, recruiter-facing API**. It sits directly on two pre-existing gates — the deployment/hosting target (spec L92) and the pre-recruiter-deployment guardrails/anonymization requirement (spec L77/L86). The guardrails layer was the one nobody had scoped; ADR-009 scopes it before going public.
- **Draft decision (2026-10-16, owner — the path, sequenced; awaiting sign-off):** private/authenticated spike → minimum guardrail layer → public (option (i), sequenced). Recorded in ADR-009.
- **Draft decision (2026-10-16, owner — deployment target; awaiting sign-off):** GCP Cloud Run + Artifact Registry + Secret Manager, EU region — `europe-central2` (Warsaw), nearest EU region to the owner. ADR-007.
- **Draft decision (2026-10-16, AD-1 supersession; awaiting sign-off):** the GH Pages widget is a **new public interface**; ADR-008 records its CORS origin and read-only posture. AD-1 is **intact for now** — the widget is deferred to E3, after the first (private) deploy.
- **Sign-off (2026-10-16, owner — after an independent verification):** ADR-007 and ADR-008 are **ADOPTED as-is**; ADR-009 is **ADOPTED CONDITIONALLY** — E2 must implement the deterministic output-level **over-claiming** guard (option (c)) and control 5 is reframed to over-claiming. Until E2 is implemented and evidenced, the service stays **authenticated-only** and spec L86's gate remains **formally OPEN**. (The three lines above are now adopted decisions, not drafts.)
- **Sequencing justified by measurement (2026-10-16):** the sequenced private→guarded→public path caught a real, reproducible defect **before any public exposure** — the over-claiming gap (`probe_over_claiming.py` / `-output.txt`: identity/commitment questions declined pre-LM by θ; `"Would you like to work for our company?"` answered with a corpus-absent first-person commitment, 2/2 byte-identical). The gate has demonstrably earned its keep.
- **Decision (2026-10-16, sequencing):** E1 (authenticated spike) is the tracer bullet (~zero cost exposure); E2 (guardrails) makes going public safe; E3 goes public + widget; E4 codifies the deploy (Terraform + WIF). E4 waits on E1–E3; the codified state matches the shipped state by **replacement, not import** — Terraform stands up a fresh stack and the E1 spike stack is torn down (see the resource-decision note below).
- **Decision (2026-10-16, scope):** the compiled variants are REJECTed by the pre-registered gate (entry 14) → **the baseline program ships**; `JANBOT_PROGRAM_PATH` stays unset (E1).
- **Gate status (honest, 2026-10-16):** until E2 is done and signed off, the service stays **authenticated-only** and the spec's recruiter-deployment gate (L86) remains **formally OPEN**. The gate is not satisfied before the controls exist and are evidenced.
- Unknown: the exact Cloud Run sizing (`--memory`/`--timeout`) for the MiniLM/Chroma cold start — settled by measurement at E1.
- Source conflict: none — the two backlog tickets agree with the spec/architecture; this epic resolves their unknowns (deploy target, guardrails) rather than contradicting them.
- Shared value list: the guardrail control set (ADR-009) is adopted by E2 and referenced by E4.
- **Decision (2026-10-16, slicing — no closing refactor sweep):** the entries are sequential deployment steps adding a `Dockerfile`/`.dockerignore`, an IaC tree, a static widget, **and E2's guardrail layer in front of `/chat`** — no shared *existing* code surface to sweep — so no "Refactor sweep" entry is added. **Revisit at closure:** E2 *does* add code (the guardrail layer), so a sweep candidate may exist then. (Owner may override.)
- **Source conflict (2026-10-16):** `backlog/story-gcp-deployment-terraform.md` (id 3) asks for a **public** Cloud Run URL as its single acceptance criterion; E1 deliberately ships **authenticated-only** (`--no-allow-unauthenticated`). This is a deliberate reframing, not a contradiction: going public is E3, gated on E2's guardrail layer (the spec L86 pre-deployment gate); the source ticket's AC is satisfied across the epic.
- **Decision (2026-10-16, owner — guardrail store):** split the controls by storage need. The **cache is a build-time artifact baked into the image** (static, zero runtime store). Only the **rate-limit and quota counters** need shared state → **Firestore in native mode, `europe-central2`** (serverless, atomic increments, GCP-native, Terraform-friendly, generous free tier). **Memorystore Redis is rejected** (a VPC connector plus a ~$30–40/month floor is unjustified). **`--max-instances=1` is a fallback only, not a solution** — instance-local counters reset on restart and cannot honour "cannot be exceeded regardless of traffic". E4 owns the Firestore IaC.
- **Decision (2026-10-16, owner — E1 vs E4 resources): FRESH, never `terraform import`.** Backlog 3's acceptance criterion is literally "`terraform apply` yields a public Cloud Run URL …", so reproducibility is only proven from zero; importing hand-made spike resources would evidence nothing and risk a half-managed state. The spike stack is named distinctly (`janbot-spike-*`) and **torn down** once E4's Terraform stands up the real stack; the E4/E1 match is by **replacement**, not import.
- **Data source (2026-10-16):** the guardrail cache (ADR-009 control 1) precomputes the answers for the **91** questions in `eval/golden_dataset.yaml` (the current golden set, owned by `epic-evaluation`); E2 carries `epic-evaluation` in `after`.
