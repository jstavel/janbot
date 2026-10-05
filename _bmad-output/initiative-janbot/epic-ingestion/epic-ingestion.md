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
3. A path outside `public_profile_org/` is refused, and a private note placed elsewhere changes no retrieval result.
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
