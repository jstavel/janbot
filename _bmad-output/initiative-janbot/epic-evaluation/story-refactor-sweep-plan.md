---
title: 'Refactor sweep'
type: 'refactor'
ticket: 10
created: '2026-10-15'
status: 'built'
baseline_revision: '30c7083'
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

**Problem:** the eval epic accumulated small deferred findings and doc gaps that were left in-flight during the builds.

**Approach:** a cleanup sweep of the eval package, taking **cleanup only** from the epic's deferred findings — no new behaviour, no scope pushed out of another story. The scope was widened in review (2026-10-15) with three deferred findings the prior reviews left behind and a full inventory of the eval-run config surface for the docs.

## Boundaries & Constraints

**Always:** behaviour-preserving; the metric values, the `/chat` contract, and the gate reference `e635c2bf` (dataset `sha256`) are unchanged.

**Never:** no new metric; no `5.11` e2e-suite work (its own ticket); no dataset change.

**Decision (2026-10-15, review — plan artifacts):** BMAD plan artifacts are **frozen records** of the runs that produced them; this sweep does **not** rewrite completed plans. The duplicated `## Review Triage Log` heading that recurs in five completed eval plan files (a template artifact) is therefore left in place deliberately — it is cosmetic, and editing historical plans would rewrite the record they exist to preserve.

## Proposed scope (deferred findings + review additions)

1. `optimize._record` / pairs last-write-wins guard (`5.14` F7) — verify the per-index pairs entry stays stable if the compile metric runs more than once per index (the existing `recorded` de-dup may already cover it).
2. Eval test import order — `tests/test_eval_*.py` still import `dspy` before `janbot.store` in places (the numpy-proxy hazard; `5.1` defer) — reorder to the documented store-before-`dspy` order.
3. Doc alignment — README/ARCHITECTURE carry no `janbot.eval` package entry or the `python -m janbot.eval` / `janbot.eval.optimize` CLIs; document the **eval-run config surface actually used**: `JANBOT_MODEL_MODE`, `JANBOT_MODEL_SNAPSHOT`, `JANBOT_JUDGE_MODEL`, `JANBOT_PROGRAM_PATH`, `JANBOT_TEMPERATURE`, `JANBOT_SEED`, `JANBOT_TOP_K`, `JANBOT_CORPUS_PATH`, `JANBOT_INDEX_PATH`, and `MLFLOW_TRACKING_URI` (the `5.1`/`5.6`/`5.8` doc defers; widened in review).
4. CHANGELOG tidy — the eval entries are present; ensure none of the stage entries are duplicated or stale after the renames.
5. **(review addition)** `retrieval_mrr` docstring consistency — the title says "the retrieved **list**" (`metrics.py:266`) but the body says "found in the retrieved **set**" (`:269`); make both say "list" (order is the point of MRR).
6. **(review addition)** Metrics-registry accessor — `tests/test_eval_metrics.py:334` reads the private `metrics_module._METRICS`; add a public `MetricSpec` plus `registered_metric_specs()` / `metric_spec(name)` in `metrics.py`, re-export them, and switch the test to the public accessor.
7. **(review addition)** Stray run-artifact hygiene — `compile_pairs.json` (an MLflow artifact) leaks to the repo root and is untracked; add it to `.gitignore` beside `split_manifest.json` and remove the stray file.

## Code Map

