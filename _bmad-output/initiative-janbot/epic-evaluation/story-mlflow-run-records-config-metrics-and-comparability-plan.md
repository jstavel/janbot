---
title: 'MLflow run records: config, metrics and comparability'
type: 'feature'
ticket: 6
created: '2026-10-14'
status: 'built'
baseline_revision: 'e44ab9b'
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

**Problem:** runs are recorded, but not yet *comparable* — a run must carry every setting that produced its metrics (including the retrieval tuning knob) and the exact **dataset revision**, so two runs can be diffed and a metric change is attributable to a pipeline change, not an input change.

**Approach:** complete the MLflow run record — log all run-affecting config (`model_mode`, `model_snapshot`, `temperature`, `seed`, `judge_model`, `top_k`) as params, log the golden dataset as an **artifact** plus a `dataset_sha256` param, and give the run a name — over the tracer's existing recorder.

## Boundaries & Constraints

**Always:** every setting that changes a metric is a logged param (AD-5 makes them all configuration); the dataset is recorded so a run is reproducible.

**Never:** no metric logic change; no judge/contract change; no new dependency.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| A recorded run | a completed eval | params cover all run-affecting config; the dataset is an artifact; the metrics are present | No error |
| Two runs, different configs | two runs | both expose config + metrics side by side | No error |
| Dataset changes | a different `golden_dataset.yaml` | the `dataset_sha256` differs; the artifact pins it | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/__main__.py:33` — `run_params(config)`; extend to include `top_k` (and it already carries `judge_model`).
- `src/janbot/eval/runner.py:107` — `_record` logs params + metrics; add the dataset artifact (`mlflow.log_artifact`) and a `dataset_sha256` param, plus a run name.
- `tests/test_eval_runner.py` — two runs expose config + metrics; the dataset artifact/param is recorded.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/eval/__main__.py` -- add `top_k` to `run_params` -- the retrieval tuning knob must be comparable.
- [ ] `src/janbot/eval/runner.py` -- log the golden dataset as an artifact and a `dataset_sha256` param, and name the run -- pin the input.
- [ ] `tests/test_eval_runner.py` -- a recorded run exposes all params + the dataset artifact; two runs compare -- prove it.

**Acceptance Criteria:**
- Given a completed eval, when the run is recorded, then its params include `model_mode`, `model_snapshot`, `temperature`, `seed`, `top_k`, `judge_model` and `dataset_sha256`.
- Given the run, when it is read back, then the golden dataset is attached as an artifact.
- Given two runs with different configs, when both are read, then their params and metrics can be compared side by side.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 6 findings, all patched:
- no test pinned the full param set / `run_params` — **medium / patch** — added a `run_params` key-set test and a run read-back asserting the recorded params.
- the CLI `dataset_path` wiring was untested — **medium / patch** — added a CLI test reading back the run's `dataset_sha256` + artifact.
- a missing `dataset_path` silently recorded an unpinned run — **medium / patch** — `run_eval` now fails closed, naming the path.
- a dataset-read error inside `_record` was misattributed as an MLflow failure — **low / patch** — the dataset is validated before the MLflow `try`.
- stale `run_eval`/module docstrings — **low / patch** — updated.
- `__main__` module docstring omitted `top_k` — **low / patch** — updated.

Review pass 2 (patches applied): params fully pinned and tested; the dataset is validated fail-closed before recording; docs match.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_runner.py` -- expected: green.
- `uv run python -m janbot.eval --dataset eval/golden_dataset.yaml` -- expected: a run whose params include `top_k`/`dataset_sha256` with the dataset artifact.
