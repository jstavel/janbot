---
title: 'Stable content-hash chunk ids'
type: 'feature'
ticket: 8
created: '2026-10-13'
status: 'done'
baseline_revision: '7904fee265223535f0df03404083f6cc16007503'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** a chunk id is `f"{source}::{ordinal}::{breadcrumb}"` (`src/janbot/ingest/org.py:108`), where `ordinal` is the node's **document-order** position. Inserting or reordering any heading shifts every later ordinal, so the whole tail is re-embedded and delete/re-added — the index churns on an edit that changed nothing in those chunks. Separately, the reconcile decides "which corpus owns a chunk" by testing the stored `source_path` for path-containment (`src/janbot/ingest/__init__.py`), a filesystem-path coincidence rather than stored ownership.

**Approach:** derive each id from the chunk's own content — `f"{source}::{sha256(source, breadcrumb, text)}"` — so a chunk's id depends only on itself, and record a **scope key** (the resolved corpus root) in each chunk's stored metadata so the reconcile deletes by stored scope, not by path coincidence. Existing indexes are rebuilt (id format changes).

## Boundaries & Constraints

**Always:**
- Ids stay **unique within the index**: the hash includes the chunk **text**, so sibling subtrees with identical heading paths but different bodies stay distinct (two existing tests assert this).
- The reconcile keeps its current guarantees: a re-run is idempotent, a removed/renamed subtree leaves no orphan, and a second corpus's chunks are preserved.
- `store/chroma.py` and `ingest/org.py` must not import each other (the existing no-cycle rule).

**Never:**
- No change to the served-surface guarantees (the 503/grounding boundary, citations) and no change to the serve-side startup check semantics.
- Do not change unrelated ids (test/store synthetic chunk ids are arbitrary and stay).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | a heading is inserted **above** an unchanged chunk, re-index | the unchanged chunk's id is unchanged | No error |
| HAPPY | two sibling subtrees, same heading path, different bodies | distinct ids (hash includes the text) | No error |
| EDGE | a chunk's own body is edited | its id changes; old id is deleted, new added, no duplicate | reconcile by scope key |
| EDGE | two corpora indexed into one store | each keeps its chunks; reconcile for corpus A does not delete corpus B's | scope key recorded per chunk |

</frozen-after-approval>

## Code Map

