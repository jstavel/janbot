---
title: 'Metric-population contract for non-answered items'
type: 'feature'
ticket: 22
created: '2026-10-20'
status: 'built'
baseline_revision: '1eeb890b03fae688e87026b7d0e1389b71bb1454'
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

**Problem:** An item that produces no ordinary answer (a hard error such as
`FabricatedCitation`, or an in-corpus decline) is counted as a miss by
`answer_coverage` but excluded from the `citation_correctness`/`faithfulness`
denominators. The same event lowers coverage and raises the quality rates, and
because θ and the ADR-010 output guard can move items out of those denominators,
a configuration change can "improve" citation by declining the items it would
have failed. This is an instrument defect, not a model defect.

**Approach:** Option **B** — one failure-inclusive population. Every metric has
a fixed nominal population; a non-answered item is a failure in every
claim-quality metric. Hard errors **and in-corpus declines** are failures.
Out-of-corpus declines remain correct behaviour and stay with the refusal
metrics. The "did not answer" vs "answered badly" distinction survives as a
reason breakdown reported beside the single population, not as a second
denominator.

**Decision (2026-10-20, owner):** B, scope = errors + in-corpus declines; keep
the full plan. Historical runs become incomparable; the reference is
re-registered under the frozen rule and the floors re-derived. Rationale: A
preserves pairwise comparability but leaves a false-accept path in the gate —
θ and the output guard can shrink the denominator while coverage is non-gating;
the common-item intersection protects a comparison, not a quoted number.

## Boundaries & Constraints

**Always:** measurement and documentation only — no change to the model,
retrieval, dataset, index, `/chat` contract or AI core. The current registered
reference is `5ed5d8d7` (guard on), not the ticket's older `4c0d848c`. Metric
names stay; every metric keeps a declared denominator and a recorded `__n`. The
contract is stated once. Any population that shrinks must be named in the
diagnostic breakdown — no score may be computed over a silently smaller
population. Gate comparisons stay on the common-item intersection (Amendment 2)
as a second guard.

**Never:** no silent metric-value change; no mid-comparison instrument change;
no removal of historical evidence; no change to `should_refuse` or the dataset;
no second denominator for a claim-quality metric; no new keyed run beyond the
single reference re-registration.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HARD ERROR | item raises (`FabricatedCitation`) | failure in coverage, citation_correctness, citation_precision, faithfulness, public_references; counted in `hard_error__n` | no special case outside the contract |
| IN-CORPUS DECLINE | `status=insufficient` on a non-refusal item | same failure-inclusive treatment; counted in `in_corpus_decline__n` | refusal metrics unchanged for `should_refuse` |
| OUT-OF-CORPUS DECLINE | `should_refuse` item declines | passes `refusal_pass_rate`; excluded from claim-quality metrics | correct behaviour, not a failure |
| UNJUDGED ANSWER | judge configured, no verdict | failure in faithfulness; counted in `judge_failure__n` | keyless run = no judge, faithfulness 0.0 over the nominal n |
| SINGLE POPULATION | any run | each claim-quality metric's `__n` is its nominal population | no nominal/observed split |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/metrics.py:145,190,202,371,421,462,478` — `_responded`,
  `_non_refusal_eligible`, `stub_metric` (coverage), `_citation_eligible`,
  `citation_correctness`, `_faithfulness_eligible`, `faithfulness`.
- `src/janbot/eval/metrics.py:530-548` — metric registration; refusal metrics'
  denominators (`_refusal_eligible`, `_in_corpus_eligible`).
- `tests/test_eval_metrics.py:243,409,445,476` — the tests pinning the old
  decline/error split; update to the new contract.
- `src/janbot/eval/runner.py:105-182,189-223` — `ItemOutcome.error`, `log_run`
  (metrics + `__n`, no per-item outcome artifact).
- `src/janbot/eval/__main__.py:105,171` — the CLI's metric printing and
  `judged: x/y` line; add the reason breakdown.
- `src/janbot/eval/optimize.py:117-132` — `_cited_ok`; its citation atom already
  treats a decline as a failure, so it matches B (docstring only).
- `_bmad-output/initiative-janbot/epic-evaluation/gate-rule.md` — reference,
  floors, comparison rule.
