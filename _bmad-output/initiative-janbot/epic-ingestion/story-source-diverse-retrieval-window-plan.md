---
title: 'Source-diverse retrieval window'
type: 'feature'
ticket: 11
created: '2026-10-15'
status: 'built'
baseline_revision: 'e5d6b97'
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

**Problem:** `VectorStore.query(k)` returns `k` **chunks**, but the answer/citation layer is **source-level**, and one org file yields several chunks (subtrees + file-root) — so a `k=4` window can hold fewer than 4 distinct sources. The 2.10 probe shows item 29's dense `k=4` window is `['cdbazar.org', 'nagios-snmp-monitoring.org', 'intranet-pattern.org', 'intranet-pattern.org']` (a duplicate); item 25 dense is `career-trajectory.org` ×2; item 32 dense is `clojure-testing.org` ×2. Two effects: (a) duplicate sources **crowd out** would-be sources (`retrieval_accuracy`; multi-source items like 25); (b) `retrieval_mrr` ranks the **raw chunk list**, so duplicates **inflate** an expected source's rank.

**Approach:** after the existing over-fetch + fail-closed scope filter + ranking, **select the top-`k` distinct sources** (best-ranked chunk per source) — so `k` chunks = `k` distinct sources — in `VectorStore.query` (the store owns over-fetch + ranking; the program cannot recover a source the store already truncated away). This is a **breadth-vs-depth policy**, not a pure correctness fix: dedup trades more distinct sources for less within-source depth (an answer spanning two subtrees of one file loses the second subtree), so which wins depends on the question and it must be **measured** like `top_k` and hybrid. Probe FIRST (deterministic, no model) over the diagnosed items {23, 25, 29, 32} in **both** dense and hybrid, recording which enter the window; then **one keyed val run at `top_k=4` in dense + source-diverse mode** against `e635c2bf` (dense + raw chunks), isolating the single variable, judged on the transfer metrics (`citation_correctness`, `faithfulness`) + `citation_precision`. The prediction is already visible: in dense mode **item 29 ENTERS once deduped** (the rank-5 chunk `vagrant-provisioning.org` fills the slot freed by the `intranet-pattern.org` duplicate); items 25/32/23 stay out. Verdict routed to entry 20's breadth decision.

## Boundaries & Constraints

**Always:** the window holds **up to `k` distinct sources**, keeping each source's best-ranked chunk; the reachable ranked set is unchanged (only the *selection* to `k` differs); the fail-closed scope filter still precedes selection; the mode ships **off by default** (`chunks`), orthogonal to `JANBOT_RETRIEVAL_MODE`, so the order-asserting store tests stay green (new tests cover the mode only); the probe over the four diagnosed items is recorded **before** any keyed run; the single keyed run pins `top_k=4`, dense + source-diverse, judge `anthropic/claude-haiku-4.5`, dataset sha `4656f824…` verified (mismatch = stop), and records the window selection in the run params; the transfer metrics are the judge.

**Never:** no dataset change; no gate-rule change; no `/chat` contract change; no optimization stage (8/9 stay gated); no change to the 2.10 hybrid mechanics (BM25/RRF) — this composes with them.

**Decision (placement):** the distinct-source selection lives in **the store** (`VectorStore.query`), not the program — the store is where over-fetch and ranking happen, and a program-side dedupe cannot recover sources the store already dropped; when enabled, the store also makes `retrieved_sources` distinct, which corrects `retrieval_mrr` for the definitional reason recorded in the epic-evaluation Notes.

**Decision (Q1 — policy, off by default):** source-diverse selection is a **breadth-vs-depth policy**, not a pure correctness fix (dedup trades distinct sources for within-source depth). It ships **off by default**: `JANBOT_RETRIEVAL_WINDOW=chunks|sources` (`chunks` default), orthogonal to `JANBOT_RETRIEVAL_MODE=dense|hybrid`. The reference `e635c2bf` (dense + raw chunks) stays fixed during the measurement, and the order-asserting store tests stay green — the expected-order changes apply only at **adoption**. Adoption is a separate, deliberate step: if the measurement holds (a gain, or at least no regression beyond the floor), flip the default and re-baseline (supersede `e635c2bf`, as `02ea30f7` was superseded).

**Decision (Q2 — the one keyed run):** the single keyed run measures **dense + source-diverse** — isolating the single variable against `e635c2bf` (dense + raw chunks); hybrid + sources would conflate two changes and make the verdict unattributable. The deterministic probe covers both modes anyway, so hybrid + sources' retrieval effect is known for free.

## Code Map

