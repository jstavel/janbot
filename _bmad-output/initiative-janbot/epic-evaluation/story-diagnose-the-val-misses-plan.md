---
title: 'Diagnose the val misses'
type: 'feature'
ticket: 19
created: '2026-10-15'
status: done
baseline_revision: 'cc2df67'
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

**Problem:** the gate said "no decision" (underpowered at n=15), but before the dataset is grown (entry 20), nobody knows **why** the ~4 failing val items fail — growing blindly could bake corpus gaps into more items instead of fixing retrieval or program behavior.

**Approach:** re-run the val baseline with the config **read from run `e635c2bf`'s recorded params** (`program`, `judge_model`, `top_k`, `dataset_sha256`; a dataset-sha mismatch is a **stop**), capture the per-item `retrieval:` / `citation:` / `judge:` / `failed:` output the CLI prints (per-item detail is **not** recorded in MLflow), and classify every failing item by **causal precedence** — what retrieval returned first: **(a) corpus gap** (the expected source is absent or does not contain the expected answer), **(b) retrieval miss** (the expected source is in the corpus but not among the retrieved top_k), **(c) program error** (only when the expected source **was** in the retrieved top_k and the answer is still declined / mis-cited / unfaithful). Write the diagnosis into `epic-evaluation.md` Notes, routing each class to its owning epic. Each metric's failing set is reconciled **separately** (retrieval_accuracy and faithfulness are both 4/15 but may be different items); the report carries the **union** (which may exceed 4 items).

## Boundaries & Constraints

**Always:** the diagnosis run pins the config read from run `e635c2bf`'s record (`program`, `judge_model`, `top_k`, `dataset_sha256`) — a dataset-sha mismatch is a **stop**, never a diagnosis on changed data; every failing item named with exactly one class, chosen by causal precedence (retrieval outcome first); each metric's failing set reconciled separately with the union reported; the written diagnosis lands in the epic Notes.

**Never:** no dataset edit (entry 20 owns data); no change to `src/janbot` (this is diagnosis, not a fix); no gate-rule change; no optimization stage (8/9 stay gated).

## Code Map

- `src/janbot/eval/__main__.py:157-190` — the per-item output lines to capture (`retrieval:`, `citation:`, `judge:`, `failed:`, `reference:`) and the metric summary; per-item detail is printed, never recorded.
- `mlflow.db` run `e635c2bf` — the reference to **read the config from** (`program=baseline`, `judge_model=anthropic/claude-haiku-4.5`, `top_k=4`, dataset sha `4656f824…`); its metrics retrieval_accuracy / citation_correctness / faithfulness are all 0.7333 (n=15), answer_coverage 1.0.
- `public_profile_org/` — the corpus objects to inspect when classifying (does the expected source actually contain the answer?).
- `chroma_db/` — the owner's real index (the baseline's substrate); used as-is, not rebuilt.
- `epic-evaluation.md` Notes — where the written diagnosis lands (one dated entry).

## Tasks & Acceptance

**Execution:**
- [x] read the config from run `e635c2bf` (program, judge_model, top_k, dataset_sha256); **stop if the dataset sha differs**; run the diagnosis eval with that config (`python -m janbot.eval --dataset eval/golden_dataset.yaml --split val`, real index, key; hitl: needs index + key, ~15 answers + ~15 judge calls) -- the failing-item capture. *(Done: sha `4656f824…` matched — no stop; run `62e44e56` reproduced the reference exactly.)*
- [x] classify each failing item by causal precedence (a) corpus gap / (b) retrieval miss / (c) program error — checking what retrieval returned before anything else -- the diagnosis. *(Done: all four are (b); zero (a), zero (c).)*
- [x] write the diagnosis into `epic-evaluation.md` Notes: the per-item cause table, each metric's failing set reconciled separately + the union, and the routing (data → epic-evaluation; behavior → epic-ingestion / epic-rag-chat) -- the deliverable.

**Acceptance Criteria:**
- Given run `e635c2bf`'s recorded config, when the diagnosis run is launched, then it uses that program/judge_model/top_k/dataset sha; a dataset-sha mismatch stops the diagnosis.
- Given the diagnosis run, when its output is read, then every failing item has a named cause and exactly one class, chosen by causal precedence (a retrieval-caused decline/mis-citation is (b), never (c)).
- Given the classification, when the per-metric failing sets are summed, then retrieval_accuracy's and faithfulness's sets are reported **separately** (4/15 each at 0.73) with their **union** (which may exceed 4 items).
- Given the epic Notes, when the diagnosis is read, then each class is routed to its owning epic and the routing names the concrete next artifact (dataset item fix vs chunking/retrieval change vs program behavior).

