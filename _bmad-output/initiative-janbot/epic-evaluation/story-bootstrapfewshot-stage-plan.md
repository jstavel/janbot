---
title: 'BootstrapFewShot stage'
type: 'feature'
ticket: 8
created: '2026-10-14'
status: 'built'
baseline_revision: 'c137a72'
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

**Problem:** entry 7 recorded the baseline (retrieval 0.78, citation 0.77, faithfulness 0.66) and ruled BootstrapFewShot **needed**. The compiled program is the durable asset this stage produces.

**Approach:** compile the DSPy program with `dspy.BootstrapFewShot` over the golden dataset against a deterministic metric, **persist** the compiled program (a file plus an MLflow artifact), and let the eval run the compiled program so a recorded run shows its metrics against the baseline's.

## Boundaries & Constraints

**Always:** the compiled program is pinned by config (a program path), so production/eval load it without recompiling (the entry-7 decision); the compile is recorded with its config; a skip stays a recorded decision.

**Never:** no MIPROv2 (entry 9); no change to `/chat` behavior; no ingestion change.

**Decision (2026-10-14):** the compile metric is a deterministic "answers and cites all expected sources" signal (no judge cost).

**Decision (2026-10-14):** the teacher LM is the locked snapshot (cheap, deterministic).

**Decision (2026-10-14):** the compiled program is pinned by `JANBOT_PROGRAM_PATH` and logged as an MLflow artifact; the eval runs the compiled program when the path exists.

**Decision (2026-10-14):** the compile is run in this session (BootstrapFewShot is the near-free stage).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Compile runs | the golden trainset + the metric | a compiled program saved and logged as an artifact | No error |
| Eval with a compiled program | `JANBOT_PROGRAM_PATH` set + the file present | the run scores the compiled program; a `program` param distinguishes it | No error |
| Eval without a program path | no path | the baseline program runs (unchanged) | No error |
| Compile finds no demos | the metric bootstraps nothing | the compiled program equals the baseline; the run records it | Recorded, not an error |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/optimize.py` (new) — `trainset_from(items)`, `compile_fewshot(program, trainset, metric, *, teacher)`, `save_program`/`load_program` (dspy JSON), and a `python -m janbot.eval.optimize` CLI that compiles, saves, and logs the artifact.
- `src/janbot/config.py` — an optional `JANBOT_PROGRAM_PATH`.
- `src/janbot/api/main.py:90` — when the configured program path exists, load the compiled program instead of the freshly built one.
- `src/janbot/eval/__main__.py:39` — `run_params` gains a `program` marker (`baseline` / `fewshot:<sha>`), so runs compare.
- `tests/test_eval_optimize.py` (new) — trainset, save/load round-trip, and a `DummyLM`-driven compile.

## Tasks & Acceptance

**Execution:**
- [x] `src/janbot/eval/optimize.py` -- the trainset, the deterministic compile metric, `compile_fewshot`, save/load, and the CLI -- the stage.
- [x] `src/janbot/config.py`, `src/janbot/api/main.py` -- `JANBOT_PROGRAM_PATH` + load the compiled program when present -- pin it by config.
- [x] `src/janbot/eval/__main__.py` -- a `program` param on the run -- comparison visibility.
- [x] `tests/test_eval_optimize.py` -- trainset + save/load + a keyless compile -- prove it.

**Acceptance Criteria:**
- Given the golden dataset, when `compile_fewshot` runs with a stub LM, then a program is produced and saved, and `load_program` restores it.
- Given a compiled program path, when the eval runs, then the recorded run carries a `program` marker and its metrics sit beside the baseline's.
- Given no program path, when the eval runs, then the baseline program is unchanged.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 9 findings:
- `create_app` imports `janbot.eval.optimize` at top, pulling MLflow + the eval layer into the production path (and a cycle) — **medium / patch** — lazy-load the program through an mlflow-free helper.
- a set-but-missing `JANBOT_PROGRAM_PATH` silently falls back to baseline — **medium / patch** — fail fast, naming the path.
- `compile_fewshot`'s `teacher` argument is a no-op when the program has an LM — **medium / patch** — drop it or make it take effect; fix the docstring.
- default `max_labeled_demos=16` makes the "no demos ⇒ baseline" case false and pins inert, field-mismatched demos (embedding golden expected answers) — **medium / patch** — default labeled demos to 0.
- README/CHANGELOG omit `JANBOT_PROGRAM_PATH` and the stage — **low / patch** — document.
- `record_compile` logs no compile config / demo count — **low / patch** — log the hyperparameters + demo count.
- `load_program` docstring wrongly claims LMs are not saved — **low / patch** — fix.
- "Never: no change to `/chat` behavior" vs loading the pinned program in production — **resolved by the existing decision** — the pin is a deliberate, config-driven change (the Never governs the baseline path); no code change.
- `BootstrapFewShot` shares the `_store` copy (a benign warning) — **low / defer** — harmless with the read-only store; the compiled program is loaded into a fresh program.

Review pass 2 (patches applied): the production import path stays MLflow-free; a bad program path fails closed; the compile records its config + demo count; docs updated.

Recorded result (re-compiled with `max_labeled_demos=0`): the compiled program bootstraps **4 demos**; against the baseline (`9d2f0f96`) the compiled run (`4e315484`) shows citation_correctness 0.800 vs 0.771, citation_precision 0.738 vs 0.700, retrieval equal at 0.778, hallucination 0.600 vs 0.657 — citation coverage improved, faithfulness slightly lower (the deterministic compile metric does not guard faithfulness).

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_optimize.py` -- expected: green (stub LM, keyless).
- `OPENROUTER_API_KEY=… uv run python -m janbot.eval.optimize --dataset eval/golden_dataset.yaml --out eval/compiled_fewshot.json` -- expected: a compiled program + an MLflow artifact.
- `JANBOT_PROGRAM_PATH=eval/compiled_fewshot.json uv run python -m janbot.eval --dataset eval/golden_dataset.yaml` -- expected: a run marked `fewshot` beside the baseline.
