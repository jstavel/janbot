---
title: 'Reject non-finite temperature'
type: 'bugfix'
ticket: ''
created: '2026-10-13'
status: 'built'
baseline_revision: 'c5f14ee23e2271488d3559ca8f98dca3a99f371a'
route: 'oneshot'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `JANBOT_TEMPERATURE` is parsed with `float()` only (`src/janbot/config.py:115-124`), so `"nan"`, `"inf"`, and `"-inf"` are accepted as valid (verified: `load_config({'JANBOT_TEMPERATURE':'nan'})` yields `nan`). The value flows into the LM kwargs in *both* model modes (`src/janbot/llm/__init__.py:63-66`), silently voiding the story-3.5 eval-determinism pin — the exact failure 3.5 exists to prevent — and can only fail at request time inside dspy/litellm, outside the `/chat` envelope mapping. Recorded in the epic-rag-chat retrospective.

**Approach:** reject a non-finite temperature at config load with a `ValueError` naming `JANBOT_TEMPERATURE` (a `math.isfinite` check beside the existing parse), and document the finite requirement. Tests cover `nan`/`inf`/`-inf`.

## Boundaries & Constraints

**Always:**
- A non-finite `JANBOT_TEMPERATURE` fails fast at `load_config` with a `ValueError` naming the variable; the message is actionable.
- Blank/unset still takes the documented default `0.0`; a finite value (e.g. `0.7`) still parses.
- The failure surfaces at config load, never at request time.

**Never:**
- No change to `llm/`, `pipeline/`, `store/`, or the contract; no new env var or config field.
- No change to the existing "not a number" behaviour or message.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| EDGE | `JANBOT_TEMPERATURE` = `nan`/`inf`/`-inf` | fail fast at load | `ValueError` naming the var |
| HAPPY | `JANBOT_TEMPERATURE` = `0.7` | parsed to `0.7` | No error |
| EDGE | blank/unset | default `0.0` | No error |
| EDGE | `1.2x` | fail fast at load | `ValueError` (unchanged wording) |

</frozen-after-approval>

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (134 baseline + new finite rows)

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: `src/janbot/config.py` — added `import math` and, after the float parse, a `math.isfinite` check raising `ValueError` naming `JANBOT_TEMPERATURE`; the module docstring and the README row now say "finite number". `tests/test_config.py` adds `test_non_finite_temperature_raises` (nan/inf/-inf/Infinity) and extends the non-numeric rows with `1.2x`.
- Verification: `uv run pytest -q` → 138 passed.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 0 medium / 2 low / 0 false / 0 maybe-false.** All routed to patch.
- **Plan omitted `## Implementation Notes`** — **verdict: low**. **route: patch** — section added.
- **The `1.2x` matrix row had no dedicated test** — **verdict: low**. Verified the behaviour is correct; **route: patch** — `1.2x` added to the non-numeric parametrization.