- `_bmad-output/initiative-janbot/epic-evaluation/epic-evaluation.md:156,170-177`
  — FINDING 1 and the reference-registration history.
- `run-5ed5d8d7-output.txt` — the current reference's per-item evidence.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/eval/metrics.py` -- make the claim-quality metrics
  failure-inclusive: citation eligibility = non-refusal + expected sources
  (drop `_responded`); a non-answer is a citation miss and precision 0.0;
  faithfulness eligibility = non-refusal, numerator = FAITHFUL verdicts, a
  missing verdict/non-answer is a failure; `refusal_pass_rate` population = all
  should-refuse items (error = fail); `spurious_refusal_rate` population = all
  non-refusal items (a decline counts; an error is not a decline) -- one
  denominator per metric.
- [ ] `src/janbot/eval/runner.py` + `src/janbot/eval/__main__.py` -- compute and
  print the reason breakdown (`hard_error__n`, `in_corpus_decline__n`,
  `judge_failure__n`, `non_answered__n`) beside the metrics, and log the counts
  in the MLflow run -- the diagnostic must survive the single denominator.
- [ ] `tests/test_eval_metrics.py` + `tests/test_eval_runner.py` -- replace the
  tests that pin the old exclusion with tests asserting the new populations and
  the reason counts -- prove the contract, not the implementation.
- [ ] `src/janbot/eval/optimize.py` -- align the `_cited_ok` docstring with the
  failure-inclusive citation contract (no behaviour change) -- keep the
  compiler atom honest.
- [ ] `_bmad-output/initiative-janbot/epic-evaluation/gate-rule.md` -- state the
  contract once (populations, failure classes, diagnostics, out-of-corpus
  exception), mark every pre-change run incomparable, and replace the reference
  and floors after the keyed run -- the gate rule is the single source.
- [ ] `_bmad-output/initiative-janbot/epic-evaluation/epic-evaluation.md` --
  close FINDING 1 with the decision and rationale; record the reference
  re-registration and the incomparability note -- the defect becomes evidence.
- [ ] Re-measure the reference: run the pinned val config with a real key
  (`model_mode=eval`, locked snapshot, hybrid, chunks, k=4, θ=0.26, judge
  `claude-haiku-4.5`, `output_guard=on`, `split=val`); capture
  `run-<id>-output.txt`; verify the per-item answers/citations/verdicts match
  `5ed5d8d7` (only aggregates change); register the new run and re-derive the
  floors -- one keyed run, bounded and attributable.

**Acceptance Criteria:**
- Given an errored or in-corpus-declined item, when any claim-quality metric
  runs, then the item is in that metric's denominator and counts as a failure.
- Given any run, when metrics are recorded, then each claim-quality `__n` is its
  nominal population and the reason breakdown names every non-answered item.
- Given an out-of-corpus decline, when the refusal metrics run, then it passes
  `refusal_pass_rate` and is absent from the claim-quality populations.
- Given the re-measured reference, when the gate rule is read, then the new
  reference, the re-derived floors and the incomparability list are present.
- Given `uv run pytest -q tests/test_eval_metrics.py tests/test_eval_runner.py`,
  then it is green.
- Given the keyed reference run, then its per-item answers/citations/verdicts
  match `5ed5d8d7` and only the aggregates and counts differ.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Quick review, 2026-10-20. Six findings; all verified and patched. No loopback.

