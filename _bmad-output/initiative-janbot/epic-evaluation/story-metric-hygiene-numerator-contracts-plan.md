---
title: 'Metric hygiene: numerator contracts (polarity, denominators, one eligibility)'
type: 'feature'
ticket: 16
created: '2026-10-14'
status: done
baseline_revision: '9260ed0'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** metrics record only a score, over different populations, so two runs' numbers are not safely comparable (a smaller `n` reads as "worse"); and a metric can register without any denominator at all. Polarity is implicit too.

**Approach:** make each metric declare its **denominator** and **polarity** at registration, record `<metric>__n` beside every score, and share the per-metric eligibility predicates. (The values themselves must not move.)

## Boundaries & Constraints

**Always:** `register_metric(name, metric, *, denominator)` — denominator keyword-only and required; a metric without one fails fast; counts are a separate `RunResult.counts`, never merged into `result.metrics`.

**Never:** no `higher_is_better` behavior beyond the flag; no change to metric values; no `retrieval_mrr` (entry 15), refusal metrics (entry 13), or `public_references` narrowing.

**Decision (2026-10-14):** `<metric>__n` is logged in `log_metrics` (numeric, charts with the score); the CLI prints `name: 0.5430 (n=35)`.

**Decision (2026-10-14, eligibility):** the shared eligibility also excludes a `status="insufficient"` response — `response is not None and response.status != "insufficient"` — defensively. It is a no-op today (the eval path's declines raise before returning, so a declined outcome is `response is None`), but it satisfies the shared-eligibility requirement and prepares entry 13. A metric and its **denominator share the same predicate** (single source), so `n` cannot drift from the metric's actual population.

**Decision (2026-10-14, registry shape):** `register_metric` records `(metric, denominator, higher_is_better)`; `registered_metrics()` keeps returning `name → callable` (unchanged for the runner and for `"x" in registered_metrics()`), and a new `metric_counts(outcomes)` exposes the denominators.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| A registered metric | any run | its score and its `<name>__n` both recorded | No error |
| Metric without a denominator | a `register_metric` call missing it | refused at registration | Error |
| Different populations | retrieval vs faithfulness | each `n` matches its own population | No error |
| Declined response | a hand-built `ChatResponse(status="insufficient", citations=[])` | excluded from citation_correctness and faithfulness | No error |
| Existing values | the current golden set | every metric value is unchanged | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/metrics.py:55` — `register_metric(name, metric, *, denominator, higher_is_better=True)`; store the triple; `registered_metrics()` stays name→callable. `:70` add `metric_counts`. `:75-313` — each metric gets a named eligibility predicate (shared with its denominator) and a denominator; the declined clause `response is not None and response.status != "insufficient"` joins the eligibility.
- `src/janbot/eval/__init__.py` — re-export `metric_counts` (and `registered_metrics` stays).
- `src/janbot/eval/runner.py:32` — `RunResult` gains `counts`; `:107` `_record` logs the `<metric>__n` counts beside the scores; `:148` the runner computes them.
- `src/janbot/eval/__main__.py:135` — the CLI prints `name: value (n=count)`.
- `tests/test_eval_metrics.py`, `tests/test_eval_runner.py` — the contract + an invariant that every registered metric has a `<name>__n`.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/eval/metrics.py` -- `register_metric(name, metric, *, denominator, higher_is_better=True)` (fail fast on a missing denominator); `metric_counts(outcomes)`; a named eligibility predicate **shared** with each metric's denominator; the declined clause `response is not None and response.status != "insufficient"` in the eligibility -- the contract.
- [ ] `src/janbot/eval/runner.py` -- compute counts, log `<metric>__n` in `log_metrics`, add `RunResult.counts` -- record them.
- [ ] `src/janbot/eval/__main__.py`, `src/janbot/eval/__init__.py` -- print `name: value (n=count)`; re-export `metric_counts` -- show them.
- [ ] `tests/test_eval_metrics.py` -- the denominator/polarity contract; **a hand-built `ChatResponse(status="insufficient", citations=[])` is excluded by citation_correctness and faithfulness**; an invariant that every registered metric has a `<name>__n` and declares a direction (faithfulness `higher_is_better=True`); existing metric-value tests stay green (values unchanged) -- prove it.
- [ ] `tests/test_eval_runner.py` -- extend **`run.data.metrics == {…}` (line ~159) additively with the six `__n`** (the proof of "<metric>__n beside the score"); **leave `result.metrics == {…}` (line ~132) scores-only** (the invariance oracle -- not weakened, not extended) -- pin the contract precisely.

**Acceptance Criteria:**
- Given a run, when it is recorded, then every metric has a matching `<name>__n` and each `n` equals that metric's own population; `result.metrics` stays scores-only while `run.data.metrics` carries the `__n` too.
- Given a `register_metric` call without a denominator, when it is made, then it fails fast.
- Given a hand-built `status="insufficient"` response, when citation_correctness and faithfulness run, then they exclude it.
- Given a registered metric, when the invariant runs, then it declares a direction and faithfulness is `higher_is_better=True`.
- Given the current golden set, when the suite runs, then every metric value is unchanged from before the refactor.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Review Triage Log

Review pass 1 (quick, pinned) — 3 findings, all patched:
- `citation_precision`'s docstring still describes the pre-change population and the "cites nothing contributes 0.0" case — **low / patch** — updated to the shared eligibility.
- `tests/test_eval_metrics.py` module docstring still says "a decline fails containment" (reversed) — **low / patch** — corrected.
- the `declined=True` branch of `_citation_outcome` is dead code after the change — **low / patch** — removed.

Review pass 2 (patches applied): docstrings match the exclusion semantics; the dead branch is gone.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_metrics.py tests/test_eval_runner.py` -- expected: green.

**Manual checks (if no CLI):** the full-run command (`python -m janbot.eval --dataset …`) is **hitl** — it needs a built index and a key, so it is not part of the keyless verification; a person runs it and confirms each metric prints `(n=…)`.
