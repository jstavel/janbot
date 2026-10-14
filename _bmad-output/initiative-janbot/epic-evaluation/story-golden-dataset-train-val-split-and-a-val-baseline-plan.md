---
title: 'Golden dataset train/val split and a val baseline'
type: 'feature'
ticket: 17
created: '2026-10-14'
status: done
baseline_revision: '4a68e8b'
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

**Problem:** compilation and evaluation run over the same 36 items, so "compiled vs baseline" is train-on-test — any gain may be memorization, not generalization.

**Approach:** a **per-item** `split: train|val` on `GoldenItem` (loader fail-closed; `load_golden_dataset(path, split=None)` filters, `None` = all), a compile CLI that refuses any split but `train`, an eval CLI that takes `--split {all,train,val}`, `split`/`trainset_size` in the run params plus a split-manifest artifact, and a **re-measured val baseline**. Annotate all 36 items in one stratified pass (~60/40 → 22 train / 14 val; val spans classes and sources, not all JanBot).

## Boundaries & Constraints

**Always:** one schema pass with entry 13's `should_refuse` field; compile is train-only (fail fast otherwise); the gate compares on the **same held-out val items**.

**Never:** no multi-objective objective (entry 14), no MRR/denominators (15/16, done), no refusal metrics (13), no gate rule (18); `eval/compiled_*.json` stays unpinned until the val re-run passes.

**Decision (2026-10-14, B3 resolved):** the split is **item-level** with the confirmed val set (2, 5, 7, 10, 13, 15, 18, 20, 21, 23, 24, 26, 30, 33). No *question* is in both splits; several *sources* are shared (val 10↔9/22, 23↔6/34, 24↔25, 13↔34, 26↔1, 26↔35) — different questions about the same document, generalized citable knowledge, not contamination. A source-disjoint val would drop public-reference coverage entirely (its items live in multi-item sources), which the plan wants.

**Decision (2026-10-14, schema — B1):** `GoldenItem.split: str = "train"` (dataclass default, so the direct constructions are unchanged); `_parse_item` is fail-closed on a missing or unknown marker, checked after question/sources so the malformed-item tests keep their intended error.

**Decision (2026-10-14, one schema pass — B2):** `GoldenItem.should_refuse: bool = False` is added in the **same** pass (forward-declared, loader-validated), so entry 13 adds only the refusal items and metrics.

**Decision (2026-10-14, granularity — Q2):** single split now (14 val → ~3-item noise floor; "no decision" is a valid gate outcome); the 3-fold variant (entry 18) is deferred.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Load all | `split=None` | every item (backward compatible) | No error |
| Load one split | `split="val"` | only val items | No error |
| Missing / unknown marker | an item without a valid `split` | the loader fails, naming the item index | Error |
| Compile over non-train | `--split val` (or all) | refused | Error |
| Eval / gate | `--split val` | scores only val items; the run records split + manifest | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/dataset.py:20` — `GoldenItem` gains `split` + `should_refuse` (both defaulted); `:67` the loader's `GoldenItem(...)`; `:74` `load_golden_dataset(path, split=None)`; `_parse_item` validates both. **Every direct `GoldenItem(...)` call-site** (all keep working via defaults): `src/janbot/eval/dataset.py:67`; `tests/test_eval_public_urls.py:47`; `tests/test_eval_judge.py:224-225`; `tests/test_eval_optimize.py:88`; `tests/test_eval_metrics.py:41`; `tests/test_eval_runner.py:35-36`. **YAML fixtures** (must carry a valid `split`): the valid-item fixtures in `tests/test_eval_dataset.py` (built via `_write`, ~7 entries); the malformed-item fixtures are unaffected (fail on question/sources before the split check).
- `src/janbot/eval/optimize.py:246` — the compile CLI takes `--split` (train only); the compiled run records `split` + `trainset_size`.
- `src/janbot/eval/__main__.py:64` — the eval CLI takes `--split {all,train,val}`; `run_params` records `split`.
- `src/janbot/eval/runner.py:107` — a split-manifest artifact beside the dataset artifact.
- `tests/test_eval_dataset.py`, `tests/test_eval_optimize.py` — the loader filter, the compile guard, the manifest.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/eval/dataset.py` -- `GoldenItem.split` + a validated loader with a `split` filter (`None` = all) -- the split.
- [ ] `eval/golden_dataset.yaml` -- annotate all 36 items `train`/`val` per the agreed stratified split -- the data (hitl: owner approves).
- [ ] `src/janbot/eval/optimize.py`, `src/janbot/eval/__main__.py` -- compile `--split` (train only, fail fast), eval `--split {all,train,val}` -- the CLIs.
- [ ] `src/janbot/eval/runner.py` -- record `split`/`trainset_size` params + a split-manifest artifact -- auditability.
- [ ] `tests/test_eval_dataset.py`, `tests/test_eval_optimize.py` -- filter/guard/manifest -- prove the matrix.
- [ ] run the **val baseline** (hitl: needs index + key) -- the gate reference.

**Acceptance Criteria:**
- Given the dataset, when it loads with no split, then every item is returned; with `split="val"`, then only val items.
- Given an item with a missing or unknown split marker, when it loads, then it fails naming the index.
- Given the compile CLI, when `--split` is anything but `train`, then it refuses; over `train`, it compiles and records `trainset_size`.
- Given an eval run with `--split val`, then it scores only val items and records `split` + a split-manifest artifact.
- Given a val baseline run, then compiled-vs-baseline is measured on the same held-out items.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Review Triage Log

Review pass 1 (quick, pinned) — 6 findings, 5 patched / 1 expected:
- `load_golden_dataset` does not validate the `split` filter, so an unknown split returns `[]` (fail-open) — **medium / patch** — validate against `VALID_SPLITS`, fail fast.
- eval `--split val` selecting **zero** items records an all-zero run and exits 0 (a gate with an empty held-out set "passes") — **medium / patch** — fail when the selected split is empty.
- `split_manifest`'s docstring claims dataset positions but it enumerates the passed iterable — **low / patch** — correct the contract.
- the shipped split has **six** cross-split sources, not the three the decision names (add clojure-testing 13↔34, career-trajectory 26↔1, dna-threads 26↔35) — **low / patch** — correct the recorded decision (item-level holds regardless).
- compile runs record `trainset_size` but no split manifest — **medium / patch** — log the manifest on compile too.
- no val baseline run — **expected** — the HITL step run separately (not a code defect).

Review pass 2 (patches applied): the filter and empty-split cases fail closed; the manifest contract and the decision text are corrected; the compile logs its manifest.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_dataset.py tests/test_eval_optimize.py` -- expected: green.
- `OPENROUTER_API_KEY=… uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` -- expected: a val run with the split + manifest (hitl).
