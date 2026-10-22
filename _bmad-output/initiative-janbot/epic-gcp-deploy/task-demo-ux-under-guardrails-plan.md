---
title: 'Demo UX under the guardrails — Retry-After, rate 20/10min, startup-cpu-boost, gemini measurement'
type: 'feature'
ticket: ''
created: '2026-10-22'
status: 'built'
baseline_revision: '440b6d3'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the owner's live demo observations (measured 2026-10-22): a 429 renders as the raw machine string `429: too many requests` with no hint of when to return; the 10/10min per-IP limit false-refuses a shared office address (a 12-request burst produced a bare 429); and the ~50 s cold start is a visitor's first impression. Separately, `google/gemini-2.5-flash` looks ~4× faster than the routed model, but nothing measured it against the shipped baseline.

**Approach (four parts, per the task file):**
1. **Honest refusal** — the guardrail 429 carries `Retry-After` (seconds) computed from the *actual* window (the next boundary that frees a slot); the widget renders human copy with the wait. The 503 store-unavailable path carries **no** `Retry-After` (a store error's recovery time is unknown — omitting is the honest choice). The other 429 (quota exhausted) carries the honest equivalent: seconds to the next UTC midnight reset.
2. **Rate 20/10min** — `var.rate_limit` default 10 → 20; the runbook records the why (the daily quota + cache are the cost guard; the per-IP window is anti-abuse, and anti-abuse at ten per office is a UX defect) and the residual risk (more model calls per office before the quota bites). No IP-less identity (non-goal).
3. **Startup CPU boost** — `template.containers.resources.startup_cpu_boost = true` (free); the cold start is re-measured after the owner's apply and the number recorded in the runbook.
4. **gemini-2.5-flash measurement** — a golden val run in **eval mode** with `JANBOT_MODEL_SNAPSHOT=google/gemini-2.5-flash` and the **judge pinned to the reference judge** (`anthropic/claude-haiku-4.5` — changing the judge would invalidate faithfulness comparability); compare faithfulness, answer_coverage, refusal_pass_rate, spurious_refusal_rate; record run id + numbers + conclusion (no regression → propose the production change; regression → do not change, name the metric). **Owner decision (2026-10-22): the comparison target is `156b5d1a`**, the registered current reference on the identical corpus/index/dataset/judge — **superseding the task file's `c6ced445` pointer**, which named the 2026-10-15 historical reference (dataset `1c3864bd…`, old corpus, gate-eligible n=44) from memory; the measurement note records the supersession and why (a stale pointer is a finding, not a slip to hide), and states explicitly that the gemini comparison **says nothing about the historical `c6ced445` gate line** — the two must not be read as a sequence. **Non-goal:** production routing is untouched.

**Always:** the `/chat` JSON schema (and the `ChatResponse`/`Citation` contract) is unchanged — `Retry-After` is a response *header* on the existing 429 envelope, and the error `detail` strings stay byte-identical (the widget keys on them). The AI core is untouched; the only `src/` change is in the guardrail layer (`limits.py` decision object + `main.py` header wiring). Parts 1–3 ship as one round ending at a verified `terraform plan`; the owner applies; the cold-start re-measure follows the apply. Part 4 is a measurement producing a decision input, not a diff.

**Never:** no SSE/streaming (explicitly out of scope); no cookies/sessions/IP-less identity; no change to what production routes to; no change to the 413/422/5xx widget behaviour (keep the `{detail}` rendering); no fabricated `Retry-After` on 503.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| RATE 429 | N+1th request in the window | 429 + `Retry-After` = seconds to the next window boundary | two calls in one window → the header decreases |
| QUOTA 429 | daily quota exhausted | 429 + `Retry-After` = seconds to the next UTC midnight | honest reset time |
| STORE 503 | Firestore unreachable | 503, **no** `Retry-After` header | fail closed, as today |
| WIDGET refusal | fake 429 fetch with `Retry-After` | *"Too many questions from this address — try again in about N minutes."* (N = ceil(seconds/60)) | no header → the copy without a number |
| WIDGET quota | fake 429 whose `detail` names the daily quota | the daily-limit copy | keyed on the stable `detail` string |
| WIDGET other errors | fake 413/422/5xx | unchanged `{detail}` rendering | as today |
| PLAN | rate default + boost + part-1 image | exactly: image digest (src trigger), `JANBOT_RATE_LIMIT` env, `startup_cpu_boost`, 0 destroy | anything else is a finding |

</frozen-after-approval>

## Code Map

- `src/janbot/guardrails/limits.py:33-46,105-135` — `GuardDecision` gains `retry_after_seconds: int | None` (default `None` keeps every existing constructor and test honest); `check_rate` computes `(window+1)·W − now`; `consume_quota` computes the seconds to the next UTC midnight.
- `src/janbot/api/main.py:270-283` — `_guard_denied` attaches `headers={"Retry-After": str(...)}` when the decision carries one; 503 stays header-free.
- `widget/index.html` — the 429 branch renders the human copy (rate vs daily-limit, keyed on the stable `detail` string) with `ceil(Retry-After/60)` minutes; everything else unchanged.
- `tests/widget/index.test.mjs` (NEW) + `tests/test_widget.py` (NEW) — node reads the shipped HTML, runs its inline script in a `vm` with stubbed `document`/`fetch` (no network), drives the submit handler with fake responses; the pytest wrapper skips only when `node` is absent.
- `tests/test_guardrails_limits.py`, `tests/test_guardrails_api.py` — the matrix rows as named tests (incl. the two-calls-one-window decreasing-header boundary).
- `terraform/variables.tf:49-53` — `rate_limit` default 20; `terraform/main.tf` resources block — `startup_cpu_boost = true`.
- `_bmad-output/initiative-janbot/epic-gcp-deploy/run-e3-public.md` — new "Guardrail tuning" section: the rate reasoning + residual risk, the cold-start re-measure procedure, and the post-apply numbers.
- Part 4 evidence: NEW `_bmad-output/initiative-janbot/epic-gcp-deploy/measurement-gemini-2.5-flash-val.md` — run id, config (snapshot + pinned judge), the four metrics vs the reference, and the stated conclusion. Reference numbers (current registered baseline `156b5d1a`, same corpus/index/dataset, judge `claude-haiku-4.5`): faithfulness 0.9184, answer_coverage 0.9796, refusal_pass_rate 1.0000, spurious_refusal_rate 0.0204 (n=49; refusal n=10).

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/guardrails/limits.py` — the decision field + the two honest computations — the mechanism.
- [ ] `src/janbot/api/main.py` — the header wiring — the surface.
- [ ] `widget/index.html` — the human refusal copy — the UX.
- [ ] `tests/widget/index.test.mjs` + `tests/test_widget.py` — the fake-fetch widget test — the done-when's no-network proof.
- [ ] `tests/test_guardrails_limits.py` + `tests/test_guardrails_api.py` — the matrix rows — the falsifiable layer.
- [ ] `terraform/variables.tf` + `terraform/main.tf` — rate 20 + startup-cpu-boost — the flip.
- [ ] `run-e3-public.md` — the tuning section + the cold-start re-measure procedure — the record.
- [ ] Part 4 — the eval run (key present locally; ~59 answer + judge calls, cents) + the measurement note — the decision input.
- [ ] Verified `terraform plan` — the owner runs the apply.

**Acceptance Criteria:**
- Given two refusals inside one rate window, when the second is served, then its `Retry-After` is strictly smaller than the first's.
- Given a 429, then the `/chat` JSON schema is unchanged and the header is an integer consistent with the window; given a 503, then no header.
- Given a fake 429 fetch response carrying `Retry-After`, then the widget (tested without network) shows the wait in minutes; 413/422/5xx behaviour is unchanged.
- Given the flipped stack, then the plan shows only the named changes and the runbook states the rate reasoning + residual risk.
- Given the eval run, then the comparison note records the run id, the four metrics, and one of the two stated conclusions.

## Implementation Notes

- **Files changed:** `src/janbot/guardrails/limits.py` (GuardDecision gains
  `retry_after_seconds: int | None`; `check_rate` computes
  `(window+1)·W − floor(now)`, `consume_quota` computes ceil-seconds to the
  next UTC midnight), `src/janbot/api/main.py` (`_guard_denied` attaches
  `Retry-After` + `Access-Control-Expose-Headers` on 429; 503 header-free),
  `widget/index.html` (429 branch → human copy keyed on the stable detail
  strings), `tests/widget/index.test.mjs` + `tests/test_widget.py` (NEW),
  `tests/test_guardrails_limits.py` (+6 tests, 2 extended),
  `tests/test_guardrails_api.py` (+4 tests, RecordingLimiter extended),
  `terraform/variables.tf` (rate default 20), `terraform/main.tf`
  (`startup_cpu_boost = true`), `run-e3-public.md` ("Guardrail tuning"
  section), and the part-4 note `measurement-gemini-2.5-flash-val.md` (NEW).
- **Finding — the widget could never have read the header without one extra
  header:** `Retry-After` is not a CORS-safelisted response header, so the
  Pages-origin fetch reads `null` unless the 429 also carries
  `Access-Control-Expose-Headers: Retry-After`. The frozen intent ("the widget
  renders human copy with the wait") is unlive without it; it is attached on
  the same 429 response inside `_guard_denied` (header wiring is this plan's
  own `main.py` surface), pinned by
  `test_rate_429_exposes_retry_after_to_the_browser_across_origins`. The JSON
  schema is untouched.
- **Part 4 run:** `effd4854d9b04bb9b3029184789443ef`, judge pinned to
  `anthropic/claude-haiku-4.5`; all four compared metrics identical to the
  reference `156b5d1a` (faithfulness 0.9184, answer_coverage 0.9796,
  refusal_pass_rate 1.0000, spurious_refusal_rate 0.0204) → the stated
  conclusion is "propose the production change". Side observation recorded:
  citation_correctness/precision dipped slightly (0.6735→0.6327,
  0.6769→0.6071) — not among the four compared metrics; noted as an input for
  the future ADR, not a blocker.
- **Left for the owner:** the apply itself; the post-apply cold-start number
  (the runbook's procedure has a pending placeholder — the pre-flip ~50 s and
  the re-measure steps are recorded).

## Plan Change Log

## Review Triage Log

## Design Notes

- **Why the quota gets midnight, not the rate window:** a quota refusal is not a per-IP window event; its honest reset is the daily counter's UTC rollover. Both 429s stay honest; the widget distinguishes them by the stable `detail` string (pinned by tests).
- **Why the widget keys on `detail` text:** the error envelope strings are the contract surface the widget already renders; no new field is added, so the JSON schema cannot drift.
- **Why the comparison target is `156b5d1a` (owner, 2026-10-22):** `c6ced445` — the pointer in the task file — is the 2026-10-15 reference measured on the old corpus (291 chunks, 91-item dataset, 44 gate-eligible); a run on today's tree (dataset `a8bd69dc…`, 417 chunks, n=49) is comparable only to a reference measured on the identical corpus/index/dataset and the same judge, which is `156b5d1a`. The measurement note records the supersession and why, and states explicitly that the gemini comparison says nothing about the historical `c6ced445` gate line — the two are not a sequence.

## Verification

**Commands:**
- `ulimit -n 16384 && uv run pytest -q` — the full suite stays green (and `node tests/widget/index.test.mjs` runs inside it via the wrapper).
- `uv run pytest tests/test_guardrails_limits.py tests/test_guardrails_api.py tests/test_widget.py -q` — the matrix rows pass.
- `JANBOT_MODEL_SNAPSHOT=google/gemini-2.5-flash JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 uv run python -m janbot.eval --split val` — the part-4 run (run id recorded in the measurement note).
- `terraform -chdir=terraform validate && terraform -chdir=terraform plan -var image_tag=$(git rev-parse --short HEAD) -var registry_auth_file="$DOCKER_CONFIG/config.json"` — exactly the named changes, 0 destroy.
- Post-apply (owner): the cold-start re-measure per the runbook procedure; the number recorded in the runbook.