- **public_references passed a non-answered URL-free item — medium, patch (fixed).** Verified at `metrics.py:225`: `_item_reference_failures` used `""` for a missing response, so an item whose expected answer names no URL passed. Fixed by failing any non-answered in-corpus item; test updated. Consequence: the contract's "non-answer is a failure in every claim-quality metric" now holds, and the reference's `public_references` is 48/49.
- **"faithfulness cannot accept" was false — medium, patch (fixed).** Verified: 45/49 leaves four non-faithful items; a 3-item gain = 0.0612 exceeds the 0.0587 floor. The old claim was an artifact of the conditional population and contradicted the symmetric-target table. Fixed to **accept ≥3 / regress ≤2** in `gate-rule.md`, the epic and the plan's design note.
- **common-item intersection guard dropped from the active rule — low, patch (fixed).** Verified against the plan's Always constraint; the new rule stated only per-item identity. Restored the comparison sentence in `gate-rule.md`.
- **reference artifact lacked final `answer:` lines — low, patch (fixed).** Verified the first artifact was captured without `--answers`. Re-ran the reference under the patched code with `--answers`; all 59 final answers plus raw answers, citations, normalized and guard lines are byte-identical to `5ed5d8d7`. New reference `156b5d1a`.
- **a non-answered item could pass through a stray FAITHFUL verdict — low, patch (fixed).** Verified `faithfulness` checked only the label. Added `_responded` to the pass condition and a regression test; the runner already prevents the state, so this is contract hardening.
- **retrieval population wording incomplete — low, patch (fixed).** Verified `_retrieval_eligible` also requires expected sources. Corrected the gate-rule sentence.


## Design Notes

- **Why B (owner):** θ and ADR-010's guard are live configuration knobs. Under A
  they can remove items from the citation/faithfulness denominators while
  coverage is non-gating, so citation can improve by declining the items it
  would have failed. The common-item intersection protects pairwise comparisons,
  not the number a report quotes.
- **Impact at `5ed5d8d7`:** 49 non-refusal items, 48 answered, 1 in-corpus
  decline, 0 hard errors. Failure-inclusive gives citation 33/49 = 0.6735 and
  faithfulness 45/49 = 0.9184; citation keeps accept ≥5 / regress ≤4, while
  faithfulness **can accept with ≥3 items up** (3/49 = 0.0612 > the 0.0587 floor)
  and regresses ≤2. The old "cannot accept" claim was an artifact of the
  conditional population.
- **Affordability:** one keyed val run plus a floor re-derivation. The project
  has re-baselined twice (`4c0d848c → 5ed5d8d7`); the pre-registered principle
  is contract-independent. The reference run is the evidence, not a new
  comparison.
- **Diagnostics, not denominators:** hard error / in-corpus decline / judge
  failure are reported as a reason breakdown beside one population. The
  information survives; the comparability hazard does not.
- **Keyless mode:** with no judge, faithfulness stays 0.0 over the nominal
  population; the diagnostic `judge_failure__n` carries the explanation. Keyless
  runs are not gate runs.
- **Recompute limit:** `log_run` stores metrics and `__n`, not per-item
  outcomes, so the old reference cannot be recomputed; a single keyed run is
  required. The per-item comparison to `5ed5d8d7` is the determinism check.

## Implementation Notes

- Review patch (2026-10-20): `public_references` now fails a non-answered in-corpus
  item even when its expected answer names no URL; `faithfulness` requires an
  ordinary answer before a `FAITHFUL` verdict can pass; the gate rule's
  faithfulness floor was corrected to **accept ≥3 / regress ≤2** (the "cannot
  accept" claim was false under the fixed population); the common-item
  intersection guard and the retrieval population wording were restored. The
  reference was re-run under the patched code with `--answers`: run
  `156b5d1a76694867bd92e7a03feda76b`, `public_references` 0.9796 (48/49), all
  per-item answer/citation/verdict lines byte-identical to `5ed5d8d7`.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_metrics.py tests/test_eval_runner.py` --
  expected: green.
- `JANBOT_MODEL_MODE=eval JANBOT_RETRIEVAL_MODE=hybrid
  JANBOT_RETRIEVAL_WINDOW=chunks JANBOT_TOP_K=4
  JANBOT_RELEVANCE_THRESHOLD=0.26 JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5
  JANBOT_OUTPUT_GUARD=on uv run python -m janbot.eval --split val` -- expected:
  a new MLflow run under the new contract; capture its output.
- `grep -n "population contract\|incomparable\|<new-run>" gate-rule.md
  epic-evaluation.md` -- expected: the contract, the incomparability list and the
  new reference are named once.

**Manual checks (if no CLI):**
- Compare the new run's per-item `citation:`/`judge:`/`failed:`/`decline:` lines
  with `run-5ed5d8d7-output.txt`; they must match item by item. Inspect the new
  `__n` values: claim-quality metrics nominal, refusal metrics fixed.
