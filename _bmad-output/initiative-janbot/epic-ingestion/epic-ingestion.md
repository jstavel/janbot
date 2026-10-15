---
tracker_id: ""
key: ""
type: epic
title: "Org-mode ingestion & fail-closed scope"
parent: initiative-janbot
covers: ["CAP-4", "CAP-5"]
after: []
assignee: ""
risk: medium
status: done
---

# Org-mode ingestion & fail-closed scope

## Description

The owner's public org-mode corpus is parsed into semantically intact chunks and indexed into ChromaDB — and only documents under `public_profile_org/` are ever indexed. `orgparse` reads each file; chunking produces one unit per org subtree (heading + body + PROPERTIES + LOGBOOK + tags + children) carrying a breadcrumb of parent headings; a fail-closed scope filter refuses any path outside the whitelist. This delivers the retrieval corpus the RAG pipeline needs.

## Outcome

Running the ingester over `public_profile_org/` yields a queryable ChromaDB index of the owner's public profile, with private notes provably excluded — the spec's CAP-4 and CAP-5.

## Requirements

- CAP-4: Only documents under the designated public profile folder are indexed; private notes are excluded (fail-closed). (`spec-janbot.md`, Capabilities)
- CAP-5: org-mode hierarchical semantics are preserved during ingestion so answers respect heading structure, properties and tags. (`spec-janbot.md`, Capabilities)

## Done when

1. The ingester parses representative `.org` files into subtree chunks with correct heading breadcrumbs, properties, tags and child content.
2. A ChromaDB collection is populated with embeddings for the public corpus and is queryable.
3. A path outside `public_profile_org/` is refused, and a private note placed elsewhere changes no retrieval result. (Containment is decided by *located* path: a symlinked public file is in scope even when its target lives outside the root, whereas a path located outside the root is refused.)
4. Re-running the ingester does not duplicate or corrupt the index.

## Boundaries

`ingest/` and `store/` only: the org reader, the subtree chunker, the scope filter, and the ChromaDB/embedding adapter. Not the DSPy answer pipeline (`epic-rag-chat`); not the endpoint. Consumes the ChromaDB and `all-MiniLM-L6-v2` dependencies wired by `epic-foundation`.

## References

- parent — `../initiative-janbot.md`, section Requirements
- spec — `../spec-janbot/spec-janbot.md`, capabilities CAP-4 and CAP-5
- architecture — `../architecture-janbot/architecture-janbot.md`, AD-3 (fail-closed boundary), AD-6 (subtree chunking)
- constraint — `../spec-janbot/spec-janbot.md`, Constraints (only `public_profile_org/`; no naive splitters)

## Notes