## Implementation Notes

Started oneshot: an analysis story — no product code, one keyed CLI run plus a written epic-Notes entry.

- The dataset-sha check passed (`4656f824…` = the run record's), so the diagnosis ran: `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` → MLflow run `62e44e56` (15/15 judged). It **reproduced `e635c2bf` exactly**: every metric identical (0.7333 ×3, 0.9333, 0.6667), and the same four items fail.
- Classification evidence: the captured per-item CLI output (retrieval/citation/judge lines) plus a direct `VectorStore.query(k=15)` rank probe against the owner's `chroma_db` with the production embedder. All four failures are (b) retrieval miss — two rank-15 cases, one rank-5 (one slot below top_k=4), one multi-source case with two of three expected sources absent from the top 15.
- `uv run pytest -q`: 328 passed, unchanged (no code touched).

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 6 findings: 5 real (all patched), 1 false:
- the failing items were labelled with 0-based dataset indices while the epic's other item reference is 1-based — **low / patch** — the base is now stated explicitly in the Notes entry.
- the (c)-exclusion rationale ("in all four cases it was not [retrieved]") contradicted item 25, whose third expected source WAS retrieved — **low / patch** — reworded per-item: the three single-source items missed their only expected source; the multi-source item missed two of three.
- the per-metric failing sets were collapsed to "the same 4" instead of being reported separately as the AC requires — **medium / patch** — each metric's set is now listed explicitly from the captured run output, with the caveat that identity was observed, not guaranteed (the judge treats omission as faithful).
- the routing said "nothing to dataset authoring" while the same sentence carried authoring guidance for entry 20 — **low / patch** — the fix-routing (epic-ingestion) is now separated from the authoring guidance (entry 20), labelled as not a fix for these four.
- the rank evidence (15th / 5th / not-in-top-15) had no recorded provenance — **low / patch** — a provenance line names the direct `VectorStore.query(k=15)` probe (reproducible).
- the plan file appeared in a pre-execution state beside the finished deliverable — **false** — the diff was captured mid-workflow; this finalize step ticks the tasks and sets `built`.

## Design Notes

Classification rubric — **causal precedence**: the class is decided by what retrieval returned, checked before the program's behavior:
- **(a) corpus gap** — the expected source is absent from `public_profile_org/`, or the source does not actually contain what the golden item expects — a data defect, routed back to epic-evaluation (entry 20 authoring).
- **(b) retrieval miss** — the expected source's content IS in the corpus (and indexed) but was **not among the retrieved top_k** for that question — routed to epic-ingestion (chunking/embedding/top_k) or the store.
- **(c) program error** — **only** when the expected source WAS among the retrieved top_k and the answer is still declined (`status=insufficient`), mis-cited, unfaithful, or a fabricated-citation refusal. Because the baseline has `answer_coverage = 1.0` (every item answered), a decline/mis-citation caused by a retrieval miss must be classified (b), not (c) — otherwise every failing item would be tagged a program error and routed to epic-rag-chat, which is exactly the misrouting this story exists to prevent.

Citation misses inherit their cause from the item's retrieval outcome (a retrieval miss usually forces a citation miss or a decline); they are not counted as a separate class. Each metric's failing set is reconciled separately (retrieval_accuracy and faithfulness are both 4/15 but may name different items); the report carries the union.

**Follow-up for entry 20 (recorded here):** this diagnosis needs a fresh keyed run only because `run_eval` persists params + dataset + split manifest + metrics but **not** per-item outcomes. Entry 20 should log the per-item outcomes as an MLflow artifact so a future diagnosis reads the recorded run instead of re-running it.

## Verification

**Commands:**
- read the run record first: `mlflow.db` run `e635c2bf` (program, judge_model, top_k, dataset_sha256); a dataset-sha mismatch is a stop.
- `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 OPENROUTER_API_KEY=… uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` (hitl) -- expected: a baseline val run whose metric summary is captured; the `retrieval:`/`citation:`/`judge:`/`failed:` lines name every failing item.
- Manual: the epic Notes entry exists with the per-item cause table (causal precedence), the two per-metric failing sets + their union, and the routing; `uv run pytest -q` -- expected: green, unchanged (no code touched).
