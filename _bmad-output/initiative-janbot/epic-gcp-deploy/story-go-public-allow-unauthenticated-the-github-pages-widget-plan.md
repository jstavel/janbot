---
title: 'Go public — allow-unauthenticated + the GitHub Pages widget'
type: 'feature'
ticket: 3
created: '2026-10-22'
status: 'built'
baseline_revision: '3a04152'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** E2 is closed — Amendment 5 verified live on `janbot-api-00008-86p` (2026-10-21), the control-5 residual is owner-accepted, and the spec L86 deployment gate closes — so the only thing between the owner's goal (a public, recruiter-facing API) and reality is the flip: the deployed service is still authenticated-only, and no recruiter-facing page exists. ADR-008 (the AD-1 supersession) already authorizes the second public interface.

**Approach:** flip Cloud Run to public ingress **in Terraform** (the `allUsers` `roles/run.invoker` binding — infrastructure state, not a console change), add the ADR-008 CORS allowance as an opt-in knob (`JANBOT_CORS_ORIGINS`, exact Pages origin, POST-only), and publish a static GitHub Pages widget — a thin caller of `POST /chat` that renders the cited answer or the graceful decline through the unchanged contract and the guardrail layer. Because the service runs scale-to-zero, usage must be observable: the daily guardrail counters gain `served`/`declined` totals, readable after the fact with no redeploy.

**Owner decisions (2026-10-22, do not re-open):**
- **`min_instances = 0` stays.** The owner accepts ~8–23 s for a first cold visitor; ~$75/month for `min_instances=1` buys one eliminated wait on negligible traffic — not worth it. `max_instances` and low concurrency stay as-is.
- **Usage visibility is part of done.** Totals of **requests served / declined per day** from the existing Firestore guardrail store, queryable **without redeploying**; no full analytics; **no raw IPs, no question or answer text** anywhere new.

## Boundaries & Constraints

