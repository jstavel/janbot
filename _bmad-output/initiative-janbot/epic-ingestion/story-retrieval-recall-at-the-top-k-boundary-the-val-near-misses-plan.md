---
title: 'Retrieval recall at the top_k boundary (the val near-misses)'
type: 'feature'
ticket: 9
created: '2026-10-15'
status: 'built'
baseline_revision: 'c9d0620'
route: 'oneshot'
route_source: 'auto'
risk: 'medium'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the 5.19 diagnosis found all four failing val items (union {23, 25, 29, 32}) are retrieval misses — the expected source is in the corpus and indexed but outside the `top_k=4` window (for item 25, two of its three expected sources are; its third, `career-trajectory.org`, was retrieved). Each recovery lever must be measured against the val reference `e635c2bf` before entry 20 decides on breadth.

**Approach:** measure the `top_k` lever with a **single keyed val run at k=6** against `e635c2bf`, and record the result in the epic-ingestion Notes. Retrieval is deterministic, so the **k=30 rank probe is the primary evidence**: item 29's expected source (`vagrant-provisioning.org`) ranks 5th — the only miss `top_k` can recover; items 23/32 (`public-proof-map.org` / `perl-clojure-gateway.org`) rank 15th and item 25's two expected sources are absent from the top 30, so k=5/6/8 are **retrieval-identical** (all recover exactly item 29). The probe therefore caps the **retrieval-driven** gain at **+1 item (~0.067)** — below the 1.5σ ≈ 0.17 (3-item) floor — so `top_k` cannot clear the floor **via `citation_correctness`** (the model cannot cite a source it never retrieved). `faithfulness` is **not** bounded by the probe: k=6 changes the context for all 15 items, so it can move either way, including a regression — which is exactly why the single k=6 run exists: it measures the unbounded part. The embedding/query-side lever — the only one that can recover the other three (its result is entry 20's breadth input) — is filed as **epic-ingestion entry 10**, not built here.

## Boundaries & Constraints

**Always:** exactly one keyed val run, at k=6 against `e635c2bf` on the val split (locked snapshot, judge `anthropic/claude-haiku-4.5`), recorded in MLflow with `top_k` in the params; the k=30 probe recorded as the primary evidence; the transfer metrics are the judge; the result lands in the epic-ingestion Notes.

**Never:** no product code (do **not** change the shipped `DEFAULT_TOP_K`, `config.py`, `README.md`, or `tests/test_config.py`); no embedding/query-side build (entry 10); no dataset change; no gate-rule change; no `/chat` contract change; no optimization stage (8/9 stay gated).

**Decision (Q1=A — build scope):** the `top_k` lever only — the experiment, the measurement, a written result + routing. The embedding/query-side lever is filed as epic-ingestion entry 10, not built here.

**Decision (Q2=B — do not ship the default):** the shipped `DEFAULT_TOP_K` is **not** changed in this story; record only. Rationale: (a) `top_k` cannot clear the floor (Q3); (b) a `DEFAULT_TOP_K` change is product-wide — cost, latency, and the over-citing risk epic-evaluation O2 recorded (`citation_precision` 0.69 → 0.50 under the multi-objective compile); (c) `top_k` is documented as a knob for the optimization stages (epic-evaluation 8/9), which is where a gated default change belongs.

**Decision (Q3=B — one run at k=6):** a single keyed run, at k=6. Rationale: retrieval is deterministic, so the k=30 probe is the primary evidence; the next expected source is at rank 15, so k=5/6/8 are retrieval-identical (all recover exactly item 29). The probe therefore caps the **retrieval-driven** gain at +1 item (~0.067) — below the 1.5σ ≈ 0.17 (3-item) floor — so `top_k` cannot clear the floor **via `citation_correctness`** (the model cannot cite a source it never retrieved); `faithfulness` is **not** bounded by the probe (k=6 changes the context for all 15 items, so it can move either way, including a regression), which is why the single k=6 run exists: to measure the unbounded part. Do not pay for k=6 + k=8.

## Code Map

- `src/janbot/config.py:60,68` — `JANBOT_TOP_K`, `DEFAULT_TOP_K = 4` (the shipped default; **not** changed here — the knob is set via env for the run only); `:151-164` validation.
- `src/janbot/config.py:19`, `README.md:58`, `tests/test_config.py:185-186,202-203` — where the default `4` is documented/asserted (left unchanged this story).
- `src/janbot/store/chroma.py:224-268` — `VectorStore.query`: plain dense `query_embeddings` only; no BM25/hybrid, rerank, MMR or query expansion (entry 10's lever has no seam yet).
- `src/janbot/pipeline/chat.py:118-146` — `ChatProgram(store, top_k, rewriter)`; `top_k` reaches `self._store.query(question, k=self._top_k)` (`:128`); `last_retrieved_sources` (`:124,130,143`); no query-rewriting seam.
- `src/janbot/eval/__main__.py:45-55` — `run_params` records `top_k` (the k=6 run is comparable to `e635c2bf` at top_k=4).
- Rank evidence (a `k=30` probe against `chroma_db` with the production embedder — reproducible, and the primary evidence this story rests on): item 29 `vagrant-provisioning.org` rank 5; items 23/32 rank 15; item 25 `dna-threads.org`/`cpp-memory-allocator.org` absent from the top 30 (`career-trajectory.org` rank 1).

## Tasks & Acceptance

**Execution:**
- [x] run the single keyed val eval at k=6 (real index + operator key; ~15 answers + ~15 judge calls; hitl) -- the measurement: `citation_correctness` / `faithfulness` (+ `citation_precision`) vs `e635c2bf`, confirming no regression. *(Done: MLflow run `c68a9a3e`; aggregates match `e635c2bf` or improve; the per-item faithfulness set changed {23,25,29,32} → {14,23,25,32} — net zero, recorded in the Notes.)*
- [x] record the k=30 rank probe as the primary evidence and the k=6 before/after in the epic-ingestion Notes, with the "within the floor, routed to entry 20" outcome and the pointer to entry 10 -- the deliverable. *(Done: the Measurement bullet in `epic-ingestion.md`; the captured run output preserved beside it as `run-c68a9a3e-output.txt`.)*

**Acceptance Criteria:**
- Given the k=30 probe, when the evidence is written, then it caps the **retrieval-driven** gain at +1 item (only item 29's source enters the window at k ≥ 5), so `top_k` cannot clear the 1.5σ floor **via `citation_correctness`**; and it states that `faithfulness` is unbounded by the probe and is what the k=6 run measures.
- Given the single k=6 val run, when compared to `e635c2bf`, then the transfer metrics `citation_correctness` / `faithfulness` (plus `citation_precision`) are recorded in MLflow and show no regression.
- Given the within-floor result, when the build completes, then it is recorded and routed to entry 20's breadth decision, and the shipped `DEFAULT_TOP_K` is unchanged.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 7 findings: 4 patched, 1 deferred, 2 false:
- per-item evidence for the faithfulness flip is stdout-only (the run persists no per-item artifact; the 5.19 follow-up stays open) — **medium / defer** — fixing `run_eval` is a code change outside this story's frozen "no product code" boundary; the captured CLI output is now preserved beside the Notes as `run-c68a9a3e-output.txt` so THIS measurement's evidence is durable, and entry 10 inherits the artifact follow-up.
- entry 10 was filed before the k=6 run recorded, and the experiment ran while the plan was still `draft` — **low / false** — entry 10's content rests on the k=30 probe + the 5.19 diagnosis (both committed and reviewer-reproduced), not on the un-run experiment; its wording ("the 2.9 experiment and the k=30 probe") was imprecise, and the process lag is noted here.
- AC2's "no regression" is undefined at per-item granularity (the recorded outcome — aggregate Δ 0 with a per-item flip — sits in that gap) — **low / defer** — the aggregate-only reading matched the plan's frozen intent; the per-item flip is recorded in the Notes and carried to entry 10's caution; a built story's frozen AC is not reopened post-hoc.
- both execution task checkboxes unchecked — **low / patch** — ticked with the completion evidence.
- the evidence chain was uncommitted (the note + status bump existed only in the tree; the run's `mlflow.source.git.commit` tag points at a commit without them) — **low / patch** — this finalize commit ties plan status, the Notes entry, and the captured output to the recorded run.
- "any `top_k` caps the gain" overreaches the probed range — **low / patch** — reworded to "within the probed range (k ≤ 30)".
- the Intent's "outside the `top_k=4` window" misstates item 25 (two of three sources out; `career-trajectory.org` retrieved) — **low / patch** — reworded.

## Verification

**Commands:**
- the k=30 rank probe against `chroma_db` with the production embedder (reproducible) -- the primary evidence: item 29 rank 5, items 23/32 rank 15, item 25 absent from the top 30.
- `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 JANBOT_TOP_K=6 OPENROUTER_API_KEY=… uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` (hitl) -- expected: one k=6 val run recorded in MLflow with `top_k=6` in the params.
- compare the k=6 run against `e635c2bf` -- expected: the transfer metrics with no regression and the within-floor verdict.
- `uv run pytest -q` -- expected: green, unchanged (no code touched).
