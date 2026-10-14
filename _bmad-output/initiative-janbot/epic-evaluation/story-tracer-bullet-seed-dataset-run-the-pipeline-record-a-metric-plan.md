---
title: 'Eval tracer: seed dataset → pipeline → MLflow metric'
type: 'feature'
ticket: 1
created: '2026-10-14'
status: done
baseline_revision: '0cb9d63c793af9c5b2fcad5ef14af3c3e4e1c392'
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

**Problem:** JanBot has no evaluation harness — nothing measures retrieval/citation quality against a golden dataset and nothing records an eval run, so Milestone 2's optimization stages have no evidence to act on. This is the epic's tracer bullet (`epic-evaluation` entry 1).

**Approach:** Add a `src/janbot/eval/` package: a YAML golden-dataset loader, a runner that executes each question through the existing `ChatProgram` (model chosen by config — AD-5), a metric-registration interface carrying one stub metric, and an MLflow run recorder. Add a `python -m janbot.eval` CLI and a seed `eval/golden_dataset.yaml`.

## Boundaries & Constraints

**Always:** run through the existing `ChatProgram` built by `create_app`; pick the model by `Config` (`build_lm`, locked snapshot in eval mode); keep the output shape the `ChatResponse` contract; keep MLflow logging off the request path.

**Never:** no real retrieval/citation metrics (entries 3–4), no LLM-as-a-judge (entry 5), no prompt optimization (entries 7–9); no changes to `pipeline/`, `api/`, `store/`, `ingest/`; no reactive-testing; do not import `dspy` before `janbot.store` (numpy proxy break — `api/main.py:16-19`).

**Decision (2026-10-14):** the seed questions in `eval/golden_dataset.yaml` are drafted by the builder from `public_profile_org/` topics with expected sources, and corrected by the owner; the full golden set is completed in entry 2.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | seed YAML, a program | each item answered; stub metric recorded in one MLflow run with params | No error |
| Missing dataset | path absent | — | `FileNotFoundError` naming the path |
| Malformed item | item missing `question`/`expected_sources` | — | `ValueError` naming the item index |
| MLflow unreachable | bad tracking URI | — | run raises with the URI (no partial silent success) |

</frozen-after-approval>

## Code Map

- `src/janbot/pipeline/chat.py:101` — `ChatProgram(store, top_k, rewriter)`; `set_lm(lm)`; `program(question=...) -> ChatResponse`. Reused as-is.
- `src/janbot/api/main.py:43` — `create_app(env, *, embedder, lm_factory)` builds config→store→LM→program at `app.state.program`; the CLI reuses it.
- `src/janbot/llm/__init__.py:59` — `build_lm(config, api_key, lm_factory)`; eval mode → `openrouter/<snapshot>` at temp/seed.
- `src/janbot/config.py:96` — `load_config(env)`; `Config` fields incl. `model_mode`, `seed`, `top_k`.
- `src/janbot/api/contract.py` — `ChatResponse{answer, citations}`; the runner's per-item result type.
- `tests/conftest.py` — `embedder`, `write_org`, `chunk_id` fixtures; `dspy.utils.DummyLM` pattern in `tests/test_chat.py`.
- `pyproject.toml` — add `mlflow` and `pyyaml` to runtime deps.
- New: `src/janbot/eval/{__init__,dataset,metrics,runner,__main__}.py`, `eval/golden_dataset.yaml`, `tests/test_eval_dataset.py`, `tests/test_eval_runner.py`.

## Tasks & Acceptance

