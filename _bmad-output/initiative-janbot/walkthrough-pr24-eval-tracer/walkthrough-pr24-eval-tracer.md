# Walkthrough: eval tracer (PR #24)

Target: `25ea4e2` — PR #24, branch `eval-5.1-tracer`; `epic-evaluation` story 5.1.

Current block: 7.

## Block 1 — Intent — [x] accepted

**Problem:** JanBot has no evaluation harness — nothing measures retrieval/citation quality against a golden dataset and nothing records an eval run, so Milestone 2's optimization stages have no evidence to act on. This is the epic's tracer bullet (`epic-evaluation` entry 1).

**Approach:** Add a `src/janbot/eval/` package: a YAML golden-dataset loader, a runner that executes each question through the existing `ChatProgram` (model chosen by config — AD-5), a metric-registration interface carrying one stub metric, and an MLflow run recorder. Add a `python -m janbot.eval` CLI and a seed `eval/golden_dataset.yaml`.

(source: the frozen Intent section of the [plan](../epic-evaluation/story-tracer-bullet-seed-dataset-run-the-pipeline-record-a-metric-plan.md))

## Block 2 — Broad strokes — [x] accepted

The change is a self-contained new package that connects three things that already exist — a golden dataset file, the `ChatProgram`, and MLflow — and wires them through a CLI. Open these in order:

- [src/janbot/eval/runner.py](../../../src/janbot/eval/runner.py) — `run_eval`: the whole mechanism, one function.
- [src/janbot/eval/dataset.py](../../../src/janbot/eval/dataset.py) — the dataset file's contract.
- [src/janbot/eval/__main__.py](../../../src/janbot/eval/__main__.py) — the `python -m janbot.eval` entry point.
- [src/janbot/eval/metrics.py](../../../src/janbot/eval/metrics.py) — where real metrics will land.
- [eval/golden_dataset.yaml](../../../eval/golden_dataset.yaml) — the seed data.

## Block 3 — Slice: golden-dataset contract — [x] accepted

[src/janbot/eval/dataset.py](../../../src/janbot/eval/dataset.py) turns `eval/golden_dataset.yaml` into `GoldenItem`s and fails closed: a missing file names the path, a malformed item names its index, an empty document is refused, and `expected_sources` must be a non-empty string list. `expected_answer` is optional (defaults to `""`).

## Block 4 — Slice: runner + metric interface — [x] accepted

[src/janbot/eval/runner.py](../../../src/janbot/eval/runner.py) calls the injected `program` once per item, converting a per-item exception into an `ItemOutcome` instead of aborting, computes every registered metric, and records exactly one MLflow run (params + metrics) after all calls — off any request path; an unreachable backend raises `RuntimeError` naming the URI. [src/janbot/eval/metrics.py](../../../src/janbot/eval/metrics.py) is the registration seam: `register_metric(name, fn)` plus one stub `answer_coverage`.

## Block 5 — Slice: CLI — [x] accepted

[src/janbot/eval/__main__.py](../../../src/janbot/eval/__main__.py) lazily imports `create_app`, builds the pipeline from the environment, loads the dataset, runs `run_eval`, prints the tracking URI / run id / metrics, prints failed items, and returns non-zero when no item succeeded. It reads `MLFLOW_TRACKING_URI` (default `sqlite:///mlflow.db`) and takes run params from the resolved `Config`.

## Block 6 — Slice: tests and review fixes — [x] accepted

[tests/test_eval_dataset.py](../../../tests/test_eval_dataset.py) and [tests/test_eval_runner.py](../../../tests/test_eval_runner.py) prove the matrix rows with a stub program and a `tmp_path` SQLite store. Three review fixes are folded in: the lazy CLI import, the empty-dataset refusal, and the non-zero exit when all items fail.

## Block 7 — Periphery — [x] accepted

- [pyproject.toml](../../../pyproject.toml) — adds `mlflow` and `pyyaml`.
- [.gitignore](../../../.gitignore) — ignores the local MLflow store.
- [deferred-work.md](../deferred-work.md) — two deferred items (eval-test import order; docs).
- [plan](../epic-evaluation/story-tracer-bullet-seed-dataset-run-the-pipeline-record-a-metric-plan.md) — the build plan.
