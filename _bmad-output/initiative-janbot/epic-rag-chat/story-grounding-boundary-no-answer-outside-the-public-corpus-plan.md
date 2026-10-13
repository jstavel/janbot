---
title: 'Grounding boundary: no answer outside the public corpus'
type: 'feature'
ticket: 6
created: '2026-10-13'
status: 'built'
baseline_revision: '3d64f58081ddb6aad7c0f483efeb497555d52abd'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Retrieval is global top-k. `VectorStore.query` passes no scope filter (`src/janbot/store/chroma.py:135-158`), so any stored chunk — including one upserted with an out-of-corpus `source_path` — is retrievable. The only thing standing between it and an answer is downstream, at derivation time: the citation rewriter refuses an out-of-root chunk and the request 500s (`src/janbot/pipeline/chat.py:58-75,100-114`). That is a refusal *after* the content has already entered the prompt context; the guarantee rests on the rewriter, not on the store boundary, and epic Done-when 5 (CAP-1: no answer from outside `public_profile_org/`) wants the store to carry it. The suspended carry in `deferred-work.md` assigns this story the store scope ownership.

**Approach:** Give the store a corpus scope at construction, fed the already-absolute `Config.corpus_path`. A scoped `query` returns up to `k` chunks that all lie within scope — it over-fetches ranked candidates and filters to scope before truncating to `k` — so an out-of-scope chunk can never enter retrieval, the prompt, or a citation. The pipeline rewriter stays as a second, fail-closed guard.

## Boundaries & Constraints

**Always:**
- Scope is configuration-derived: the store is given the corpus root from `Config.corpus_path`; nothing hardcodes a root and no branch selects scope by caller identity.
- Every chunk a scoped `query` returns lies within the scope; out-of-scope chunks are never returned, so they never reach the prompt or a citation.
- `VectorStore.query` keeps its return shape (`id`/`text`/`source_path`/`breadcrumb`); an unscoped store (scope unset) behaves exactly as today.
- Fail-closed: a chunk whose `source_path` is missing or cannot be judged to lie in scope is excluded.
- Preserve story 3.2/3.3/3.4/3.5 pins: the contract, the `janbot.store`-before-`dspy` import order, the 422/503/500 envelope shapes, the citation rewriter, and the seed/config behaviour.

