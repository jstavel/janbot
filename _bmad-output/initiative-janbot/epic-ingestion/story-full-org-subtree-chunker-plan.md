---
title: 'Full org subtree chunker'
type: 'feature'
ticket: '3'
created: '2026-10-05'
status: 'built'
baseline_revision: '2f4bc211e72c4f13d066d6bfb860ba1ecfcef06e'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-janbot/epic-ingestion/epic-ingestion.md'
  - '_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The tracer chunker only emits one chunk per *top-level* subtree and drops PROPERTIES; it does not preserve the org hierarchy the answers must respect (AD-6), so nested content is not independently retrievable and properties are lost.

**Approach:** Chunk **every** org subtree at any depth: one `Chunk` per non-root node whose text carries the heading, tags, PROPERTIES, the body (LOGBOOK + text) and all descendant text, with a `breadcrumb` of the full heading path (including the node's own heading). Ids stay unique per file via a document-order ordinal. No naive text splitting.

## Boundaries & Constraints

**Always:** `orgparse` only; one chunk per subtree node (top-level and nested); text includes heading + tags + PROPERTIES + body/LOGBOOK + descendant content; breadcrumb is the full heading path including self; ids unique within a file (source + ordinal + breadcrumb); absolute `source_path`; stdlib + pinned deps only.

**Never:** no scope/symlink policy (entry 2.4); no embedding changes; no idempotency guarantee (entry 2.5); no DSPy/`/chat`; no new dependency; do not change `Chunk`'s public fields or `VectorStore`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Nested subtree | a node with a parent heading + PROPERTIES + tag + a child | one chunk with breadcrumb `Parent > Child`, the properties, the tag and the child's content | No error |
| Every level | a 3-level tree | one chunk per node (every non-root node) | No error |
| Duplicate headings | two sibling `* Notes` | two chunks, distinct ids | No error |
| Empty node | a heading with no body/children | the heading-only text is produced (or the empty chunk skipped) | No error |
| Properties/logbook | PROPERTIES drawer + LOGBOOK drawer | properties in the chunk text; LOGBOOK retained in the body | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/ingest/org.py` -- MODIFY. Current: `Chunk(id, text, source_path, breadcrumb)`, `_heading_path` (full path incl. self), `_subtree_text` (heading+tags+body+children), `read_org_file` (top-level nodes only, id `src::ordinal::breadcrumb`). Change: `read_org_file` recurses over every non-root node; text also includes `node.properties` (PROPERTIES drawer); keep id scheme.
- `tests/test_ingest_tracer.py` -- MODIFY. Its `test_read_org_file_chunks_top_level_subtrees` asserts `len == 2` and breadcrumb `About`; with full chunking the fixture yields one chunk per node (4). Update the count/assertions to the new semantics (or rename to reflect full chunking).
- `tests/test_org_chunker.py` -- NEW (preferred) OR add cases to the tracer test file: nested breadcrumb, properties, tags, child content, duplicate-heading uniqueness, 3-level depth.
- Reference: `architecture-janbot.md` AD-6 (subtree chunking); `epic-ingestion.md` Done-when 1.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/ingest/org.py` -- recurse to every non-root node; include `node.properties` in chunk text; keep breadcrumb (incl. self) and the ordinal-unique id -- covers CAP-5
- [ ] `tests/test_org_chunker.py` (and update `tests/test_ingest_tracer.py` expectations) -- matrix rows -- verification

**Acceptance Criteria:**
- Given a nested node with a parent heading, PROPERTIES, a tag and a child, when read, then one chunk's breadcrumb is `Parent > Child`, its text contains the property value, the tag and the child's text.
- Given a 3-level tree, when read, then there is one chunk per non-root node.
- Given two sibling subtrees with the same heading, when read, then their chunk ids differ.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Verdict counts: low 5.

- low | patch | `src/janbot/ingest/org.py` — a non-root node with an empty heading but tags (`* :work:`) renders to empty text and is dropped, losing the tag (breaks "one chunk per node"). Fix: render tags even when the heading is empty.
- low | accepted | `src/janbot/ingest/org.py` — `node.tags` is inherited, so a child chunk shows ancestor tags. Accepted as intended org semantics (tag inheritance gives useful retrieval context); a test now pins it.
- low | accepted | `src/janbot/ingest/org.py` — orgparse normalizes PROPERTIES values (`:Effort: 1:10` → `70`); the value is semantically preserved, so accepted as-is.
- low | patch | `tests/test_org_chunker.py` — the "empty node" case used a titled heading and never exercised an untitled one; add an untitled-tagged case.
- low | patch | `tests/test_org_chunker.py` — tag semantics (inherited vs own) were unpinned; add a test documenting inherited tags.

## Design Notes

Each node's text includes its whole subtree (descendants), matching AD-6 ("heading + body + PROPERTIES + LOGBOOK + tags + children"); the intentional overlap lets retrieval return either the broad ancestor or the focused child. `breadcrumb` includes the node's own heading (as in the tracer) so a top-level node still has a meaningful, unique breadcrumb; the per-file ordinal keeps ids unique when sibling headings collide. PROPERTIES come from `node.properties`; LOGBOOK is retained inside `node.get_body("raw")`.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass
