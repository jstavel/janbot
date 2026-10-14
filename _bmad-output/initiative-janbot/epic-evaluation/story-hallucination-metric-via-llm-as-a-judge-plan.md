---
title: 'Hallucination metric via LLM-as-a-judge'
type: 'feature'
ticket: 5
created: '2026-10-14'
status: 'built'
baseline_revision: 'd24a62d'
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

**Problem:** retrieval and citation are now measured, but nothing scores whether an *answer* is faithful to the corpus or invents facts — the hallucination gap. An LLM-as-a-judge closes it.

**Approach:** a config-driven **judge model** (`JANBOT_JUDGE_MODEL`, default the locked snapshot, routed through OpenRouter) scores each item's answer against the golden `expected_answer` and returns a **verdict label** (+ a short rationale). The runner runs the judge per item (injected, so tests stub it), and a pure `hallucination` metric aggregates the verdicts; the per-question verdicts are recorded.

## Boundaries & Constraints

**Always:** the judge is **configuration only** (AD-5) — a stronger judge is a change to `JANBOT_JUDGE_MODEL`, not code; all model calls route through OpenRouter (one provider/invoice); the judge is injectable so the suite stays keyless.

**Never:** no judge output asserted byte-for-byte (the provider is not byte-deterministic); no change to `/chat` or the pipeline; no retrieval/citation re-scoring.

**Decision (2026-10-14):** the judge scores against the golden `expected_answer` only; it returns a verdict label plus a short rationale (the rationale is logged, never asserted).

**Decision (2026-10-14):** the runner runs the injected judge per item and a pure `hallucination` metric aggregates the verdicts (the metric never calls the model itself).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Faithful answer | judge verdict "faithful" | item passes; counted in the aggregate | No error |
| Hallucinated answer | judge verdict "hallucinated" | item fails; the verdict is recorded per item | Flagged in the run |
| Judge call fails | model/key error on one item | the item is recorded as unjudged, the run continues | Flagged, no abort |
| No judge configured | run without a judge | the metric is absent/0 over no eligible items | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/config.py:57` — add `JANBOT_JUDGE_MODEL` (default `config.model_snapshot`); `src/janbot/llm/__init__.py:59` — the `build_lm` seam builds the judge LM (`openrouter/<judge_model>`, `temperature=0`, seed).
- `src/janbot/eval/metrics.py:29` — `ItemOutcome`; add the judge verdict. Register `hallucination` over the verdicts.
- `src/janbot/eval/judge.py` (new) — the judge prompt + verdict parsing; an injectable callable.
- `src/janbot/eval/runner.py:77` — `run_eval` gains an optional `judge` callable; per item it stores the verdict (an error is caught, not aborted).
- `src/janbot/eval/__main__.py` — build the judge from config and pass it.
- `tests/test_eval_metrics.py`, `tests/test_eval_judge.py` (new) — a stub judge proves the metric.

## Tasks & Acceptance

**Execution:**
- [x] `src/janbot/config.py`, `src/janbot/llm/__init__.py` -- `JANBOT_JUDGE_MODEL` + a judge-LM builder from the same seam -- configuration-only judge selection.
- [x] `src/janbot/eval/judge.py` -- the judge: given an item's `expected_answer` and the model's answer, return a verdict label (+ rationale) -- the scoring.
- [x] `src/janbot/eval/metrics.py`, `src/janbot/eval/runner.py`, `src/janbot/eval/__main__.py` -- `ItemOutcome` verdict; the runner runs the judge (injected); `hallucination` metric + per-item verdicts; the CLI wires the judge from config -- the aggregate + records.
- [x] `tests/test_eval_judge.py`, `tests/test_eval_metrics.py` -- a stub judge: faithful / hallucinated / judge-failure / no-judge -- prove the matrix.

**Acceptance Criteria:**
- Given a stub judge returning "faithful" for an item, when the eval runs, then the item passes and the aggregate counts it.
- Given a stub judge returning "hallucinated", when the eval runs, then the item fails and the verdict is recorded.
- Given a judge call that raises on one item, when the eval runs, then that item is unjudged and the run continues.
- Given the eval run, when metrics are logged, then `hallucination` appears and each item's verdict is recorded.
- Given `JANBOT_JUDGE_MODEL` set, when the app/eval builds the judge, then it routes `openrouter/<judge_model>` through the same key.

## Implementation Notes

- `config.py`: `Config.judge_model` from `JANBOT_JUDGE_MODEL`, defaulting to the resolved `model_snapshot` (so a snapshot override carries through when the judge is unset).
- `llm/__init__.py`: `build_judge_lm(config, api_key, *, lm_factory)` reuses the `build_lm` seam — always `openrouter/<judge_model>`, `temperature=0`, `api_base` OpenRouter, the eval `seed`, and the same `api_key` when given. It never branches on model mode.
- `eval/judge.py` (new): `Verdict(label, rationale)`, `FAITHFUL`/`HALLUCINATED`, `parse_verdict` (fails closed on an unrecognized label), and `build_judge(lm)` wrapping a DSPy `Predict`. `dspy` is imported lazily inside `build_judge` so the eval import chain keeps the documented store-before-`dspy` order.
- `eval/metrics.py`: `ItemOutcome.judge_verdict` (None = unjudged) and a pure `hallucination` metric over judged items; registered globally, so it logs as `0.0` when nothing is judged.
- `eval/runner.py`: `run_eval(..., judge=...)` runs the injected judge per answered item; a judge that raises leaves the item unjudged, is recorded in `RunResult.judge_failures`, and never aborts the run. A program failure stays unjudged (no answer to judge).
- `eval/__main__.py`: builds the judge from config only when `OPENROUTER_API_KEY` is present (a keyless eval stays offline and unjudged); prints `judge:` lines; records `judge_model` in the MLflow run params.
- Docs: `README.md` config table gains `JANBOT_JUDGE_MODEL`; `CHANGELOG.md` gains the metric entry.

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 4 findings, all patched:
- the real keyed CLI crashes: `build_judge_lm(..., lm_factory=None)` overrides its own default and calls `None(**kwargs)` — **high / patch** — pass the factory only when provided.
- `parse_verdict` inverts negated verdicts ("not hallucinated", "no hallucination detected" → hallucinated) — **high / patch** — symmetric negation handling; never the opposite label.
- per-item verdicts live only in memory; a hallucinated item is not visible in the run — **medium / patch** — surface each judged item's verdict and distinguish "nothing judged" from "all hallucinated".
- `hallucination=0.0` conflates all-hallucinated with nothing-judged — **low / patch** — folded into the surfacing fix (judged count).

Review pass 2 (patches applied): the keyed CLI no longer passes a `None` factory; `parse_verdict` handles negation symmetrically and fails closed; the CLI prints `judged: N/M` and a `judge:` line per item.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_judge.py tests/test_eval_metrics.py` -- ran: 50 passed (stub judge, keyless).
- `uv run pytest -q` -- ran: 270 passed (full suite, including the runner's exact metric-dict assertions updated for the new registered metric).
- `OPENROUTER_API_KEY=... uv run python -m janbot.eval --dataset eval/golden_dataset.yaml` -- NOT run here (no key available); the equivalent wired path is proven keyless by `tests/test_eval_judge.py::test_cli_scores_with_an_injected_judge`, which asserts `hallucination: 1.0000`.
