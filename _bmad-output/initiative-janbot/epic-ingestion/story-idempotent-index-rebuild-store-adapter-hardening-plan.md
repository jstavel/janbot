---
title: 'Idempotent index rebuild + store adapter hardening'
type: 'feature'
ticket: '5'
created: '2026-10-05'
status: done
baseline_revision: '422e55b932a0eac086f93610bc54dda6f7f9b134'
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

<frozen-after-approval reason="human-owned intent — do not modify unless you explicitly renegotiate">

## Intent

**Problem:** Re-running the ingester must not duplicate or corrupt the index. Chunk ids are stable, so identical re-runs currently upsert in place, but a removed or renamed subtree leaves an orphan chunk, and there is no guarantee the index mirrors the corpus.

**Approach:** Make indexing a **reconcile**: compute the desired chunk set from the corpus, upsert it, then delete collection ids no longer present, so the index equals the corpus after every run. Harden `VectorStore` with `ids()` and `delete(ids)`; keep `upsert` id-based and safe on an existing collection.

## Boundaries & Constraints

**Always:** the collection ends equal to the corpus (no orphans, no duplicates); re-running with an unchanged corpus yields an identical collection (same size, same ids); an empty corpus empties the index; ids stay the stable `<source>::<ordinal>::<breadcrumb>`; stdlib + pinned deps only.

**Never:** no change to `Chunk`, `read_org_file`, or the scope filter; no embedding changes; no DSPy/`/chat`; no new dependency; do not add a second collection or a `where`-prefix scan — M1 indexes one corpus into one collection.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Re-run unchanged | index the same corpus twice | the collection size and id set are identical; no duplicate chunks | No error |
| File removed | index corpus A, delete a file, index again | that file's chunks are gone; the rest remain | No error |
| Heading edited | a subtree's heading/content changes | the changed chunk is replaced; ids still unique; no duplicate | No error |
| Empty corpus | a corpus with no `.org` files, indexed over a populated index | the index is emptied | No error |
| Existing index | indexing into a pre-existing collection | reuses the collection; no error, no corruption | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/store/chroma.py` -- MODIFY. Current: `VectorStore(index_path, embedder)` with `upsert(chunks)` (id-based, no-op when empty) and `query(text, k)`. Add `ids() -> set[str]` (`collection.get(include=[])`) and `delete(ids) -> None` (no-op when empty). Keep `upsert` as-is.
- `src/janbot/ingest/__init__.py` -- MODIFY `index_corpus`: after building `chunks`, `store.upsert(chunks)` then `store.delete(store.ids() - {chunk.id for chunk in chunks})`; return the chunk count.
- `tests/test_ingest_idempotent.py` -- NEW: the five matrix rows, using the deterministic stub embedder and a temp index.
- Reference: `epic-ingestion.md` Done-when 4; `architecture-janbot.md` AD-7/index-as-build-artifact.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/store/chroma.py` -- add `ids()` and `delete(ids)`; keep `upsert` id-based -- hardening
- [ ] `src/janbot/ingest/__init__.py` -- `index_corpus` reconciles (upsert, then delete stale ids) -- idempotency
- [ ] `tests/test_ingest_idempotent.py` -- the five matrix rows -- verification

**Acceptance Criteria:**
- Given the same corpus indexed twice, when compared, then the collection size and id set are identical (no duplicates).
- Given a file removed between runs, when re-indexed, then its chunks are gone and the others remain.
- Given no `.org` files, when indexed over a populated index, then the index is empty.
- Given an existing collection, when indexed again, then it is reused without error or corruption.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Verdict counts: high 1, medium 1, low 2.

- high | patch | `src/janbot/ingest/__init__.py` — a missing/non-directory corpus root returns no files, so the reconcile deletes the whole index (a typo'd `JANBOT_CORPUS_PATH` wipes it) instead of failing closed. Fix: refuse (raise) when the corpus root does not exist or is not a directory.
- medium | patch | `src/janbot/ingest/__init__.py` + `src/janbot/store/chroma.py` — reconcile deletes stale ids against the entire collection, so indexing a second corpus into the same index wipes the first. Fix: scope deletion to the corpus (only stored ids whose `source_path` is within the corpus root).
- low | patch | `tests/test_ingest_idempotent.py` — expected ids use the unresolved `tmp_path`, while production uses `located_path` (parent-resolved), so the asserts break on symlinked temp dirs. Fix: derive expected ids from the located path.
- low | accepted | `tests/test_ingest_idempotent.py` imports ingest/store internals (AD-7 names the HTTP port). Accepted for now: there is no `/chat` endpoint yet, and unit tests of the AI core are appropriate in Milestone 1.

## Design Notes

Reconcile (upsert-then-delete-stale) is chosen over clear-then-add: it never leaves the index empty mid-run, it removes orphans left by deleted or renamed subtrees, and stable ids make the unchanged case a no-op. `ids()`/`delete()` are the minimal store surface this needs; the whole desired set is computed in memory, and the collection is the single M1 corpus so a global stale-id diff is correct here (a `where`-scoped scan is deliberately avoided).

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass
