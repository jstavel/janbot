---
title: 'Multi-objective compile metric (citations + faithfulness)'
type: 'feature'
ticket: 14
created: '2026-10-15'
status: done
baseline_revision: 'adb95dd'
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

**Problem:** the compile objective was citation-only, so it bought citation coverage at the cost of faithfulness — the Goodhart trade entry 8 exposed and entry 9 would have deepened.

**Approach:** make the objective multi-objective. Objective `score = w_c·cited_ok + w_f·faithful` (default `w_c = w_f = 0.5`); a demo is accepted only when `cited_ok AND faithful` (so a citation-only win is not bootstrapped); short-circuit to `False` without a judge call when `cited_ok` is false (keeps it near-free); record the weights, the demo count, and the `(cited_ok, faithful)` pair per item. Re-compile over the **train** split and evaluate on **val**, then judge against the pre-registered gate rule.

## Boundaries & Constraints

**Always:** only **program-controlled** terms in the objective (`retrieval_accuracy`, `answer_coverage` do not belong); the teacher is the locked snapshot; the judge is the eval judge, injected (tests stub it); the gate rule (`gate-rule.md`) is fixed and not retuned.

**Never:** no MIPROv2 (entry 9); no dataset or gate-rule change; no `/chat` change.

**Decision (2026-10-15):** weights default `w_c = w_f = 0.5`, recorded in the compile hyperparams; the compile records the per-item `(cited_ok, faithful)` pairs as an MLflow artifact (for a future Pareto/GEPA objective).

**Decision (2026-10-15, Q1 — short-circuit):** the no-judge-call short-circuit applies to the **demo path only** (`trace != None`). The scalar path cannot short-circuit without distorting the signal — with `cited_ok = false` the score is `w_f·faithful ∈ [0, 0.5]`, unknowable without a judge call; returning `0` underestimates a faithful-but-uncited answer, returning `w_f` overestimates it, and MIPROv2 ranks by score. The scalar-path decision is **deferred to `5.9`** with this reasoning on record; the scalar branch stays (stub-tested) but unexercised until 5.9.

**Decision (2026-10-15, Q2 — pairs artifact):** `[{index, question, cited_ok, faithful}]` as an MLflow artifact beside the compiled program, keyed on the dataset **index** (stable) with the question for readability. `faithful` is **`null`** when the demo path short-circuited (no judge call by design) — documented, so a later Pareto read does not mistake null for false. The val-side pairs are complete (the eval judges every answered item; no short-circuit there).

**Decision (2026-10-15, B2 — judge failure):** fail-closed — a judge error rejects the demo (`cited_ok AND faithful` is false) and records the failure (item `judged=False`). Note this differs by design from the eval harness, which leaves a judge-failed item **unjudged** and excludes it from the denominator; the compile rejects, because an unjudgeable candidate must not become a demo.

**Decision (2026-10-15, B3):** the compile hyperparams record the **judge model id**, so the faithful term is reproducible.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Demo bootstrap | `trace != None`, cites + faithful | the demo is accepted (metric truthy) | No error |
| Citation-only win | `trace != None`, cites but not faithful | the demo is **rejected** (AND) | No judge hedge |
| No citation | `trace != None`, `cited_ok` false | `False` without a judge call (short-circuit) | No error |
| Judge fails | `trace != None`, cited but judge raises | the demo is rejected; the failure is recorded | Recorded (fail-closed) |
| MIPROv2 scalar | `trace is None` | `w_c·cited_ok + w_f·faithful` (continuous) | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/optimize.py` — `compile_metric` becomes a factory `make_compile_metric(judge, *, w_c, w_f)` (the AND/scalar path by `trace`); the compile records weights + demo count + the pairs artifact; the CLI builds and injects the judge (over `--split train`).
- `src/janbot/eval/metrics.py` — reuse the existing per-item atoms (`cited_ok` via `citation_misses`/expected⊆cited; `faithful` via the judge verdict); no new metric.
- `src/janbot/eval/judge.py` — reused for the `faithful` term.
- `tests/test_eval_optimize.py` — a stub judge proves the AND, the scalar, and the short-circuit.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/eval/optimize.py` -- `make_compile_metric(judge, *, w_c=0.5, w_f=0.5)`; AND when `trace != None`, scalar otherwise; short-circuit without a judge call when `cited_ok` is false; judge failure fails closed; record weights + **judge model id** + demo count + the pairs artifact (`faithful` null on short-circuit) -- the multi-objective stage.
- [ ] `src/janbot/eval/optimize.py` -- build the judge from config (as the eval CLI does) and inject it; compile over `--split train` -- the runner.
- [ ] `tests/test_eval_optimize.py` -- a stub judge: citation-and-faithful accepted, citation-only rejected, no-citation short-circuits, judge-failure rejects, scalar = `w_c·cited + w_f·faithful` -- prove the matrix.
- [ ] run the compile over train, then the val eval **with `JANBOT_PROGRAM_PATH` set to the compiled output** (hitl: key + index), and judge against `gate-rule.md` -- the result (without the path it is baseline-vs-baseline and reads "no decision" vacuously).

**Acceptance Criteria:**
- Given a candidate that cites but is judged not faithful, when the compile metric runs with `trace != None`, then it is rejected.
- Given a candidate with no citation, when the metric runs, then it returns `False` with no judge call.
- Given `trace is None`, when the metric runs, then it returns `w_c·cited_ok + w_f·faithful`.
- Given the compile, when recorded, then the weights, demo count, and the `(cited_ok, faithful)` pairs are logged.
- Given the val re-run, when compared to `e635c2bf` under `gate-rule.md`, then a verdict (accept / reject / no decision) is recorded.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Review Triage Log

Review pass 1 (quick, pinned) — 8 findings, 6 patched / 1 expected / 1 deferred:
- the pairs artifact is only the bootstrapped prefix (BootstrapFewShot stops after the demo count), not the per-item map Q2 describes — **medium / patch** — add a full pass over the train split after compiling.
- `judge_model` is recorded even when no judge ran (keyless), undermining B3 — **medium / patch** — the compile requires a judge (fail fast without one).
- `faithful: null` has two causes (short-circuit vs no-judge), only one documented — **medium / patch** — distinguish them.
- `_cited_ok` diverges from the eval citation atom on declines — **low / patch** — reuse the eval eligibility (exclude `status="insufficient"`).
- the B3 test asserts a param already logged by `run_params`, so it cannot detect a regression — **low / patch** — assert the compile hyperparam/artifact.
- B2's rationale ("consistent with the eval harness") misstates it (the compile rejects on a judge error; the eval leaves the item unjudged) — **low / patch** — correct the wording.
- no val verdict — **expected** — the HITL gate step run separately.
- `_record` is last-write-wins if the metric runs >1x per index — **low / defer** — inert at `max_rounds=1`.

Review pass 2 (patches applied): the pairs map is complete; a keyless compile fails fast; null is unambiguous; the citation atom matches the harness; the B3 test is real.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_optimize.py` -- expected: green (stub judge, keyless).
- `OPENROUTER_API_KEY=… uv run python -m janbot.eval.optimize --dataset eval/golden_dataset.yaml --split train --out eval/compiled_fewshot.json` then `JANBOT_PROGRAM_PATH=eval/compiled_fewshot.json OPENROUTER_API_KEY=… uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` (hitl) -- the val run **must** load the compiled program (else baseline-vs-baseline), then judge against `gate-rule.md`.
