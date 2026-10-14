---
id: 2
type: story
title: "Replace ChromaDB with Qdrant as the vector store"
parent: none
covers: []
after: []
refined: false
hitl: false
risk: medium
---

# Replace ChromaDB with Qdrant as the vector store

## Description

Swap the embedded ChromaDB store for a Qdrant service orchestrated by podman-compose: ingestion writes org-derived chunks with Pydantic-validated payload metadata, and DSPy retrieves through Qdrant instead of ChromaDB.

## Acceptance Criteria

Verify: the podman-compose stack starts Qdrant and the API, the corpus is ingested into a Qdrant collection with Pydantic-validated payloads, and `POST /chat` answers from it with citations.

## Boundaries

- Must not change: the `/chat` Pydantic contract, the fail-closed scope filter, the citation path shape, or the DSPy `retrieve → answer + cite` signature.

## References

- source — `qdrant-used.md`
- stack — `_bmad-output/initiative-janbot/spec-janbot/stack.md` (ChromaDB as vector store)
- architecture — `_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md`, AD-2 (isolated AI/vector core)

## Notes

- Unknown: adopting Qdrant overturns the stack's ChromaDB choice; settle it with a superseding ADR before this starts.
- Unknown: which environment this targets — local podman only, or the hosted/deployment environment too.
- Open question: chunk-id and metadata parity with the current store (chunk ids are content-hashes today).
