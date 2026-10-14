---
id: 5
type: story
title: "Index the file root (SYNOPSIS) as a retrievable chunk"
parent: none
covers: []
after: []
refined: true
hitl: false
risk: low
---

# Index the file root (SYNOPSIS) as a retrievable chunk

## Description

The org chunker emitted one chunk per non-root subtree only, so a document's own `:SYNOPSIS:` drawer and any text above its first heading were unreachable by retrieval. A file-root chunk now carries the drawer (the approved `:SYNOPSIS:` among it) and the pre-heading body, under a breadcrumb marker no heading path can collide with.

## Acceptance Criteria

1. **Root chunk carries the drawer and pre-heading text**
   **Given** an org file with a PROPERTIES drawer or text above its first heading
   **When** the file is read
   **Then** a file-root chunk is emitted carrying that content
2. **Empty root yields no chunk**
   **Given** a file whose root has neither drawer nor text
   **When** the file is read
   **Then** no root chunk is emitted
3. **Keyword lines are not prose**
   **Given** `#+TITLE:` and similar keyword lines in the root
   **When** the root chunk text is built
   **Then** those lines are excluded (`#+BEGIN_SRC`/`#+END_SRC` are kept)
4. **Subtree behavior unchanged**
   **Given** any org file
   **When** it is read
   **Then** every non-root subtree chunk and its content-addressed id are unchanged

## Boundaries

- Must not change: existing subtree chunk content or ids, or the fail-closed scope filter.

## References

- code — `src/janbot/ingest/org.py`
- tests — `tests/test_org_chunker.py`
- architecture — `ARCHITECTURE.md`, Key Design Decisions 3

## Notes

- Decision (2026-10-14): implemented and verified (per-file corpus coverage 0.69–0.91 → 1.00); filed as the ticket that was missing for already-applied work.