- `src/janbot/store/chroma.py` — `query`'s dense path truncates the ranked chunk list to `k` (the change: select `k` distinct sources); `_query_hybrid` truncates the fused list the same way. `_within_scope` still filters before selection. Return shape `[{id, text, source_path, breadcrumb}]` unchanged.
- `src/janbot/pipeline/chat.py:124,130,143` — `last_retrieved_sources` is set from the query's sources; it becomes distinct once the store selects distinct sources (the `retrieval_mrr` correction).
- `src/janbot/eval/metrics.py:254-291` — `retrieval_accuracy` (set containment — benefits from more distinct sources) and `retrieval_mrr` (ranks the source list — benefits from distinctness).
- `src/janbot/config.py:60-68,151-164` — a new env knob `JANBOT_RETRIEVAL_WINDOW` (`chunks` default; `sources`; unknown values fail fast), orthogonal to `JANBOT_RETRIEVAL_MODE`; documented in `README.md` and covered in `tests/test_config.py` like the 2.10 knob.
- `src/janbot/eval/__main__.py:45-55` — `run_params` (records `retrieval_mode` since 2.10); add the **window selection** so the run is comparable.
- `tests/test_store_scope.py` (order-asserting: `:55,78,180,197`), `tests/test_ingest_tracer.py:69-83`, `tests/test_ingestion_e2e.py:64-92`, `tests/test_scope.py`, `tests/test_ingest_idempotent.py:192,322` — asserted raw chunk orders that stay **green** (the window mode is off by default; new tests cover the `sources` mode only). The expected-order changes apply only at adoption.
- `tests/test_store_hybrid.py` — the 2.10 hybrid tests (order/truncation/scope) likewise.
- Evidence base: `epic-ingestion/run-7c868e2f-probe.txt` (the per-item dense/hybrid windows) and MLflow run `7c868e2f`.

## Tasks & Acceptance