- `src/janbot/ingest/org.py` — build the id from a content hash (`hashlib.sha256`): `f"{source}::{sha256(f'{source}\n{breadcrumb}\n{text}')}"`; drop the `enumerate` ordinal; update the module + `_heading_path` docstrings.
- `src/janbot/store/chroma.py` — the store gains an optional `scope_key` on `upsert` (written into each chunk's metadata) and a `scope_keys()` accessor (`{id: scope_key}`); `upsert`'s signature gains a keyword so existing direct-upsert callers (tests) are unaffected.
- `src/janbot/ingest/__init__.py` — `index_corpus` passes `scope_key=str(root_resolved)` and reconciles by stored scope key: delete stored ids whose `scope_key` equals this corpus's key and whose id is not desired (replacing the `within(root, source)` filter). Update the docstring.
- `tests/conftest.py` — the `chunk_id` oracle fixture is re-implemented for the new format (or replaced by deriving expected ids from `read_org_file`).
- `tests/test_ingest_tracer.py` (`:27,:32` exact strings), `tests/test_ingest_idempotent.py` (all `chunk_id(...)` sites) — expected ids updated; `test_org_chunker.py`/`test_ingestion_e2e.py` need only a check they still derive ids correctly.
- Do not touch: `src/janbot/pipeline/`, `src/janbot/api/`.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/ingest/org.py` -- content-hash ids (no ordinal) -- position-independent identity.
- [ ] `src/janbot/store/chroma.py` -- optional `scope_key` metadata + `scope_keys()` accessor -- stored ownership.
- [ ] `src/janbot/ingest/__init__.py` -- reconcile by scope key -- ownership is stored, not a path coincidence.
- [ ] `tests/conftest.py` + `tests/test_ingest_tracer.py` + `tests/test_ingest_idempotent.py` -- expected ids updated to the new format -- suite stays green and meaningful.
- [ ] `README.md` / `ARCHITECTURE.md` -- note the chunk-id format if they state it -- docs match behaviour.

**Acceptance Criteria:**
- Given a corpus indexed, when a heading is inserted **alongside** (not as an ancestor of) an existing unchanged chunk and the corpus is re-indexed, then that chunk's id is unchanged.
- Given two sibling subtrees with the same heading path and different bodies, when the file is read, then their ids differ.
- Given a corpus indexed, when a chunk's own body is edited and the corpus re-indexed, then the old id is gone, the new id is present, and no duplicate remains.
- Given two corpora indexed into one store, when corpus A is re-indexed, then corpus B's chunks are preserved.
- Given the whole suite keyless, when run, then every test passes.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: content-hash ids (`{source}::{sha256(source, breadcrumb, text)}`), a `scope_key` (resolved corpus root) recorded per chunk with a `scope_keys()` accessor, and reconcile by stored scope key. Tests updated; `test_inserting_heading_above_leaves_chunk_id_unchanged` added. Verified keyless 161 passed, e2e 8 passed.
- 2026-10-13 (review patches): (1) exact-duplicate sibling subtrees now take a `{base}::{n}` suffix so ids stay unique (the content hash alone collided → `DuplicateIDError`); (2) the reconcile falls back to path ownership for chunks with no `scope_key`, so an in-place rebuild prunes a pre-scope-key index's orphans; (3) `_chunk_metadata` docstring corrected. Two regression tests added (`test_identical_sibling_subtrees_get_distinct_ids`, `test_rebuild_prunes_orphans_without_a_scope_key`). Verified keyless 163 passed.

- `org.py`: id is now `f"{located source}::{sha256(f'{source}\n{breadcrumb}\n{text}')}"` via a small `_chunk_id` helper; the `enumerate` ordinal is gone and the module/`_heading_path` docstrings are updated. The digest includes `text`, so identical-breadcrumb siblings with different bodies stay distinct.
- `chroma.py`: `upsert` gained a keyword-only `scope_key: str | None`; a module-level `_chunk_metadata` helper adds `scope_key` to each chunk's metadata only when non-`None` (Chroma rejects `None` values). New `scope_keys() -> {id: scope_key}` returns stored ownership, omitting chunks stored without a scope key. `sources()`/`out_of_scope_sources()`/`query()` are untouched, so serve-side semantics are unchanged.
- `ingest/__init__.py`: `index_corpus` upserts with `scope_key=str(root_resolved)` and reconciles via `store.scope_keys()` (delete stored ids whose stored scope equals this root and that are not desired), replacing the `within(root, source)` path filter. `within` remains for fail-closed file-level reading. Docstring updated.
- Tests: `tests/conftest.py`'s `chunk_id` fixture now takes `(path, breadcrumb)` and rebuilds the hash itself from the reader's text/breadcrumb (independent of production's id construction). `test_ingest_tracer.py` uses the fixture; `test_ingest_idempotent.py` call sites drop the ordinal. Added `test_inserting_heading_above_leaves_chunk_id_unchanged` for the headline acceptance criterion.
- Docs: neither `README.md` nor `ARCHITECTURE.md` state the id format, so no doc change was needed.
- Migration: old indexes carry no `scope_key`, so an in-place re-index cannot attribute/delete their chunks; a rebuild is required (as the Design Notes state). This was verified only via fresh temp indexes.
- Verified: `env -u OPENAI_API_KEY uv run pytest -q` → 161 passed; `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` → 8 passed.

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 2 medium / 2 low / 0 false / 0 maybe-false.** Three patched, one rejected.
- **Identical sibling subtrees collided on one id → `DuplicateIDError` on ingest** — **verdict: medium**. Verified by reproduction: two siblings with the same heading *and* byte-identical bodies hash identically, where the old ordinal kept them unique — a regression. `index_corpus` raised `DuplicateIDError`. **route: patch** — `read_org_file` now suffixes each repeat of a base id (`{base}::{n}`); the repro yields 2 chunks / 2 ids, and `test_identical_sibling_subtrees_get_distinct_ids` locks it.
- **A pre-existing old-format index silently keeps unprunable orphans** — **verdict: medium**. Verified: old chunks carry no `scope_key`, so `scope_keys()` omits them and the reconcile never deletes them; the run reports success and the startup check does not flag it, breaking "removed/renamed leaves no orphan" on the migration path. **route: patch** — the reconcile falls back to path ownership for scope-less chunks; locked by `test_rebuild_prunes_orphans_without_a_scope_key`.
- **`_chunk_metadata` docstring stated a false premise** ("Chroma rejects `None` metadata values") — **verdict: low**. Verified: Chroma silently drops `None` metadata values instead. **route: patch** — docstring corrected.
- **Acceptance criterion 1 read as covering an *ancestor* insertion** — **verdict: low**, **rejected** (the only fix edits this plan). "an unchanged chunk" means a non-ancestor insertion; an ancestor insertion changes the breadcrumb and so the id, by design. Criterion reworded ("alongside") as plan hygiene.

## Design Notes

- Why the hash includes the text, not just `source+breadcrumb`: the ordinal existed because sibling headings collide (`org.py` docstring); two existing tests (`test_duplicate_sibling_headings_get_unique_ids`, `test_duplicate_headings_get_unique_ids`) require identical-breadcrumb siblings with different bodies to get distinct ids. `sha256(source, breadcrumb, text)` keeps that while removing position-dependence.
- Why a stored scope key, not path-containment: `within(root, source)` makes "which corpus owns this chunk" a coincidence of the filesystem path; recording the resolved ingest root at upsert makes ownership explicit and survives a corpus moving.
- Migration: the id format changes, so a previously built index must be rebuilt (the real corpus lives outside the repo; tests build fresh indexes).

## Verification

**Commands:**
- `env -u OPENAI_API_KEY uv run pytest -q` -- expected: every test passes.
- `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` -- expected: the keyless e2e rows pass (the fixture index is rebuilt with the new ids).
