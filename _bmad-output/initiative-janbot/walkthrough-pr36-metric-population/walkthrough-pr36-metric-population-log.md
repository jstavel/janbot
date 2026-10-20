# Review log: PR #36 — metric population

Target: PR #36, branch `eval-5.22-metric-population`, commit `5519505`.

## 1 — Orientation / narrative — created

Session: unavailable · Timestamp: 2026-10-20T14:58:00+02:00

- Action: Read the plan intent, PR #36 description, and the changed surfaces; created the narrative and this log.
- Result: Narrative blocks 1–8 written; block 1 (Intent) is current and unvisited.
- Evidence: `_bmad-output/initiative-janbot/walkthrough-pr36-metric-population/walkthrough-pr36-metric-population.md`; plan `story-metric-population-inconsistency-errored-items-are-coverage-m-plan.md`.
- Open: human acceptance of each block.

## 2 — Intent — accepted

Session: unavailable · Timestamp: 2026-10-20T15:02:00+02:00

- Action: Presented the verbatim intent block.
- Result: Accepted by the reviewer.
- Evidence: narrative block 1.

## 3 — Broad strokes — accepted

Session: unavailable · Timestamp: 2026-10-20T15:05:00+02:00

- Action: Presented the four entry points.
- Result: Accepted by the reviewer.
- Evidence: narrative block 2.

## 4 — Claim-quality population — accepted

Session: unavailable · Timestamp: 2026-10-20T15:08:00+02:00

- Action: Presented the fixed in-corpus population and the citation/faithfulness predicates.
- Result: Accepted by the reviewer.
- Evidence: narrative block 3; metrics.py eligibility functions.

## 5 — Contract scope (retrieval exception) — fixed

Session: unavailable · Timestamp: 2026-10-20T15:20:00+02:00

- Action: Scoped the fixed-population sentence to claim-quality/gating metrics; named retrieval as the explicit exception; added a test pinning a hard-error-before-retrieval item as out of retrieval scope while the claim-quality metrics count and fail it.
- Result: Document and code agree; test passes. Commit `5417cad`.
- Evidence: `gate-rule.md` population contract; `tests/test_eval_metrics.py::test_a_hard_error_before_retrieval_is_out_of_scope_for_retrieval`.
- Open: none.

## 6 — Known-red full suite — recorded

Session: unavailable · Timestamp: 2026-10-20T15:21:00+02:00

- Action: Reproduced `ulimit -n 1024` → 21 failed / 493 passed in the three store test files with `chromadb.errors.InternalError: ... (code: 14) unable to open database file`; recorded it in `README.md` and `deferred-work.md`, and qualified the PR's test claim.
- Result: Known-red entry exists; no artifact claims an unqualified green. With `ulimit -n 16384` the suite is 515 passed. Commit `68574d1`.
- Evidence: `README.md` reproducibility note; `deferred-work.md` review-defers entry; `/tmp` run capture.
- Open: the store-test resource leak is deferred as its own slice.

## 7 — Diagnostics — accepted

Session: unavailable · Timestamp: 2026-10-20T15:28:00+02:00

- Action: Presented the reason breakdown.
- Result: Block 4 accepted by the reviewer.
- Evidence: narrative block 4.

## 8 — Known-red record — corrected

Session: unavailable · Timestamp: 2026-10-20T15:29:00+02:00

- Action: Replaced the unsupported "ordering/state interaction, not store logic" cause with cumulative fd usage (ordering is a symptom); updated 514 → 515 where the count refers to the post-`5417cad` suite; kept "unclosed Chroma clients" as an unproven hypothesis; recorded the one-off `retrieval_mmr` NameError as fixed, green on re-run, not known-red.
- Result: No artifact states a cause the evidence does not support; counts agree with the fresh 515-pass run. Commit pending.
- Evidence: README reproducibility note; deferred-work review-defers entry.
- Open: none.

## 9 — Optimizer faithful atom — fixed

Session: unavailable · Timestamp: 2026-10-20T15:40:00+02:00

- Action: `_judge_faithful` now returns not-faithful without a judge call for a decline (`status="insufficient"`) or an empty answer; added scalar-path tests for both. The compile-metric docstring records the exception.
- Result: The eval and optimizer layers cannot disagree about whether a non-answer is faithful. Commits `415c00a`, `a04d989`; counts refreshed to 517 passed with the raised limit, 21 failed / 496 passed at the low limit.
- Evidence: `src/janbot/eval/optimize.py:134`; `tests/test_eval_optimize.py::test_compile_metric_does_not_judge_a_non_answer_on_the_scalar_path` and `...empty_answer...`.
- Open: none.

## 10 — Refusal metrics + optimizer alignment — accepted

Session: unavailable · Timestamp: 2026-10-20T15:43:00+02:00

- Action: Presented refusal populations and the aligned optimizer atoms, including the newly guarded faithful atom.
- Result: Block 5 accepted by the reviewer.
- Evidence: narrative block 5; commits `415c00a`, `a04d989`.

## 11 — Reference re-registration — accepted

Session: unavailable · Timestamp: 2026-10-20T15:46:00+02:00

- Action: Presented the new reference, per-item identity and floors.
- Result: Block 6 accepted by the reviewer.
- Evidence: narrative block 6; `gate-rule.md`, `run-156b5d1a-output.txt`, epic registration.

## 12 — Tests — accepted

Session: unavailable · Timestamp: 2026-10-20T15:49:00+02:00

- Action: Presented the tests pinning the contract.
- Result: Block 7 accepted by the reviewer.
- Evidence: narrative block 7; metrics/runner/public-urls/optimize tests.

## 13 — Periphery — accepted; round closed

Session: unavailable · Timestamp: 2026-10-20T15:55:00+02:00

- Action: Presented the periphery; closed item 3 (decline vocabulary prose + named owner follow-up) and item 5 (triage log now records the independent review and its five later items). Marked all eight blocks done.
- Result: Round closed from the reviewer's side. Narrative and log committed as evidence (`0cf23d7`); follow-up docs commit pending.
- Evidence: narrative block 8; plan Review Triage Log and Follow-ups; `deferred-work.md`; `gate-rule.md` / epic item-41 vocabulary.
- Open: none.