**Execution:**
- [x] `src/janbot/store/chroma.py` -- select the top-`k` distinct sources (best-ranked chunk per source) after ranking, in both the dense and hybrid paths, gated by the window mode -- the lever. *(Done: `_window` shared by both paths; `chunks` short-circuits to `ranked[:k]` — byte-identical; sourceless chunks keyed by id so they do not collapse.)*
- [x] `src/janbot/config.py`, `tests/test_config.py`, `README.md` -- the `JANBOT_RETRIEVAL_WINDOW` knob (`chunks` default / `sources`, fail-fast), orthogonal to the retrieval mode -- the off-by-default seam. *(Done.)*
- [x] `src/janbot/api/main.py` -- thread the window mode into `VectorStore` -- the wiring. *(Done.)*
- [x] `src/janbot/eval/__main__.py` -- record the window selection in `run_params` (and update `tests/test_eval_runner.py`'s params key set) -- comparability. *(Done.)*
- [x] `tests/test_store_*.py` -- the `sources` mode: order, `k` semantics (k distinct sources), scope-filter-before-selection, fewer-distinct-sources-than-k, determinism, both modes; the default `chunks` mode keeps the existing order tests green -- prove the mechanism without a model. *(Done: `tests/test_store_window.py`, 17 cases incl. the unscoped sourceless-chunk case.)*
- [x] run the no-model window probe over the four diagnosed items (dense and hybrid, `top_k=4`) -- record which enter; the primary evidence, before the keyed run. *(Done: `run-2.11-window-probe.txt` — dense×sources recovers item 29 exactly as predicted.)*
- [x] run the single keyed val run at `top_k=4` in dense + source-diverse mode against `e635c2bf` (keyed; hitl) -- the measurement. *(Done: MLflow run `0c01ba33`.)*
- [x] record the before/after table, per-item effects, and the floor verdict in `epic-ingestion.md` Notes, routed to entry 20 -- the deliverable. *(Done; captured output preserved as `run-0c01ba33-output.txt`.)*

**Acceptance Criteria:**
- Given a ranked candidate set, when the `sources` window is selected, then it holds up to `k` **distinct** sources with each source's best-ranked chunk, and the fail-closed scope filter still precedes selection.
- Given the shipped default (`chunks`), when no knob is set, then retrieval behavior is byte-identical to today (the order-asserting store tests pass unchanged).
- Given the deterministic probe, when it runs over {23, 25, 29, 32} in both modes, then it records which enter the window before any keyed run (dense: item 29 enters once deduped).
- Given the single keyed val run, when its params are read, then `top_k=4`, dense mode, and the `sources` window are recorded.
- Given the keyed run, when compared to `e635c2bf`, then before/after `retrieval_accuracy` / `retrieval_mrr` / `citation_correctness` / `faithfulness` (+ `citation_precision`) are recorded, and the verdict states whether a gate metric moved beyond the 1.5σ floor (≥ 3 items at n=15) or is within noise and routed to entry 20 — with the `retrieval_mrr` delta reported as **definitional** (retrieved_sources becomes distinct; see the epic-evaluation Notes entry), not a quality change.

## Implementation Notes

- The mechanism: `JANBOT_RETRIEVAL_WINDOW` (`chunks` default / `sources`, fail-fast) → `Config.retrieval_window` → `api/main.py` → `VectorStore(retrieval_window=…)`. `_window(ranked, k)` is shared by both query paths: `chunks` short-circuits to `ranked[:k]` (byte-identical to the old truncation); `sources` walks the ranked list keeping the first (best-ranked) chunk per distinct source and stops at `k`. Sourceless chunks (`source_path is None`) are keyed by their `id` so they do not collapse into one slot (scoped paths never see them — the fail-closed filter drops them first). `run_params` records `retrieval_window`.
- The measurement: the no-model window probe (primary evidence, `run-2.11-window-probe.txt`) then one keyed val run — MLflow `0c01ba33` (judge `anthropic/claude-haiku-4.5`, `top_k=4`, dense + `retrieval_window=sources`, dataset sha `4656f824…` verified) against `e635c2bf`. Result: `retrieval_accuracy` 0.7333 → 0.8000 (**+1 item — item 29**, exactly the prediction); `retrieval_mrr` 0.6667 → 0.7056 (**definitional** — sources became distinct); but **`faithfulness` 0.7333 → 0.4667 — a −4-item regression beyond the 1.5σ ≈ 0.17 floor** (the failing set {23,25,29,32} → {14,17,19,22,23,25,32,36}: items 14, 17, 19, 22, 36 regressed, item 29 fixed), `citation_correctness` flat 0.7333, `citation_precision` → 0.6111, `public_references` → 0.8667 (a new reference failure on item 22). **Verdict: the breadth-vs-depth trade loses on the val set — the dense+sources configuration is NOT adopted; the shipped default stays `chunks`; routed to entry 20's breadth decision.**
- Captured evidence preserved beside the Notes: `run-2.11-window-probe.txt` and `run-0c01ba33-output.txt`.
- Full verification after the review patches: `uv run pytest -q` → **379 passed**; the store's order-asserting tests pass unchanged.

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 4 findings: 3 patched, 1 patched at commit:
- `run-0c01ba33-output.txt` was untracked, so the note's per-item-evidence pointer dangled on a clean checkout — **low / patch** — the finalize commit includes the artifact beside the note (the sibling run artifacts are tracked).
- `tests/test_store_window.py`'s mode-invariant assertion was a tautology for the `chunks` cases (`... or window == "chunks"` is constant True there) — **low / patch** — the distinctness assertion now applies only to the `sources` cases.
- `src/janbot/eval/__main__.py`'s module docstring omitted `retrieval_window` from the recorded-config enumeration — **low / patch** — added.
- `_window` collapsed all `None`-source chunks into one slot under the `sources` window (an unscoped store returns sourceless chunks; the scoped paths never do) — **low / patch** — sourceless chunks are now keyed by their `id`, with a test case covering an unscoped store of sourceless chunks.

## Design Notes

- **Adoption re-bases the reference.** Adopting `sources` as the default makes the new reference source-diverse, which **stales the 2.10 hybrid comparison** (measured against dense + raw chunks): after re-baselining, the whole lever set (`top_k`, hybrid, future levers) must be compared against the new reference.
- **The `retrieval_mrr` delta is definitional, not quality.** Once the window is source-diverse, `retrieved_sources` becomes distinct, so MRR shifts for a definitional reason (see the epic-evaluation Notes entry) — the before/after MRR delta must not be read as a quality change.
- **`sources` is meaningful only over a complete candidate set.** The scoped path (and production, which is scoped; the eval path is scoped) over-fetches every in-scope chunk, so the selection sees everything. An unscoped dense store fetches only `k` candidates, so `sources` degrades there (it cannot recover a source that was never fetched) — the fewer-distinct-sources-than-k test covers that degradation; the dense unscoped path is deliberately not changed to over-fetch.

## Verification

**Commands:**
- verify the dataset sha (`sha256sum eval/golden_dataset.yaml` = `4656f824…`) before the keyed run -- a mismatch is a stop.
- the no-model window probe over the four diagnosed items (dense and hybrid, `top_k=4`) -- expected: which enter the window (dense: item 29 enters once deduped).
- `uv run pytest -q` -- expected: green (the order-asserting store tests unchanged — `chunks` is the default; only the new sources-mode tests are added).
- `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 JANBOT_TOP_K=4 JANBOT_RETRIEVAL_WINDOW=sources OPENROUTER_API_KEY=… uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` (hitl) -- expected: one keyed val run recorded in MLflow with `top_k=4`, dense mode, and the `sources` window in the params.
- compare against `e635c2bf` -- expected: the before/after table, per-item effects, and the floor verdict routed to entry 20.
