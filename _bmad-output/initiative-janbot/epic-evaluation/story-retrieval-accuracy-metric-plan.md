---
title: 'Retrieval-accuracy metric'
type: 'feature'
ticket: 3
created: '2026-10-14'
status: done
baseline_revision: '827ce57f379eb56d65f576bfd060d6411289da00'
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

**Problem:** the eval measures whether an answer is *cited* correctly (entry 4) and whether it public-references soundly, but nothing measures whether the **retriever** actually fetched the golden item's expected source. The two questions are distinct: 5.3 asks "was the expected source *retrieved*?", 5.4 asks "did the answer *cite* it?" — and today only the cited half is observable.

**Approach:** expose the sources the pipeline retrieved for a question, carry them per item, and register a `retrieval_accuracy` metric — per-item, the golden `expected_sources` must be a subset of the retrieved sources; the aggregate is the fraction of items that pass. Report per-item misses (like the public-reference failures).

## Boundaries & Constraints

**Always:** measure the *retrieved* set, never the citations (that is entry 4); keep the `/chat` contract and behavior unchanged.

**Never:** no citation-correctness metric (entry 4); no judge (entry 5); no ingestion change.

**Decision (2026-10-14):** the retrieved set is exposed as an additive `ChatProgram` attribute (`last_retrieved_sources`) that the runner reads — truthful, no duplicate retrieval, accepting a small touch to the done `epic-rag-chat` module.

**Decision (2026-10-14):** per-item misses reuse the `reference_failures` pattern — a `retrieval_misses` list on `RunResult` plus a CLI line.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Expected source retrieved | golden item + a run that retrieved it | item passes; counted in the aggregate | No error |
| Expected source missed | retriever never returned it | item fails; the miss is reported per item | Flagged in the run |
| Item declined | the pipeline returned an insufficiency reply | accuracy still reflects what was retrieved | No error |
| No expected sources | a should-refuse item | the item is excluded (no retrieval claim) | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/pipeline/chat.py:112` — `ChatProgram.forward` computes the corpus-relative `sources` from the retrieved chunks; expose them (see Open Question 1).
- `src/janbot/eval/metrics.py:29` — `ItemOutcome`; add `retrieved_sources`. `:57` `registered_metrics`; the new metric registers here, and a `retrieval_misses(outcomes)` accessor mirrors `public_reference_failures`.
- `src/janbot/eval/runner.py:98` — the runner reads the program's retrieved sources into the outcome; `:110` carries the per-item misses out like `reference_failures`.
- `src/janbot/eval/__main__.py:97` — print a `reference:`-style line per retrieval miss.
- `tests/test_eval_metrics.py` (new) — the metric and misses.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/pipeline/chat.py` -- record the corpus-relative retrieved sources on the program for the last call (an additive observation seam) -- makes the retrieved set observable without changing the contract.
- [ ] `src/janbot/eval/metrics.py` -- add `ItemOutcome.retrieved_sources`; register `retrieval_accuracy` (expected subset of retrieved, aggregate fraction) and a `retrieval_misses` accessor -- the metric.
- [ ] `src/janbot/eval/runner.py`, `src/janbot/eval/__main__.py` -- capture the retrieved sources per item and report the misses -- per-item visibility.
- [ ] `tests/test_eval_metrics.py` -- retrieved / missed / declined / no-expected cases -- prove the matrix; `tests/test_chat.py` -- the program exposes the last retrieved sources.

**Acceptance Criteria:**
- Given a golden item whose expected sources were all retrieved, when the metric runs, then the item passes and the aggregate counts it.
- Given an item whose expected source was not retrieved, when the metric runs, then the item fails and the miss is named per item.
- Given an item with no expected sources, when the metric runs, then it is excluded from the aggregate.
- Given a run, when the metric is logged, then `retrieval_accuracy` appears in the MLflow run.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 7 findings:
- a call that raised before the sources were set leaves `last_retrieved_sources=[]`, conflating "not observed" with "retrieved nothing" and silently lowering accuracy — **medium / patch** — distinguish `None` (unobserved) from `[]` (retrieved nothing).
- the `ChatProgram` seam test cannot prove retrieval ≠ citations (the retrieved set equals the happy-path citations) — **medium / patch** — strengthen so a retrieved source the answer does not cite is what the seam exposes.
- `CHANGELOG.md` has no entry, unlike the sibling `public_references` metric — **low / patch** — add an `[Unreleased] > Added` line.
- the "no expected sources / should-refuse" matrix row is unreachable until the refusal item class (entry 13) allows source-less items — **low / defer** — recorded; entry 13 owns the dataset support.
- the seam is shared mutable state on the one program instance, racy if read while serving — **low / defer** — responses use a local; the eval reads sequentially.
- an all-excluded run logs `0.0`, indistinguishable from total failure — **low / defer** — pre-existing convention (matches `public_references`).
- "the test layer is never modified to accommodate an AI-core change" (a runner test's exact metric-dict assertions changed) — **false** — the modified test is the eval harness's own, and the change is eval-side, not an AI-core change; the README invariant governs the AI-core↔port-test boundary, not eval-internal tests.

Review pass 2 (patches applied):
- `last_retrieved_sources` now `None` until retrieval is observed (`[]` on empty retrieval) — unobserved no longer scores as a miss.
- the seam test now retrieves a source the answer does not cite, proving retrieval ≠ citations.
- `CHANGELOG.md` gains the `retrieval_accuracy` entry.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_metrics.py tests/test_chat.py` -- expected: green.
- `uv run python -m janbot.eval --dataset eval/golden_dataset.yaml` -- expected: `retrieval_accuracy` in the run.
