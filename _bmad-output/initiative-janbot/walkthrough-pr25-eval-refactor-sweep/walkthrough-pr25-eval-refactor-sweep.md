# Walkthrough — PR #25: eval cleanup sweep

Target: PR #25 (`eval-refactor-sweep`), commit 9160535 on branch `eval-refactor-sweep`, repo `jstavel/janbot`.

## Review

- [x] **1. Intent** — *(check when satisfied)*

Accepted 2026-10-15 — no edits.

> **Problem:** the eval epic accumulated small deferred findings and doc gaps that were left in-flight during the builds.
>
> **Approach:** a cleanup sweep of the eval package, taking **cleanup only** from the epic's deferred findings — no new behaviour, no scope pushed out of another story. The scope was widened in review (2026-10-15) with three deferred findings the prior reviews left behind and a full inventory of the eval-run config surface for the docs.

Source: the plan file's frozen Intent block, [`../../epic-evaluation/story-refactor-sweep-plan.md`](../../epic-evaluation/story-refactor-sweep-plan.md), carried verbatim.

- [x] **2. Broad strokes** — *(check when satisfied)*

The change is a documentation-and-hygiene pass over the eval package plus one small API widening — no runtime behavior changes. Four entry points a reader would open first:

1. [metrics.py:54](../../../src/janbot/eval/metrics.py#L54) — the public `MetricSpec` (the renamed former `_Registration`) plus the new accessors `registered_metric_specs()` and `metric_spec(name)` just below it (~line 101) — the one real API change in the PR.
2. [test_eval_metrics.py:331](../../../tests/test_eval_metrics.py#L331) — the polarity test switched from the private `metrics_module._METRICS` to `metric_spec(...)`, proving the point of the new accessor.
3. [README.md:92](../../../README.md#L92) — the new `## Evaluation` section: the three eval CLIs, the full eval config surface, and the keyless/keyed split.
4. [test_eval_runner.py:15](../../../tests/test_eval_runner.py#L15) and [test_eval_optimize.py:18](../../../tests/test_eval_optimize.py#L18) — the import-order fixes (store-loading imports before `dspy`).

- [x] **3. Slice: the metric registry goes public**

The metric registry's private per-metric record becomes a public, frozen API: `register_metric` builds a `MetricSpec`, the existing `registered_metrics()`/`metric_counts()` read it, and two accessors expose it — `registered_metric_specs()` returns a snapshot mapping, `metric_spec(name)` a single spec (raising `KeyError` for an unregistered name). Re-exported from the package, and the polarity test now reads through the public path instead of the module-private `_METRICS`.

- [metrics.py:54](../../../src/janbot/eval/metrics.py#L54) — the public frozen `MetricSpec` (renamed `_Registration`).
- [metrics.py:101](../../../src/janbot/eval/metrics.py#L101) — `registered_metric_specs()` / `metric_spec(name)`.
- [metrics.py:90](../../../src/janbot/eval/metrics.py#L90) — `register_metric` builds the spec; `:112`/`:124`-area consumers unchanged.
- [__init__.py:21](../../../src/janbot/eval/__init__.py#L21) — `MetricSpec`, `metric_spec`, `registered_metric_specs` re-exported.
- [test_eval_metrics.py:331](../../../tests/test_eval_metrics.py#L331) — the test switch to `metric_spec(name).higher_is_better`.

- [x] **4. Slice: store-before-dspy import order in the eval tests**

`chromadb` must load before `dspy`, which installs a lazy numpy proxy at import time and breaks numpy when it lands first (the documented hazard in `pipeline/chat.py`). Two eval test modules imported `dspy` at the top before any store/ingest import; each is reordered so the chromadb-loading import comes first, mirroring the documented order. `test_eval_judge.py` already imports `dspy` lazily inside functions, so it is untouched.

- [pipeline/chat.py:20](../../../src/janbot/pipeline/chat.py#L20) — the documented store-before-dspy rule.
- [test_eval_runner.py:15](../../../tests/test_eval_runner.py#L15) — `janbot.ingest` (loads `janbot.store` → chromadb) now precedes `dspy`.
- [test_eval_optimize.py:18](../../../tests/test_eval_optimize.py#L18) — `janbot.store` now precedes `dspy`.
- [test_eval_judge.py:155](../../../tests/test_eval_judge.py#L155) — already lazy; unchanged.

- [x] **5. Slice: the eval docs**

Three docs now carry the eval story end to end. README gains an `## Evaluation` section (the three CLIs, the eval config surface, and the keyless-vs-keyed split — the compile requires a judge/key) plus an `eval/` entry in the package layout; ARCHITECTURE gains an `### Eval Layer` subsection under Layer Details; CHANGELOG corrects the stale citation-only BootstrapFewShot entry and adds the train/val and run-records entries. Accuracy was reviewed against the code: the section separates the config the eval *reads* from the params a run *records*, and names the real artifact directory (`mlruns/`).

- [README.md:92](../../../README.md#L92) — `## Evaluation`; [README.md:123](../../../README.md#L123) — `eval/` in the package layout.
- [ARCHITECTURE.md:98](../../../ARCHITECTURE.md#L98) — `### Eval Layer`.
- [CHANGELOG.md:18](../../../CHANGELOG.md#L18) — corrected BootstrapFewShot entry and new train/val + run-records entries.

- [x] **6. Slice: verified, not changed (5.14 F7)**

One planned sweep item turned out to already be done. `optimize._record` keeps a `recorded` dict keyed by dataset index: a repeat call updates the first-seen entry in place instead of appending, so the `compile_pairs.json` list stays one entry per index even if the compile metric runs more than once per index — exactly what `5.14` F7 deferred. The residual last-write-wins *value* semantics is inert (`max_rounds=1`, and `5.9` is skipped), so nothing was changed.

- [optimize.py:181](../../../src/janbot/eval/optimize.py#L181) — `_record`'s `recorded` per-index de-dup (the verified guard).

- [x] **7. Periphery**

Small enablers and registration, one clause each:

- [.gitignore:11](../../../.gitignore#L11) — `compile_pairs.json` added beside `split_manifest.json` (both MLflow artifact names that leaked to the repo root); the stray copy is removed.
- [__init__.py:69](../../../src/janbot/eval/__init__.py#L69) — `__all__` gains `MetricSpec`, `metric_spec`, `registered_metric_specs`.
- [story-refactor-sweep-plan.md:1](../../../_bmad-output/initiative-janbot/epic-evaluation/story-refactor-sweep-plan.md#L1) — the plan itself is committed with the change, closed as `built`.
- Decision on record: BMAD plan artifacts are frozen records — the duplicated `## Review Triage Log` heading in five completed plans is left in place deliberately (cosmetic; not rewritten).

All 7 blocks accepted — walkthrough complete (2026-10-15).
