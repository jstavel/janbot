---
title: 'Citation-correctness metric'
type: 'feature'
ticket: 4
created: '2026-10-14'
status: 'built'
baseline_revision: 'ecada94'
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

**Problem:** nothing measures whether an answer *cites* the golden item's expected source. The pipeline already refuses a citation outside the retrieved set, so precision over the corpus is structurally enforced — what is unmeasured is **containment**: did the answer cite the sources it should have?

**Approach:** a `citation_correctness` metric over the citations already in `ChatResponse` — per item, the golden `expected_sources` must be a subset of the cited sources (containment/recall); the aggregate is the fraction of items that pass. A **retrieved-but-unexpected** source is **not** an error: record precision (cited sources that are expected) as a separate, informational count. Report per-item misses.

## Boundaries & Constraints

**Always:** score **containment** (`expected ⊆ cited`), never exact-set equality — a legitimately retrieved related source must not count as a citation error (the owner's 2026-10-14 ruling).

**Never:** no retrieval-accuracy metric (entry 3); no judge (entry 5); no contract change.

**Decision (2026-10-14):** precision is a `citation_precision` aggregate metric (a float), consistent with the other metrics; per-item `citation:` lines carry the diagnostic detail.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Expected all cited | answer cites every expected source | item passes; counted in the aggregate | No error |
| Expected source not cited | answer omits one | item fails; the miss is named per item | Flagged in the run |
| Extra expected-adjacent source cited | answer cites a related, retrieved source | not an error; lowers precision only | Informational |
| Decline / no citations | insufficient reply | the item fails containment (expected not cited) | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/metrics.py:29` — `ItemOutcome` carries the `ChatResponse` (its `citations`); the metric reads them. Register `citation_correctness` and a `citation_misses` accessor (the `public_reference_failures` pattern), plus `citation_precision`.
- `src/janbot/eval/runner.py:110` — carry the per-item misses out like `reference_failures`/`retrieval_misses`.
- `src/janbot/eval/__main__.py:97` — print a `citation:` line per miss.
- `src/janbot/eval/__init__.py` — export the new names.
- `tests/test_eval_metrics.py` — the metric, misses, precision.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/eval/metrics.py` -- register `citation_correctness` (expected ⊆ cited, aggregate fraction), `citation_precision` (expected-share of cited, aggregate), and a `citation_misses` accessor -- the containment contract, precision kept separate.
- [ ] `src/janbot/eval/runner.py`, `src/janbot/eval/__main__.py` -- carry and print the per-item citation misses -- per-item visibility.
- [ ] `tests/test_eval_metrics.py` -- contained / missed / extra-source (precision only) / decline cases -- prove the matrix.

**Acceptance Criteria:**
- Given an answer that cites every expected source, when the metric runs, then the item passes and the aggregate counts it.
- Given an answer missing an expected source, when the metric runs, then the item fails and the miss is named per item.
- Given an answer citing a retrieved-but-unexpected source, when the metric runs, then the item still passes and only precision drops.
- Given a run, when the metrics are logged, then `citation_correctness` and `citation_precision` appear in the MLflow run.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 2 findings, both patched:
- `citation_correctness` counted a crashed item (`response is None`) as a claim-making item in the denominator and a miss — **medium / patch** — exclude an unobserved response from the denominator (matching `retrieval_accuracy`); a valid decline is still a claim-making item that fails containment.
- `citation_precision`'s population diverged from `citation_correctness` (it skipped no-citation items), so it could read `1.0` while correctness read `0.0` — **medium / patch** — precision now averages the same eligible items, an item citing nothing contributing `0.0`.

Review pass 2 (patches applied): a crashed item is excluded from both metrics' denominator (a valid decline stays eligible and fails containment); precision and correctness now share one population.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_metrics.py` -- expected: green.
- `uv run python -m janbot.eval --dataset eval/golden_dataset.yaml` -- expected: `citation_correctness` and `citation_precision` in the run.
