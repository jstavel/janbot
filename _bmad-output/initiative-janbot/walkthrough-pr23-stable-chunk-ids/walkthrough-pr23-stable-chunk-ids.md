# Walkthrough — PR #23: "stable content-hash chunk ids and scope-key reconcile (story 2.8)"

Target: PR https://github.com/jstavel/janbot/pull/23 · branch `ingest-stable-chunk-ids` · commit `b50f3fd`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the content-hash ids
- [x] Block 4 — Slice: the scope-key reconcile
- [x] Block 5 — Periphery

## Status

All blocks accepted: 5 of 5. Review complete: PR #23 squash-merged (`1226379`), story 2.8 marked done; epic-ingestion re-closed as done.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-stable-content-hash-chunk-ids-plan.md](../epic-ingestion/story-stable-content-hash-chunk-ids-plan.md).

> **Problem:** a chunk id is `f"{source}::{ordinal}::{breadcrumb}"`, where `ordinal` is the node's **document-order** position. Inserting or reordering any heading shifts every later ordinal, so the whole tail is re-embedded and delete/re-added — the index churns on an edit that changed nothing in those chunks. Separately, the reconcile decides "which corpus owns a chunk" by testing the stored `source_path` for path-containment, a filesystem-path coincidence rather than stored ownership.
>
> **Approach:** derive each id from the chunk's own content — `f"{source}::{sha256(source, breadcrumb, text)}"` — so a chunk's id depends only on itself, and record a **scope key** (the resolved corpus root) in each chunk's stored metadata so the reconcile deletes by stored scope, not by path coincidence. Existing indexes are rebuilt.

## Block 2 — Broad strokes

A production change across ingestion and the store — two spots:

- [src/janbot/ingest/org.py:99](../src/janbot/ingest/org.py#L99) — `_chunk_id` / `read_org_file`.
- [src/janbot/ingest/__init__.py:20](../src/janbot/ingest/__init__.py#L20) — `index_corpus`; [src/janbot/store/chroma.py:163](../src/janbot/store/chroma.py#L163) — `scope_keys`.

## Block 3 — Slice: the content-hash ids

Each id is `{source}::{sha256(source, breadcrumb, text)}`; the ordinal is gone. The hash covers the text so identical-breadcrumb siblings with different bodies stay distinct, and an exact-duplicate sibling takes a `{base}::{n}` suffix so ids stay unique (the review caught that the bare hash collided → `DuplicateIDError`).

- [org.py:99](../src/janbot/ingest/org.py#L99) — `_chunk_id`; [org.py:111](../src/janbot/ingest/org.py#L111) — `read_org_file` (the duplicate-suffix loop).

## Block 4 — Slice: the scope-key reconcile

`upsert` records an optional `scope_key` in each chunk's metadata; `scope_keys()` returns the stored ownership. `index_corpus` upserts with `scope_key=str(root_resolved)` and deletes stored ids whose scope key equals this root and are no longer desired — falling back to path ownership for chunks with no scope key, so an in-place rebuild still prunes a pre-scope-key index's orphans.

- [chroma.py:122](../src/janbot/store/chroma.py#L122) — `upsert`; [chroma.py:163](../src/janbot/store/chroma.py#L163) — `scope_keys`.
- [ingest/__init__.py:20](../src/janbot/ingest/__init__.py#L20) — `index_corpus`'s reconcile.

## Block 5 — Periphery

- [tests/conftest.py](../../../tests/conftest.py) — the `chunk_id` oracle rebuilt for the new format; [tests/test_org_chunker.py](../../../tests/test_org_chunker.py) and [tests/test_ingest_idempotent.py](../../../tests/test_ingest_idempotent.py) — updated ids + two regression tests.
- [story-stable-content-hash-chunk-ids-plan.md](../epic-ingestion/story-stable-content-hash-chunk-ids-plan.md) — the plan (`built`); Review Triage Log records the three patches.
