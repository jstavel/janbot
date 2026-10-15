---
title: 'Retrieval recall: the embedding/query-side lever (the distant val misses)'
type: 'feature'
ticket: 10
created: '2026-10-15'
status: 'built'
baseline_revision: '0699535'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the 2.9 experiment proved `top_k` alone recovers only item 29; the other three misses (items 23, 32 — expected sources at rank 15 — and item 25 — two expected sources absent from the top 30) are semantically distant from the questions' phrasing, and the store is plain dense embedding with no other lever. This is the lever that can plausibly move a gate metric beyond the 1.5σ floor, and its result is entry 20's breadth input.

**Approach:** build a **hybrid dense+lexical retrieval mode** in the store — the chosen candidate of the three (embedder swap / hybrid / query expansion): BM25 over the candidate chunk texts fused with the dense ranking by reciprocal-rank fusion. It needs **no re-index** (dense vectors unchanged; the lexical side runs over the documents the scoped query already over-fetches), **no new dependency** (a small in-module BM25), and is deterministic. It ships **off by default** (`dense` stays the shipped behavior) and is enabled per-run for the measurement, so the existing order-asserting store tests stay green. **This story never flips the shipped default**: on a clear win it records an explicit adoption recommendation — including the `citation_precision` guard (the O2 over-citing risk) — and the owner adopts (or not) as a separate act. Primary evidence first (the 2.9 pattern): the fusion is deterministic, so a **no-model probe over the real index** computes which of {23, 25, 32} enter the `top_k=4` window under BM25+RRF before any model call — it caps the retrieval-driven gain up front and says whether the keyed run can even reach the floor. The measurement then compares the hybrid-enabled val run against `e635c2bf` (dataset sha `4656f824…` verified before launching — a mismatch is a stop; the mode is the only variable: `top_k=4`, judge `anthropic/claude-haiku-4.5`). Judge on the transfer metrics (`citation_correctness`, `faithfulness`) and watch `citation_precision`; never the mechanically inflated `retrieval_accuracy`. Item 25 may stay unrecovered — lexical overlap with "younger engineer" is weak; record what happens.

## Boundaries & Constraints

**Always:** the fusion is deterministic (fixed tokenizer — lowercase alnum runs, no stemming, no stopword list — fixed BM25 parameters, fixed RRF constant) and the store's return shape, scope filtering (fail-closed, before truncation), and `k` truncation semantics are unchanged; **the shipped default stays `dense`, full stop — this story never flips it**; the measurement run pins `top_k=4` (the mode is the only variable vs `e635c2bf`), judge `anthropic/claude-haiku-4.5`, and the dataset sha verified before launching (a mismatch is a stop); the run records `retrieval_mode` in its MLflow params; the no-model window probe is recorded before the keyed run; every claim about ranks is backed by the deterministic mechanism.

**Never:** no dataset change; no gate-rule change; no `/chat` contract change; no embedder swap in this story (recorded as the next lever if hybrid falls short); no optimization stage (8/9 stay gated); no new runtime dependency.

**Decision (ship semantics):** this story **never** flips the shipped retrieval default — not even on a clear win. On a win it records an explicit **adoption recommendation** for the owner (the flip itself is a separate act), with the `citation_precision` guard attached: a hybrid window retrieves more candidates, and the O2 over-citing risk (`citation_precision` 0.69 → 0.50 under the multi-objective compile) is exactly what the recommendation must address.

## Code Map

- `src/janbot/store/chroma.py:224-269` — `VectorStore.query`: already over-fetches all in-scope documents with texts (`include=["documents"]`, `n_results=collection.count()` when scoped); add the lexical scorer + fusion here, before truncation to `k`. The unscoped path (`:241`) needs the same over-fetch to have candidates to fuse.
- `src/janbot/store/chroma.py:22` — the `Embedder` seam (unchanged); `:25-38` `ChunkLike`; `:259-266` the return shape `[{id, text, source_path, breadcrumb}]` (unchanged).
- `src/janbot/config.py:60-68,151-164` — a new env knob `JANBOT_RETRIEVAL_MODE` (`dense` default; `hybrid`; unknown values fail fast), following the existing fail-fast pattern; documented beside `README.md:58`'s table.
- `src/janbot/eval/__main__.py:45-55` — `run_params` records the run's config (model_mode, model_snapshot, judge_model, temperature, seed, top_k, program) but **no retrieval mode yet** — this story adds `retrieval_mode` so the hybrid run is comparable to `e635c2bf` (whose params lack the key, marking it the dense reference).
- `src/janbot/pipeline/chat.py:128` — the only production `query` caller (reads `source_path`/`text`); unchanged apart from receiving the configured mode through `api/main.py:97`.
- `tests/test_store_scope.py` (order-asserting: `:55,78,180,197`), `tests/test_ingest_tracer.py:69-83`, `tests/test_ingestion_e2e.py:64-92`, `tests/test_scope.py`, `tests/test_ingest_idempotent.py:192,322` — all stay green with the default `dense`; new tests cover the fusion mode (order, scope-filter interaction, truncation, k=0, determinism, stub-embedder interplay).
- `tests/conftest.py:20-32` — the 64-dim deterministic stub embedder the fusion tests reuse.
- Rank evidence (5.19/2.9, reproduced): item 23 `public-proof-map.org` rank 15 (a URL-list object; the question shares "projects"/"inspect" lexically), item 32 `perl-clojure-gateway.org` rank 15 ("perl"/"clojure" tokens), item 25 `dna-threads.org`/`cpp-memory-allocator.org` absent from the top 30 (weak lexical overlap with "younger engineer").

