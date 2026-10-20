# Walkthrough — PR #36 (story 5.22)

Target: PR #36, branch `eval-5.22-metric-population`, commit `5519505`.
Current block: **walkthrough complete** (all blocks done).

## 1. Intent — [x] done

Pasted verbatim from the plan's frozen intent.

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

## 2. Broad strokes — [x] done

The change redefines the measurement population of the eval metrics and then
re-registers the reference under that definition. Open these four first:

- [metrics.py](../../../src/janbot/eval/metrics.py) — the eligibility predicates and metric functions; the contract lives here.
- [runner.py](../../../src/janbot/eval/runner.py) — records the metric counts and the diagnostic reason counts in MLflow.
- [gate-rule.md](../epic-evaluation/gate-rule.md) — the single written contract, the new reference and the re-derived floors.
- [epic-evaluation.md](../epic-evaluation/epic-evaluation.md) — FINDING 1 closed and the reference registration recorded.

## 3. Slice — claim-quality population — [x] done

The five claim-quality metrics now share one fixed in-corpus population. A hard
error or an in-corpus decline stays in the denominator and fails, rather than
leaving the population. The citation metrics additionally require expected
sources; a non-answer is a citation miss and precision 0.0.

- [metrics.py](../../../src/janbot/eval/metrics.py) — `_citation_eligible`, `citation_correctness`, `citation_precision`, `_faithfulness_eligible`, `faithfulness`, `_non_refusal_eligible`.
- [metrics.py](../../../src/janbot/eval/metrics.py) — `public_references` now fails a non-answered in-corpus item even when its expected answer names no URL.

## 4. Slice — diagnostics — [x] done

The reason breakdown replaces the second denominator. `reason_counts` reports
hard errors, in-corpus declines, judge failures and their sum; the runner logs
them beside the metric counts and the CLI prints them.

- [metrics.py](../../../src/janbot/eval/metrics.py) — `reason_counts`.
- [runner.py](../../../src/janbot/eval/runner.py) — `RunResult.reason_counts` and `log_run`.
- [__main__.py](../../../src/janbot/eval/__main__.py) — prints the breakdown.

## 5. Slice — refusal metrics and optimizer alignment — [x] done

`refusal_pass_rate` now covers every should-refuse item (an error fails);
`spurious_refusal_rate` covers every in-corpus item (a decline counts, an error
does not). Both optimizer atoms now agree with the eval: the citation atom is
documented against the failure-inclusive contract, and the faithful atom never
judges a non-answer (a decline or empty answer is not faithful).

- [metrics.py](../../../src/janbot/eval/metrics.py) — `_refusal_eligible`, `_non_refusal_eligible`, registration.
- [optimize.py](../../../src/janbot/eval/optimize.py) — `_cited_ok` docstring.

## 6. Slice — reference re-registration — [x] done

The reference is re-registered as `156b5d1a` under the frozen rule. The per-item
answers, citations, verdicts and guard actions are byte-identical to `5ed5d8d7`;
the one intentional aggregate change is `public_references` 48/49. Floors:
citation accept ≥5 / regress ≤4; faithfulness accept ≥3 / regress ≤2.

- [gate-rule.md](../epic-evaluation/gate-rule.md) — contract, reference, floors, incomparability list.
- [run-156b5d1a-output.txt](../epic-evaluation/run-156b5d1a-output.txt) — the reference artifact.
- [epic-evaluation.md](../epic-evaluation/epic-evaluation.md) — FINDING 1 closure and the registration note.

## 7. Slice — tests — [x] done

The tests now pin the fixed population: declined/errored items fail, counts stay
nominal, the reason breakdown is exact, and a non-answer cannot pass through a
stray `FAITHFUL` verdict.

- [test_eval_metrics.py](../../../tests/test_eval_metrics.py) — population, counts, diagnostics.
- [test_eval_runner.py](../../../tests/test_eval_runner.py) — recorded counts and reasons.
- [test_eval_public_urls.py](../../../tests/test_eval_public_urls.py) — the non-answered URL-free failure.

## 8. Periphery — [x] done

- [plan](../epic-evaluation/story-metric-population-inconsistency-errored-items-are-coverage-m-plan.md) — the build record and review triage.
- No model, retrieval, dataset, index, `/chat` or AI-core change.