**Always:** the `/chat` contract (`ChatResponse` shape, error envelope) and the AI core semantics (`pipeline/`, `store/`) are unchanged; the only code additions are the CORS allowance — a public-surface middleware wired in `create_app` (the same precedent as E2's `BodySizeLimitMiddleware`) plus its config knob — and the usage counters. Terraform owns the flip in one plan whose only changes are the named ones: the image digest (via the `src/**` trigger), the new env, and the IAM binding. The widget is static — no framework, no build step, no secrets, `POST /chat` only. CORS preflights are answered at the middleware edge and consume no rate/quota. Usage counters are **fail-open** (a counter error never denies a request) and record no IP or text. Guardrails stay on in production and must re-prove live on the public revision. No key in any response body, log line, or public artifact.

**Never:** no CORS origin beyond `https://jstavel.github.io`; no `Access-Control-Allow-Credentials`; no manual `gcloud`/console flip outside Terraform; no AI logic in the widget; no new dependency (Starlette's `CORSMiddleware`, `google-cloud-firestore` already present); no public usage/metrics endpoint (a new interface would need a superseding decision); no change to E2's recorded evidence; no other route or method made public.

**Widget scope (owner, 2026-10-22):** a demo, not a project page — question input, the cited answer or graceful decline, error states (429/413/422), loading copy for the cold start, and **at most one short caption paragraph linking to the repo README**. It must **never** duplicate README content, documentation, blog material, or anything derived from the corpus (`public_profile_org/`): the README is the claim, the widget is the chance to try it — duplication would create a second source of truth over the same facts.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| PREFLIGHT allowed | `OPTIONS /chat`, Origin `https://jstavel.github.io`, Request-Method POST | 200 with `Access-Control-Allow-Origin: https://jstavel.github.io` | answered at the middleware edge |
| PREFLIGHT refused | `OPTIONS /chat` from any other Origin, or a method ≠ POST | 400 `Disallowed CORS origin`/`method`, no ACAO header | never reaches the route |
| Browser POST allowed | `POST /chat` with the Pages Origin | normal response + ACAO echoed — including 429/413/422 refusals, so the widget can show them | refusal bodies readable |
| Browser POST other origin | `POST /chat` from a non-listed Origin | response carries no ACAO header — the browser blocks the read | non-browser callers unaffected |
| Knob unset | `JANBOT_CORS_ORIGINS` unset/blank | middleware absent; behavior byte-identical to today | eval/tests unchanged |
| Cache-hit demo | a golden question from the widget | cached answer, no model call, quota not consumed | demo survives a spent quota |
| USAGE served | answered reply (live or cache hit) | `usage_<UTC date>.served` +1 | counter error logged, request unaffected |
| USAGE declined | `insufficient` reply, or a route-level guardrail refusal (422/429/503) | `usage_<UTC date>.declined` +1 | counter error logged, request unaffected |
| USAGE read | operator runs the CLI | served/declined totals for the date(s) | no store/ADC → clear error, no service impact |

</frozen-after-approval>

## Code Map

- `src/janbot/api/main.py:227-258,289-339` — `create_app` middleware wiring and the `/chat` outcomes; add `CORSMiddleware` outermost (after `BodySizeLimitMiddleware`) from `fastapi.middleware.cors`, and call the usage counter on each outcome (sync handler → threadpool, so a blocking Firestore write is safe; the async body-limit middleware does not count — 413/400 stay in the decline log).
- `src/janbot/config.py` — new `JANBOT_CORS_ORIGINS` (comma-separated, trimmed; blank = unset), `Config.cors_origins: tuple[str, ...] | None`.
- `src/janbot/guardrails/usage.py` — NEW: `UsageCounter` (Firestore `janbot_guardrails` collection, doc `usage_<YYYY-MM-DD>`, `served`/`declined` atomic increments, fail-open) + `python -m janbot.guardrails.usage --date|--days` read CLI (no service dependency).
- `widget/index.html` — NEW, single file, vanilla JS: question input → `fetch` POST to the service URL → render `answer` + `citations[].source`; map `insufficient`/`reason` to the graceful-decline copy; surface 429/413/422 `detail`; loading copy ("first question after idle may take up to ~23 s"); at most one short caption linking the repo README. **The service URL is a public, non-secret constant hardcoded once at the top of this file** — no CI injection, no build step; one source of truth in one file. No key.
- `.github/workflows/pages.yml` — NEW: deploy `widget/` to Pages from `main` on `widget/**` (configure-pages enablement, upload-pages-artifact, deploy-pages). Site `https://jstavel.github.io/janbot/` → Origin exactly `https://jstavel.github.io` (the origin is the domain, not the path, so first-deploy timing cannot change it).
- `terraform/main.tf:208-310` — add `google_cloud_run_v2_service_iam_member` (`allUsers` + `roles/run.invoker`) and the `JANBOT_CORS_ORIGINS` env; `variables.tf` gains `cors_origins`.
- `README.md` §Configuration — one row for the knob.
- `tests/test_cors_api.py`, `tests/test_usage.py` (NEW) + `tests/test_config.py` — the matrix as named tests.
- `_bmad-output/initiative-janbot/epic-gcp-deploy/run-e3-public.md` — NEW: flip/verify/live-acceptance runbook plus the usage query, in `run-e2-guardrails.md` style.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/config.py` — parse/validate `JANBOT_CORS_ORIGINS`; default unset — the knob.
- [ ] `src/janbot/api/main.py` — wire `CORSMiddleware` (`allow_origins`, `allow_methods=["POST"]`, `allow_headers=["content-type"]`, no credentials), added last; call `usage.record_served/declined` per outcome; add a `usage=None` test seam — the allowance + visibility.
- [ ] `src/janbot/guardrails/usage.py` — fail-open daily counters + read CLI — the artifact the owner reads.
- [ ] `widget/index.html` — the thin caller — the demo.
- [ ] `.github/workflows/pages.yml` — the Pages publication.
- [ ] `terraform/main.tf` + `variables.tf` — allUsers binding + CORS env — the flip as IaC.
- [ ] `README.md` — the knob row — one authority.
- [ ] `tests/` — preflights allowed/refused, POST-only method check, ACAO echoed on refusals, unset-knob no-op, usage increments, usage fail-open, config parsing — the falsifiable layer.
- [ ] `run-e3-public.md` — flip procedure, preflight curls, live-acceptance table (rate N+1 → 429; 2500-char → 422; 9 KB body → 413; Amendment-5 probes with cache-hit vs live-guard attribution), and the usage query — owner-runnable. **Pre-apply checks it must carry:** (i) the project's effective IAM constraints (`iam.allowedPolicyMemberDomains` and neighbours) can refuse the `allUsers` binding at apply time even when `plan` is clean — inspect them and, if allowed, attempt the binding by hand before the formal apply; (ii) Pages must be enabled in the repo with GitHub Actions allowed — a one-time manual precondition, or `configure-pages` fails confusingly on the first run.
- [ ] Verified `terraform plan` — the round ends here; the owner runs the apply (E2 blast-radius rule).

**Acceptance Criteria:**
- Given the published Pages page, when a visitor asks a question, then the cited answer (or the graceful decline) renders through the deployed public service.
- Given a preflight from the Pages origin, then it succeeds; given any other origin or method, then it is refused (400, no ACAO).
- Given the flipped stack, then the plan shows only the named changes (new image digest, the new env, the IAM binding) — no other drift.
- Given the public revision, then the guardrail layer re-proves live: the N+1th request is refused (429), oversized input is rejected (413/422), and one over-claiming case behaves per Amendment 5.
- Given traffic, when the owner runs the usage CLI, then served/declined totals for the day are returned without a deploy, and no record contains an IP or question/answer text.
- Given the widget sources, then they contain no key and only `POST` to `/chat`.

## Implementation Notes

## Plan Change Log

- 2026-10-22 — owner review before approval: added the `allUsers` pre-apply org-policy check and the Pages-enablement precondition to the runbook task; pinned the widget's service URL as a single hardcoded constant; added the owner's widget-scope constraint (demo, not a project page — no README/corpus duplication, at most one caption link). Frozen block unchanged apart from the owner's own scope sentence.

## Review Triage Log

- 2026-10-22 — owner review (pre-approval). Findings: **1** — org policy (`iam.allowedPolicyMemberDomains`) can refuse `allUsers` at apply while `plan` is clean → **patched**, named pre-apply check added to the runbook task; **2** — widget service-URL source unstated → **patched**, one hardcoded constant in `widget/index.html`, no CI injection; **3** — Pages must be enabled with Actions allowed before the first workflow run → **patched**, one-time precondition in the runbook task. Scope clarification (owner): widget is a demo with at most one caption linking the README, no content duplication → **recorded** in Boundaries. No finding touched the frozen block.

### Review pass 2026-10-22 — quick lens (0 high / 4 medium / 4 low / 1 false)

| finding | verdict | route | evidence |
|---|---|---|---|
| runbook pre-apply probe leaves `allUsers` granted if the apply aborts, so a public service can exist outside Terraform state | medium | patch (fixed) | verified: the probe added the binding and never removed it; now add→remove with a "removal failed — do not proceed" branch, and the service becomes public only via the owner's apply |
| `allUsers` exposes `/docs`, `/redoc`, `/openapi.json` beyond ADR-008's `POST /chat` + `GET /health` posture | low | patch (fixed) | verified against `FastAPI(title="JanBot")` defaults; production now builds with `docs_url`/`redoc_url`/`openapi_url = None` (eval unchanged); production-404 + eval-200 tests added |
| CORS middleware is app-wide, so the allowed origin can read GET routes | low | rejected | verified true as filed, but after the docs patch the only allowed-origin-readable GET route is `/health` (`{"status":"ok"}`, no data, no state); path-scoping needs a custom middleware (more than a direct correction), and no user/developer harm is plausible |
| `JANBOT_CORS_ORIGINS` accepts `*` and malformed origins; `*` makes Starlette allow every origin | medium | patch (fixed) | verified `allow_origins=["*"]` → `allow_all_origins`; `_valid_origin` now rejects `*`, non-http(s), path/query/fragment (incl. trailing slash) and userinfo, fail-fast naming the variable; 12 rejected shapes + accepted forms tested |
| fail-open covers only `ref.set`; lazy import, clock and `document()` can escape and 500 a served request — plus `served` counted before response validation | medium | patch (fixed) | verified the three statements sat outside the `try`; the whole `_increment` body is now inside it. The served-before-validation sub-claim is **low and accepted** (reachable only via a program-contract bug that already 500s; it overcounts by one and a post-serialization counter is a restructure, not a patch) |
| reconciliation says `served + declined` excludes only 413/400 and 5xx | low | patch (fixed) | verified pre-handler 422s (blank/malformed), 405s and `/health` also bypass the route; runbook wording corrected to list them |
| canonical runbooks/output still say authenticated-only; invoker grants listed outside Terraform | medium | patch (fixed) | verified `RUNBOOK.md:107`, `terraform/RUNBOOK.md:11,236`, `terraform/outputs.tf:2`; updated to the public posture (token-free `/chat`, Pages CORS origin, Terraform-owned `allUsers`) |
| rollback text claims an empty `cors_origins` "removes the env" and IAM removal waits for a revision | low | patch (fixed) | verified the env block is unconditional and the IAM binding is service-level; rollback now says the env stays blank (middleware absent) and the IAM removal is immediate |
| the retrospective file contradicts the E3 state ("no plan files", 8.3 pending) | false | rejected | disproved: the file was already untracked at baseline (`git status` before any change), predates this work, is not in the Code Map, and no task touched it — it appears in the staged diff only because untracked files are included |

## Design Notes

- **Why the middleware lives in `create_app`:** E2 established `create_app` as where request-surface middleware lands; CORS is the same kind of addition — in front of the unchanged core, no contract change. The knob keeps it opt-in (unset = today's behavior).
- **Why Starlette's `CORSMiddleware`:** deny-by-default; preflight refusals are real server-side 400s (`Disallowed CORS origin`, verified in installed starlette 1.7.0) — "a request from a different origin is refused" is server behavior, not just browser convention.
- **Why the widget lives in this repo:** `https://jstavel.github.io/janbot/` sends Origin `https://jstavel.github.io` — exactly the ADR-008 origin; one repo, one workflow.
- **Usage design:** the existing `quota_<date>` counter mixes answered and declined (it counts program-bound requests) and declines otherwise live only in logs, so a daily `usage_<date>` doc with two atomic increments is the minimum that answers "is anyone using this?". Cost: one extra Firestore write per request (~50–90 ms, E2's measured per-op) — acceptable against a 0.95–23 s request range; a failed usage write is logged and never denies. A read-only CLI keeps the query operator-side: no new public surface, no redeploy. Totals exclude pre-route body-limit refusals (413/400), which stay in the decline log.
- **Honest scope of the flip:** unauthenticated means any HTTP client, not just browsers — CORS constrains only which origins a *browser* lets read responses; the abuse controls are the per-IP rate limit + global quota (ADR-009 control 7), which is why they re-prove live.

## Verification

**Commands:**
- `uv run pytest tests/test_cors_api.py tests/test_usage.py tests/test_config.py -q` — green.
- `ulimit -n 16384 && uv run pytest -q` — the full suite stays green.
- `terraform -chdir=terraform validate && terraform -chdir=terraform plan -var image_tag=$(git rev-parse --short HEAD) -var registry_auth_file="$DOCKER_CONFIG/config.json"` — exactly: the IAM `allUsers` binding (1 add), the service revision change (env + new image digest), 0 destroy.
- Post-apply probes (runbook): `OPTIONS` from the Pages Origin → 200 + ACAO; another Origin → 400; cross-origin POST → no ACAO; the published page answers end-to-end.
- `uv run python -m janbot.guardrails.usage --date <UTC date>` — prints served/declined for the day.