**Never:**
- No changes to `ingest/` (fail-closed indexing is already delivered; chunk-id stability is outside this epic).
- No change to `corpus_relative` or the derived-from/uncited-answer rejection — that is story 3.4, kept as the second guard.
- No metadata rewrite or re-ingestion, no second collection, no new contract fields or routes.
- Do not make `scope` a required constructor argument: `ingest` constructs a store without one (`src/janbot/ingest/__init__.py:49`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | scoped store, corpus of public chunks | up to `k` chunks, all in scope | No error |
| EDGE | scoped store, an out-of-scope chunk ranks highest | it is excluded; public chunks returned instead | No error |
| EDGE | scoped store, only out-of-scope chunks | `query` returns `[]` | (port: empty retrieval → 503) |
| EDGE | unscoped store (`scope` unset) | identical to today's global top-k | No error |
| EDGE | scoped, chunk with no `source_path` | excluded | No error |
| PORT | foreign + public both indexed | 200, citing only the public source | No error |
| PORT | foreign-only index | no answer from foreign content | 503, `{"detail"}` envelope |

Decision (2026-10-13): the scope is constructor-level — `VectorStore(index_path, embedder, scope=corpus_root)`, set once at `src/janbot/api/main.py:59` from the absolute `Config.corpus_path` (option A). The out-of-scope-only case becomes 503 (empty retrieval), and the existing out-of-corpus 500 test is updated to the new boundary (foreign-only → 503, foreign + public → 200 citing only the public source), with the rewriter kept as a backstop (option A).

Decision (2026-10-13, review): the story-3.3 sourceless-chunk port pin (500) yields to the store boundary — a chunk with no `source_path` is excluded by the scope, so a sourceless-only index is empty retrieval → 503 with the existing `0 chunks … corpus` detail. 500 remains reserved for model-output integrity failures (uncited/unverifiable answers). Confirmed by the human during review.

</frozen-after-approval>

## Code Map

- `src/janbot/store/chroma.py` — `VectorStore.__init__` (`:59-66`) gains an optional `scope: str | Path | None = None`, stored resolved once. `query` (`:135-158`) over-fetches ranked candidates (`n_results` = the collection count when scoped) and filters to scope before truncating to `k`; the returned dict shape is unchanged. Add a small **local** containment helper — do NOT import `janbot.ingest.scope`: `ingest/__init__.py:9` already imports `janbot.store`, so that import would be circular. Mirror its semantics (resolved relative-root containment) for `source_path`.
- `src/janbot/api/main.py` — `:59` pass `scope=config.corpus_path` (already absolute/resolved) to `VectorStore`.
- `src/janbot/store/__init__.py` — exports unchanged; only the `VectorStore` signature grows an optional argument.
- `tests/test_store_scope.py` (new) — store-level rows: unset scope = global top-k; scoped excludes an out-of-scope chunk; scoped with only out-of-scope returns `[]`; missing `source_path` excluded. Reuse the conftest `embedder` fixture, direct `upsert`, and a small chunk stand-in.
- `tests/test_chat.py` — update `test_chat_source_outside_corpus_root_is_refused_with_500_envelope` (`:428-447`) to the new boundary; add a port row for foreign + public → 200 citing only the public source. Keep the `ForeignChunk`/`SourcelessChunk` stand-ins (`:52-77`).
- `README.md` / `ARCHITECTURE.md` — one line each: retrieval is scoped to the corpus at the store boundary (`ARCHITECTURE.md:83` currently claims "Collection per domain scope", which is untrue today).
- Do not touch: `src/janbot/ingest/`, `src/janbot/pipeline/chat.py`, `src/janbot/api/contract.py`, `src/janbot/config.py`.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/store/chroma.py` -- add optional `scope`, over-fetch + filter in `query`, local containment helper -- the scope/top-k guarantee lives at the store boundary.
- [ ] `src/janbot/api/main.py` -- pass `config.corpus_path` as the store scope -- scope becomes configuration.
- [ ] `tests/test_store_scope.py` -- store-level matrix rows -- the boundary is proven at the store.
- [ ] `tests/test_chat.py` -- update the foreign 500 row; add the foreign+public port row -- the port behaviour matches the new boundary.
- [ ] `README.md` / `ARCHITECTURE.md` -- document the store scope -- docs match behaviour.

**Acceptance Criteria:**
- Given a scoped store and an indexed corpus, when a chunk outside the corpus root is also stored and ranks highest, then `query` never returns it.
- Given a scoped store whose collection holds only out-of-scope chunks, when `query` runs, then it returns an empty list.
- Given an unscoped store, when `query` runs, then behaviour is identical to today's global top-k.
- Given a scoped app with one public and one foreign chunk indexed, when a question is posted, then it returns 200 citing only the public source.
- Given the full suite, when run, then every 3.2/3.3/3.4/3.5 pin passes unchanged.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: Implemented per Code Map. `src/janbot/store/chroma.py`: `VectorStore.__init__` gains optional `scope`, stored resolved once; new module-local `_within_scope(scope, source_path)` mirrors `ingest.scope.within` (no import — avoids the `ingest`→`store` cycle) and is fail-closed on a missing/unjudgeable path; `query` over-fetches (`n_results = collection count` when scoped) and filters to scope before truncating to `k`, return shape unchanged. `src/janbot/api/main.py`: `VectorStore(..., scope=config.corpus_path)`. `tests/test_store_scope.py` (new, 5 rows: unscoped global top-k; out-of-scope ranked highest excluded; only-out-of-scope → `[]`; missing `source_path` excluded; filter-before-truncate keeps `k` in-scope). `tests/test_chat.py`: foreign-only row updated to the store boundary (503, foreign path never emitted); new foreign+public row (200, cites only the public source). README/ARCHITECTURE document the store scope. Full suite: 125 passed.
- 2026-10-13: Deviation forced by the frozen matrix — the ALWAYS rule "a chunk whose `source_path` is missing ... is excluded" and the "scoped, chunk with no `source_path` → excluded" row mean a sourceless-only index reaches retrieval as empty, so the port row for the sourceless chunk moves from 3.3's 500 to 503 (empty retrieval). The `{detail}` envelope shape is unchanged (422/503/500) and the pipeline's `UnattributableContext` instrument stays as defence-in-depth; only that one port row's status moved. The task list named only the foreign-row update, but this row necessarily follows the frozen boundary.


## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 1 medium / 2 low / 0 false / 0 maybe-false.** One finding needs a human ruling (a pinned 3.3 behaviour changed); two are patches.
- **3.3 sourceless-chunk port pin flipped 500 → 503** (`tests/test_chat.py:298`) — **verdict: medium**. Verified: story 3.3's frozen AC pins "an indexed chunk without `source_path` → 500" (`story-full-pydantic-contract-error-envelope-plan.md:79`), and this story's frozen matrix row "scoped, chunk with no `source_path` → excluded" implies the port case becomes empty retrieval → 503. The two frozen intents conflict for this one row; the flip follows 3.6's matrix but was not surfaced in the human-owned intent (the 3.6 decision 2A named only the foreign row). **route: intent_gap** — needs the human to confirm the 3.3 pin yields to the 3.6 boundary.
- **`_within_scope` raises on an unjudgeable (non-str) `source_path`** (`src/janbot/store/chroma.py:54`) — **verdict: medium**. Verified by the reviewer (live: `source_path=123` → `TypeError` from `Path(source_path).parts` *outside* the try). Chroma metadata admits non-str and `upsert` stores `source_path` verbatim, so the fail-closed rule "cannot be judged … is excluded" is violated and the `TypeError` escapes the route's `ValueError` mapping. **route: patch** — guard non-string/missing inside the fail-closed branch.
- **Scoped `query(k=0)` returns every in-scope chunk** (`src/janbot/store/chroma.py:203`) — **verdict: low**. Verified: the truncation check runs after append, so `k=0` never breaks; contract says "up to `k`". Not reachable via the app (`Config` rejects `top_k < 1`) but `query` is public API. **route: patch** — return `[]` for `k <= 0`.


## Design Notes

- Why the store and not the pipeline: the carry wording and epic lane note (`epic-rag-chat.md:54-55`) place the boundary in `store/`; a scope filter at the store means out-of-scope content never reaches the prompt context at all, whereas the rewriter only refuses it at citation time.
- Why over-fetch rather than a Chroma `where`: Chroma 1.5.9's `where` has no path-prefix operator (`$contains` is a fragile substring), so containment against an absolute `source_path` cannot be expressed in the query. Over-fetch ranked candidates, filter with path containment, truncate to `k`.
- Why fetch the whole ranked set when scoped: it gives a true top-`k`-within-scope guarantee; the corpus is a small personal org tree, so the cost is bounded. If a large corpus later makes this visible, narrowing the fetch is a deferrable optimization, not a correctness issue.
- Why a local helper, not `ingest.scope.within`: importing it would be circular (`ingest` already imports `store`); the store only needs resolved-root containment for `source_path`, and the strong symlink semantics stay at ingestion.
- The rewriter stays: it is now defence-in-depth — the store prevents out-of-scope content from ever being retrieved, and the rewriter still refuses to emit an absolute/out-of-root path should one somehow arrive.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (119 baseline + new scope rows; the revised foreign-chunk row reflects the store boundary)

**Manual checks:**
- Index a corpus, upsert a chunk with an out-of-root `source_path`, post a question -- expected: 200, the foreign source never appears in `citations`.