- Decision (2026-10-05, #1a — corpus-root ownership): the corpus root is configuration. `JANBOT_CORPUS_PATH` (default `public_profile_org`) points at the public scope folder; the ingestion scope filter is fail-closed against that configured root, refusing any path outside it.
- Decision (2026-10-05, public-scope mechanism): the public scope is a dedicated folder, `~/org/h1_horizon/public_profile_org/`, containing the public profile files (symlinked from their real locations in `~/org`, which also holds private notes). The real corpus stays outside the repository.
- Decision (2026-10-05, test corpus): tests use a synthetic fixture under `tests/fixtures/public_profile_org/`; the real corpus is never committed.
- Decision (2026-10-05, embeddings): use ChromaDB's built-in default embedding (`all-MiniLM-L6-v2`) behind an injectable seam, so tests run with a deterministic stub (fast, offline) and production uses the default.
- Decision (2026-10-05, sequencing): entry 1 is an opening prerequisite carrying the retrospective follow-ups (#1, #3, #5, #6); entry 2 is the tracer bullet (thinnest path through every layer). Entries 3 and 4 touch different files (`ingest/org.py`, `ingest/scope.py`) and may run in parallel; entry 2 owns the shared store setup.
- Decision (2026-10-05, scope): retrospective item #2 (production routing, `temperature`, `top-k` on `Config`) is deferred to `epic-rag-chat`, not this epic.
- Decision (2026-10-05, slicing): the DSPy signature's citation contract is a downstream concern; this epic's output is the indexed chunks plus their source-path metadata, which citations will read.
- Decision (2026-10-12, symlink-by-location reconciliation): containment is decided by *located* path, not target resolution — a symlinked public file under the root is in scope; a path located outside the root is refused. `spec-janbot.md` CAP-4 and this epic's Done when 3 are now worded to match, closing the retrospective's wording item. (Store scope ownership, the DW3 evidence-strength gap and citation/id concerns are tracked as carries to `epic-rag-chat`.)
- Decision (2026-10-12, closure): epic accepted `done` with the above carries; child tickets `2.1`–`2.7` all `done`, and the payload-stability remediation (`test_rerun_preserves_documents_and_embeddings`, `test_rerun_repairs_corrupted_payload`) closes the retrospective's "corrupt" clause.
- Decision (2026-10-13, reopened): entry **8** (stable content-hash chunk ids) added from `deferred-work.md` ("Sweep decisions", chunk-id stability). The epic is reopened `in-progress` until it lands; the earlier `done` closure covered entries 1–7.
- Note (2026-10-15, entries 9/10 — revisits): entries 9 (the `top_k` experiment) and 10 (the embedding/query-side lever) are revisits driven by the epic-evaluation diagnosis (entry 5.19), which routed all four val retrieval misses to this epic. Their entry-level `after` edges into epic-evaluation are legitimate revisits — a later phase feeding an earlier epic, not a cycle; no epic-level coupling is declared, because the epic `after`/`needs` model encodes build order and declaring it would encode a false order.
- Measurement (2026-10-15, entry 9 — the `top_k` lever): a single keyed val run at `JANBOT_TOP_K=6` (MLflow run `c68a9a3e`, judge `anthropic/claude-haiku-4.5`, dataset sha `4656f824…` unchanged) against the reference `e635c2bf` (k=4). Primary evidence first — the deterministic **k=30 rank probe**: `vagrant-provisioning.org` ranks **5th** (the only miss `top_k` can recover), `public-proof-map.org` and `perl-clojure-gateway.org` rank **15th**, and item 25's `dna-threads.org`/`cpp-memory-allocator.org` are absent from the top 30 — so within the probed range (k ≤ 30; ranks beyond 30 were never probed) k=5/6/8 are retrieval-identical, and any `top_k` within that range caps the **retrieval-driven** gain at +1 item (~0.067), below the 1.5σ ≈ 0.17 (3-item) floor. The k=6 run confirmed it: `retrieval_accuracy` 0.7333 → 0.8000 and `citation_correctness` 0.7333 → 0.8000 (both **+1 item — item 29 recovered**, exactly the probe's prediction), `retrieval_mrr` 0.6667 → 0.6800, `citation_precision` 0.6889 → 0.7222 (**no over-citing regression** — the O2 fear did not materialize here), `public_references` 0.9333 and `answer_coverage` 1.0 unchanged. `faithfulness` — the term the probe cannot bound — stayed 0.7333 but its **failing set changed**: {23, 25, 29, 32} → {14, 23, 25, 32}: item 29 turned faithful (recovered) while item 14 ("Do you have security or PKI experience?") **regressed** to hallucinated — the larger window fixed one item and destabilized another, net zero. (Per-item evidence: the captured CLI output is preserved beside this note as `run-c68a9a3e-output.txt` in the same folder — stdout only, since `run_eval` persists no per-item artifact; the per-item-artifact follow-up recorded in epic-evaluation 5.19 remains open and entry 10 inherits it.) **Verdict: within the 1.5σ floor on both gate metrics (Δ +1 item ≈ 0.067 < 0.17; `faithfulness` Δ 0) — no gate movement; the within-noise result is recorded and routed to epic-evaluation entry 20's breadth decision.** The shipped `DEFAULT_TOP_K` stays 4 (`top_k` is the optimization stages' knob, entries 8/9); the decisive lever for the remaining misses {23, 25, 32} is entry **10** (the embedding/query-side lever), and item 14's flip is a caution entry 10 should carry: changed retrieval windows can destabilize previously-faithful items, so its measurement must watch per-item flips, not just aggregates.
