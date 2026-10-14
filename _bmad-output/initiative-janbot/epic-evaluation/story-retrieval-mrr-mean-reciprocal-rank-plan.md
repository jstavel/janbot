---
title: 'Retrieval MRR (mean reciprocal rank)'
type: 'feature'
ticket: 15
created: '2026-10-14'
status: done
baseline_revision: '8ad9c6d'
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

**Problem:** `retrieval_accuracy` is binary — it cannot tell a source at rank 1 from rank 4, so it hides the item-5 finding (an expected source sat at rank 4 and `top_k=4` barely saved it). A rank-aware, judge-free signal is missing.

**Approach:** add `retrieval_mrr` — over the same eligible items as `retrieval_accuracy`, the mean of `1 / rank` of the first expected source found in the retrieved list (0 when none is retrieved). Data-level, no judge.

## Boundaries & Constraints

**Always:** the same eligibility and denominator as `retrieval_accuracy`; the retrieved list's order is the retrieval order.

**Never:** no judge, no compile/optimization change; no change to `retrieval_accuracy`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Expected source at rank 1 | retrieved list | item scores `1.0` | No error |
| Expected source at rank 4 | retrieved list | item scores `0.25` | No error |
| Expected source not retrieved | retrieved list | item scores `0.0` | No error |
| No expected sources / unobserved retrieval | item | excluded (same as `retrieval_accuracy`) | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/metrics.py:240` — `_retrieval_eligible` (reuse); `:250` `retrieval_accuracy` (the sibling); add `retrieval_mrr`; `:391` register it with `denominator=_retrieval_eligible`.
- `tests/test_eval_metrics.py` — the rank cases and eligibility.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/eval/metrics.py` -- add `retrieval_mrr` (mean reciprocal rank of the first expected source) and register it with `_retrieval_eligible` -- the metric.
- [ ] `tests/test_eval_metrics.py` -- rank 1 / rank 4 / not-retrieved / excluded -- prove the matrix.

**Acceptance Criteria:**
- Given an expected source retrieved at rank 1, when `retrieval_mrr` runs, then it contributes `1.0`.
- Given it retrieved at rank 4, when it runs, then it contributes `0.25`.
- Given it not retrieved, when it runs, then it contributes `0.0`.
- Given a run, when it is recorded, then `retrieval_mrr` appears with its `<metric>__n`.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Review Triage Log

Review pass 1 (quick, pinned) — 3 findings, all patched:
- `CHANGELOG.md` has no `retrieval_mrr` entry — **low / patch** — added.
- `retrieval_mrr` is not re-exported from `janbot/eval/__init__.py` (every sibling metric is) — **low / patch** — exported.
- the `tests/test_eval_metrics.py` module docstring under-describes the suite — **low / patch** — updated.

Review pass 2 (patches applied): docs and the package export match the new metric.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_metrics.py` -- expected: green.