- `src/janbot/eval/optimize.py:181` — `_record`'s `recorded` per-index de-dup (already present; verify only).
- `src/janbot/eval/metrics.py:269` — `retrieval_mrr` docstring body ("retrieved set" → "retrieved list").
- `src/janbot/eval/metrics.py:54` — private `_Registration`; rename to public `MetricSpec` and add `registered_metric_specs()` / `metric_spec(name)`; `:99` `registered_metrics()`, `:104` `metric_counts()` consume it.
- `src/janbot/eval/__init__.py:18` — re-export `MetricSpec`, `registered_metric_specs`, `metric_spec`.
- `tests/test_eval_*.py` — import order; `tests/test_eval_metrics.py:334` uses the public accessor.
- `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md` — the eval docs.
- `.gitignore` — `compile_pairs.json`.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/eval/optimize.py` -- confirm the per-index pairs entry is stable across repeated metric calls; change nothing if the `recorded` de-dup already holds -- `5.14` F7.
- [ ] `tests/test_eval_*.py` -- store-before-`dspy` import order -- the `5.1` defer.
- [ ] `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md` -- the `janbot.eval` package, the CLIs, and the full eval config surface (incl. `MLFLOW_TRACKING_URI`) -- the docs gap.
- [ ] `src/janbot/eval/metrics.py` -- `retrieval_mrr` docstring "set" -> "list" -- the review nit.
- [ ] `src/janbot/eval/metrics.py`, `src/janbot/eval/__init__.py`, `tests/test_eval_metrics.py` -- public `MetricSpec` + `registered_metric_specs()`/`metric_spec(name)`; test switch -- the review smell.
- [ ] `.gitignore` -- ignore `compile_pairs.json`; remove the stray copy -- the review hygiene.

**Acceptance Criteria:**
- Given the suite, when it runs, then it is green and metric values are unchanged.
- Given the eval tests, when they import, then `janbot.store` imports before `dspy`.
- Given README/ARCHITECTURE, when read, then the eval package, its CLIs, and the eval config surface (`JANBOT_MODEL_MODE`…`JANBOT_INDEX_PATH`, `MLFLOW_TRACKING_URI`) are documented.
- Given `tests/test_eval_metrics.py`, when it runs, then it reads polarity through a public accessor, not `_METRICS`.
- Given the repo root, when `git status` runs, then `compile_pairs.json` is ignored.

## Implementation Notes

- **Item 1 (5.14 F7) — verified, no change.** `optimize._record` already keeps one pairs entry per index: the `recorded` dict (`optimize.py:181-205`) updates the first-seen entry instead of appending on a repeat index, so the pairs list is stable across repeated metric calls. The residual last-write-wins *value* semantics is inert (`max_rounds=1`, and `5.9` is skipped), so nothing was changed.
- **Item 2 — import order.** Reordered `tests/test_eval_runner.py` and `tests/test_eval_optimize.py` so the chromadb-loading `janbot.ingest`/`janbot.store` import precedes `dspy`, matching the documented order in `pipeline/chat.py:20`. `tests/test_eval_judge.py` already imports `dspy` lazily inside functions (after the module-level store import), so it was left alone.
- **Item 5 — docstring.** `retrieval_mrr`'s body now says "retrieved list", matching its title (order is the point of MRR).
- **Item 6 — accessor.** `_Registration` is renamed to the public `MetricSpec`; added `registered_metric_specs()` and `metric_spec(name)`; re-exported from `janbot.eval`; the polarity test now reads via `metric_spec`.
- **Item 7 — gitignore.** Added `compile_pairs.json` beside `split_manifest.json` (both are MLflow artifact names that leaked to the repo root) and removed the stray file.
- **Decision b** (plan artifacts frozen) recorded in the frozen block; the five completed plans with the duplicated heading were left untouched deliberately.
- **Docs** widened per review: README gains an `eval/` package-layout line and an `## Evaluation` section; ARCHITECTURE gains an `### Eval Layer` subsection; CHANGELOG's stale BootstrapFewShot entry (described the pre-5.14 citation-only objective) was corrected and the train/val + run-records entries added.

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 3 findings, all verified real and patched:
- README claimed every run pins `JANBOT_CORPUS_PATH`/`JANBOT_INDEX_PATH`, but `run_params` (`__main__.py:45`) records neither — **low / patch** — split the sentence into "config the eval reads" vs "params the run records".
- README named a `mlflow-artifacts/` directory; the default SQLite store writes artifacts under `mlruns/` (verified `artifact_location = …/mlruns/1`) — **low / patch** — corrected.
- README presented `janbot.eval.optimize` beside keyless commands, but `optimize.main` calls `parser.error` when no judge resolves (`optimize.py:487`) — **low / patch** — noted it requires `OPENROUTER_API_KEY`.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: green, unchanged values.
- `git status --short` -- expected: no `compile_pairs.json`.