## Tasks & Acceptance

**Execution:**
- [x] `src/janbot/store/chroma.py` -- a deterministic in-module BM25 (fixed tokenizer, k1/b) + reciprocal-rank fusion of the dense and lexical rankings over the scoped candidate set; over-fetch for the unscoped path -- the lever. *(Done: the `dense` path is byte-identical; `_query_hybrid` over-fetches, scope-filters, fuses, truncates.)*
- [x] `src/janbot/config.py`, `tests/test_config.py`, `README.md` -- the `JANBOT_RETRIEVAL_MODE` knob (default `dense`, fail-fast on unknown values) -- the off-by-default seam, with config coverage matching the existing pattern. *(Done: +10 config tests.)*
- [x] `src/janbot/api/main.py` -- thread the configured mode into `ChatProgram`/`VectorStore` -- the wiring. *(Done.)*
- [x] `src/janbot/eval/__main__.py` -- `run_params` records `retrieval_mode` (and `tests/test_eval_runner.py:461-468`'s params key set is updated) -- the hybrid run is comparable to the dense reference. *(Done.)*
- [x] `tests/test_store_hybrid.py` (or the store test files) -- fusion order vs dense order, scope-filter interaction, truncation, k=0, determinism across two calls, stub-embedder interplay -- prove the mechanism without a model. *(Done: 12 tests + the review's golden pinned-order case.)*
- [x] run the no-model hybrid window probe over the real index -- which of {23, 25, 32} enter the `top_k=4` window under BM25+RRF -- the primary evidence, recorded before the keyed run. *(Done — and corrected in review: the probe initially covered only {23, 25, 32}; the review patch re-ran it over all four diagnosed items and saved `run-7c868e2f-probe.txt`. Items 23 **and** 29 enter the window.)*
- [x] run the single keyed val eval in the hybrid mode against `e635c2bf` (keyed; ~15 answers + ~15 judge calls; hitl) -- the measurement. *(Done: MLflow run `7c868e2f`.)*
- [x] record the result in `epic-ingestion.md` Notes: the before/after table (retrieval_accuracy, retrieval_mrr, citation_correctness, faithfulness, citation_precision), per-item misses before/after, and the 1.5σ floor verdict routed to entry 20 -- the deliverable. *(Done; captured outputs preserved as `run-7c868e2f-output.txt` / `run-7c868e2f-probe.txt`.)*

**Acceptance Criteria:**
- Given the fusion, when the no-model window probe runs over the real index, then it records which of {23, 25, 32} enter the `top_k=4` window **before** the keyed run -- the primary evidence capping the retrieval-driven gain.
- Given the hybrid mode, when a query runs against the fixture index, then the ranking is the deterministic fusion of the dense and lexical rankings, the return shape is unchanged, scope filtering still precedes truncation, and `k` truncation still applies.
- Given the shipped default, when no knob is set, then retrieval behavior is byte-identical to today (the order-asserting store tests pass unchanged).
- Given the hybrid val run, when its MLflow params are read, then `retrieval_mode` and `top_k=4` are recorded, making it comparable to `e635c2bf`.
- Given the hybrid val run, when compared to `e635c2bf`, then before/after `retrieval_accuracy` / `retrieval_mrr` and the transfer metrics `citation_correctness` / `faithfulness` (plus `citation_precision`) are recorded in MLflow.
- Given the measurement, when the verdict is written, then it states whether a gate metric moved beyond the 1.5σ floor (≥ 3 items at n=15) or is within noise and routed to entry 20's breadth decision — item 25's outcome is recorded either way, and on a clear win an explicit adoption recommendation (with the `citation_precision` guard) is recorded for the owner.

## Implementation Notes

- The mechanism: `JANBOT_RETRIEVAL_MODE` (`dense` default / `hybrid`, fail-fast) → `Config.retrieval_mode` → `api/main.py` → `VectorStore(retrieval_mode=…)`. The `dense` path is the existing body byte-for-byte; `_query_hybrid` over-fetches `collection.count()` for **both** scoped and unscoped stores, applies the fail-closed scope filter before ranking, fuses the chroma dense order with the in-module BM25 order (RRF, constant 60), and truncates to `k` with the unchanged return shape. `run_params` records `retrieval_mode`.
- `VectorStore` imports the mode constants from `janbot.config` (stdlib-only module; no import cycle) — single source of truth for the allowed values.
- The measurement: the no-model window probe (primary evidence) then one keyed hybrid val run — MLflow `7c868e2f` (judge `anthropic/claude-haiku-4.5`, `top_k=4`, `retrieval_mode=hybrid`, dataset sha `4656f824…` verified) against `e635c2bf`. Result: `retrieval_accuracy`/`citation_correctness` 0.7333 → 0.8667 (**+2 items** — items 23 and 29 recovered; the probe initially under-reported by checking only {23, 25, 32}), `retrieval_mrr` 0.6667 → 0.8333, `citation_precision` 0.6889 → 0.7556 (no over-citing regression), `public_references` 0.9333 → 1.0000, `faithfulness` 0.7333 with its failing set changed {23, 25, 29, 32} → {19, 23, 25, 32} (item 29 fixed, item 19 "Tell me about yourself" destabilized — net zero). **Verdict: both gate metrics within the 1.5σ ≈ 0.17 (three-item) floor → NO gate movement; routed to entry 20's breadth decision.** The shipped default stays `dense` (ship-semantics decision); no adoption recommendation is indicated at +2 of the needed 3 items.
- Captured evidence preserved beside the Notes: `run-7c868e2f-probe.txt` (the deterministic probe over all four items) and `run-7c868e2f-output.txt` (the keyed run's CLI output).
- Full verification after the review patches: `uv run pytest -q` → **351 passed** (328 prior + 22 hybrid/config + 1 golden pin); the store's order-asserting tests pass unchanged.

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 7 findings: 5 patched, 1 deferred-none (see rows), 1 false:
- the entry-10 note's arithmetic contradicted its own set change ("fixed two … destabilized one" vs {23,25,29,32} → {19,23,25,32}) and its probe sentence claimed a +1 cap the same note revised to +2 — **low / patch** — reworded to one fixed (29), one regressed (19), net zero; the probe now covers all four items (23 and 29 enter) and states the +2 cap consistently.
- the primary-evidence probe under-reported (it covered only {23, 25, 32} while entry 9's evidence already placed item 29 at dense rank 5) — **low / patch** — grouped with the probe-artifact finding: the probe was re-run over all four items, its raw output saved as `run-7c868e2f-probe.txt`, and the note records the corrected +2 cap.
- the probe had no preserved artifact or committed tooling (its numbers existed only as prose) — **low / patch** — grouped above; the raw probe output is now committed beside the note.
- the plan's Execution tasks were unchecked and the notes sections empty although the work was complete — **false** — the diff was captured mid-workflow; this finalize step ticks the tasks and fills the logs.
- the "independent" BM25/RRF reference in `tests/test_store_hybrid.py` mirrors the production formula, so the maths is unpinned against future drift — **low / patch** — a golden pinned-order case on a tiny fixed corpus was added (full independence would need a second implementation, excluded by the no-new-dependency boundary; the docstring says so).
- `src/janbot/eval/__main__.py`'s module docstring still enumerated the recorded config without `retrieval_mode` — **low / patch** — added.
- `CHANGELOG.md` had no Unreleased entry for the `JANBOT_RETRIEVAL_MODE` knob / hybrid retrieval mode — **low / patch** — added, matching the existing entries' style.

## Design Notes

Why hybrid first (of the ticket's three candidates): the embedder swap needs a model download, a dimension-changing **re-index**, and invalidates the embedder-seam assumptions tests rely on; query expansion needs an LM call per question (cost + a new nondeterminism surface). Hybrid needs none of those, is fully deterministic, and targets exactly the observed failure mode — lexical overlap where dense similarity fails (a URL-list object for item 23; the "perl"-distinctive narrative for item 32). RRF (constant 60) fuses the two rankings without score-scale calibration. BM25 parameters fixed (k1=1.5, b=0.75) and the **tokenizer is fixed by spec**: lowercase, runs of `[a-z0-9]+` (the same character class the stub embedder's tokenizer uses), no stemming, no stopword list — determinism by specification, not by accident.

## Verification

**Commands:**
- verify the dataset sha (`sha256sum eval/golden_dataset.yaml` = `4656f824…`, `e635c2bf`'s recorded value) before launching -- a mismatch is a stop.
- the no-model hybrid window probe over `chroma_db` (BM25+RRF, `top_k=4`) -- expected: which of {23, 25, 32} enter the window; the primary evidence recorded before the keyed run.
- `uv run pytest -q` -- expected: green with the default `dense` (order-asserting store tests unchanged) plus the new hybrid tests.
- `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 JANBOT_TOP_K=4 JANBOT_RETRIEVAL_MODE=hybrid OPENROUTER_API_KEY=… uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` (hitl) -- expected: one hybrid val run recorded in MLflow with `retrieval_mode=hybrid` and `top_k=4` in the params.
- compare against `e635c2bf` -- expected: the before/after table, per-item misses before/after, the floor verdict, and (on a clear win) the adoption recommendation.
