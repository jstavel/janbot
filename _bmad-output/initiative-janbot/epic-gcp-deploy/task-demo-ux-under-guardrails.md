# Task — make the public demo pleasant under its own guardrails

**Priority:** medium · **Type:** UX + config · **Scope:** the guardrail layer's
refusal path, the widget, Terraform env, and one *measurement* of an alternative
model. The `/chat` contract and the AI core do not change.

## Context (measured 2026-10-22, live service)

| Scenario | Measured |
|---|---|
| Cached question (49 baked entries) | 0.9 s |
| Fresh question, warm instance | 10.5 s |
| Cold start after idle (`minScale=0`) | ~50 s |
| Refusal (429) | 0.15 s |
| `openrouter/auto` direct (routed → `gpt-6-luna`) | 4.3 s |
| `openai/gpt-4o-mini-2024-07-18` direct | 2.2 s |
| `google/gemini-2.5-flash` direct | 0.9 s |
| `google/gemini-2.5-flash` through the app, local eval mode | 1.2–3.2 s |

Observed by the owner while trying the demo: every submit waits ~10 s, and a
burst of test traffic (12 requests from one address) produced a bare
`429: too many requests` on the page.

## Part 1 — the refusal should say what to do

**Problem.** A 429 renders as `429: too many requests`. It is accurate and
useless: no hint of how long. And the widget composes `status + ": " + detail`,
so the copy is the raw machine string.

**Do:**
- The guardrail refusal path sends `Retry-After` (seconds) on 429, computed from
  the actual rate window — the earliest moment the caller's window frees a slot,
  not a constant.
- The 503 store-unavailable path may carry `Retry-After` too, but only if the
  value is honest; otherwise omit it.
- The widget renders human copy for a refusal, and includes the wait when the
  header is present. Suggested copy: *"Too many questions from this address —
  try again in about N minutes."* Keep the existing behaviour for 413/422/5xx
  (the `{detail}` envelope), which are already readable.

**Done when:** a unit test asserts the 429 carries a `Retry-After` consistent
with the window (boundary: two calls inside one window → header decreases), the
`/chat` JSON schema is unchanged, and the widget shows the wait using a fake
fetch response (no network in the test).

## Part 2 — the rate limit is too tight for a shared address

**Problem.** 10 requests / 10 min is per client IP, and a corporate NAT shares
one IP — a whole office gets ten questions per window. For a portfolio demo that
is a false refusal far more often than it is protection.

**Do:** raise the deployed default to **20 / 10 min** (`var.rate_limit`), and
record in the runbook *why*: the daily quota (500 model calls) and cache are the
real cost guard; the per-IP window is anti-abuse, and anti-abuse at ten per
office is a UX defect.

**Done when:** the Terraform default is 20, `terraform plan` shows the env change
only, and the runbook states the reasoning plus the residual risk (raised limit =
more model calls per office before the quota bites).

**Non-goal:** do not invent IP-less identity (cookies/sessions). A public
endpoint without auth cannot reliably identify a caller, and pretending otherwise
would be worse than an honest IP limit.

## Part 3 — cold start should not be the first impression

**Do:** set `startup-cpu-boost` on the Cloud Run service (free, no cost impact).
Re-measure the cold-start path afterwards and record the number.

## Part 4 — `gemini-2.5-flash`: measure before believing

**Context.** `production` resolves to `openrouter/auto`, which routed to
`gpt-6-luna` (4.3 s) today; `eval` resolves to the pinned snapshot. So an
alternative model is testable **through configuration alone** in eval mode:
`JANBOT_MODEL_SNAPSHOT=google/gemini-2.5-flash`.

**Do:** run the golden-dataset evaluation in eval mode with that snapshot and
compare against the shipped baseline (`c6ced445`): faithfulness,
answer_coverage, refusal_pass_rate, spurious_refusal_rate. Anecdotal local run
answered correctly but cited `mta-and-antispam-operations.org` for "What is
JanBot?" — exactly the kind of citation noise the dataset must judge.

**Done when:** the comparison is recorded with the run id and the numbers, and
one of two conclusions is stated: *no regression → propose the production
change*, or *regression → do not change, and say which metric moved.*

**Non-goal:** do not change what production routes to in this task. That is a
behaviour change outside the measured baseline and needs its own decision (ADR
level, because production's `openrouter/auto` is a deliberate routing choice, not
an accident).

## Sequencing note

Part 1+2+3 are one small round and can ship together. Part 4 is a measurement,
not a change — it can run in parallel and produces a decision input, not a diff.
Streaming (SSE) is deliberately **not** in this task: it is the largest UX win but
touches a new public surface, CORS and the widget, and deserves its own story
with its own acceptance.