**Execution:**
- [ ] `pyproject.toml` -- add `mlflow` and `pyyaml` -- runner needs both.
- [ ] `src/janbot/eval/dataset.py` -- `GoldenItem(question, expected_answer, expected_sources)`; `load_golden_dataset(path)` validates each item and fails closed -- the dataset contract.
- [ ] `src/janbot/eval/metrics.py` -- metric callable type + a registry + one stub metric -- the registration interface entries 3–5 extend.
- [ ] `src/janbot/eval/runner.py` -- `run_eval(items, program, *, tracking_uri, experiment)` runs each item, computes metrics, records one MLflow run (params: model mode, snapshot, temperature, seed; the metric) -- the thinnest dataset→pipeline→MLflow path.
- [ ] `src/janbot/eval/__main__.py` -- CLI: `create_app`, load dataset, `run_eval`; reads `MLFLOW_TRACKING_URI` (default `mlruns`) -- the runnable entry point.
- [ ] `eval/golden_dataset.yaml` -- seed of recruiter Q&As (draft from `public_profile_org/` topics) -- the dataset.
- [ ] `tests/test_eval_dataset.py`, `tests/test_eval_runner.py` -- unit tests using a stub program and a `tmp_path` MLflow URI -- prove loading, validation, and recording without a key.

**Acceptance Criteria:**
- Given a stub program answering every item, when `run_eval` runs against a `tmp_path` tracking URI, then exactly one MLflow run exists with the configured params and the stub metric.
- Given the seed YAML, when `load_golden_dataset` runs, then it returns one `GoldenItem` per entry with non-empty question and expected sources.
- Given an item missing a required field, when loading, then it raises `ValueError` naming that item.
- Given `python -m janbot.eval` against a keyless eval config, when the CLI runs, then it reads the dataset and reports the tracking URI rather than failing on the key.

## Implementation Notes

- MLflow 3.17.1 refuses the filesystem backend by default (`MLFLOW_ALLOW_FILE_STORE`), so tests and the epic's real runs use SQLite. The CLI default is `sqlite:///mlflow.db` (epic decision), not the plan's literal `mlruns`, which would fail on first run.
- The loader requires `question` and `expected_sources` (per the frozen I/O matrix); `expected_answer` is optional and defaults to `""`. Seed items all carry it.
- `.gitignore` gained `mlruns/`, `mlflow.db`, `mlflow-artifacts/` so a real run's local store is never committed.
- The seed dataset is builder-drafted (8 items) and unverified against real retrieval (no model key); the owner corrects it, and entry 2 completes the full set.

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 5 findings:
- lazy-import `create_app` in the eval CLI — **medium / patch** — verified: `janbot.api.main:131` has module-level `app = create_app()`, so `from janbot.api.main import create_app` at `__main__.py:22` builds a second app from ambient env at import, and fails without a key in production mode.
- empty golden dataset returns `[]` — **medium / patch** — verified: `dataset.py:88-89` returns `[]` for an empty/comment-only file, so `run_eval` records a 0-item, `answer_coverage=0.0` run and exits 0, contradicting the loader's "fails closed" contract.
- CLI ignores per-item failures and exits 0 — **medium / patch** — verified: `__main__.py:90-95` prints metrics and returns 0 even when items raised (`ItemOutcome.error` set, e.g. `answer_coverage` 0.75).
- test import order (`dspy.utils` before `janbot.store`) — **low / defer** — a latent numpy-proxy hazard, but it mirrors the pre-existing `tests/test_chat.py` pattern; not introduced here.
- no CHANGELOG/README/ARCHITECTURE update — **low / defer** — the repo-wide CHANGELOG gap is already tracked in `deferred-work.md`; the README/ARCHITECTURE layout note is deferred to a docs pass.

## Design Notes

`run_eval(items, program, ...)` keeps the pipeline out of the eval package: the CLI wires `create_app`, tests inject a stub `program`, so the core is testable keyless. MLflow writes to `tracking_uri` (a file store in tests, a server in real runs).

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_dataset.py tests/test_eval_runner.py` -- expected: green.
- `uv run ruff check src/janbot/eval tests/test_eval_*.py` (if ruff is configured) -- expected: clean.

**Manual checks (if no CLI):**
- With an index built and `MLFLOW_TRACKING_URI` pointing at a store: `uv run python -m janbot.eval --dataset eval/golden_dataset.yaml` records a run visible via `mlflow ui`. (Real locked-snapshot run needs `OPENROUTER_API_KEY`; the person starts the MLflow tracking server.)
