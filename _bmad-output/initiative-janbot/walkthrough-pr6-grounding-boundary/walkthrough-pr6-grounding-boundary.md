# Walkthrough — PR #6: "scope retrieval to the corpus at the store boundary" (story 3.6)

Target: PR https://github.com/jstavel/janbot/pull/6 · branch `story-3.6-grounding-boundary` · commit `f656020`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the store-boundary scope
- [x] Block 4 — Slice: wiring the scope from config
- [x] Block 5 — Slice: proving the boundary (store + port)
- [x] Block 6 — Periphery

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-grounding-boundary-no-answer-outside-the-public-corpus-plan.md](../epic-rag-chat/story-grounding-boundary-no-answer-outside-the-public-corpus-plan.md).

> **Problem:** Retrieval is global top-k. `VectorStore.query` passes no scope filter (`src/janbot/store/chroma.py:135-158`), so any stored chunk — including one upserted with an out-of-corpus `source_path` — is retrievable. The only thing standing between it and an answer is downstream, at derivation time: the citation rewriter refuses an out-of-root chunk and the request 500s (`src/janbot/pipeline/chat.py:58-75,100-114`). That is a refusal *after* the content has already entered the prompt context; the guarantee rests on the rewriter, not on the store boundary, and epic Done-when 5 (CAP-1: no answer from outside `public_profile_org/`) wants the store to carry it. The suspended carry in `deferred-work.md` assigns this story the store scope ownership.
>
> **Approach:** Give the store a corpus scope at construction, fed the already-absolute `Config.corpus_path`. A scoped `query` returns up to `k` chunks that all lie within scope — it over-fetches ranked candidates and filters to scope before truncating to `k` — so an out-of-scope chunk can never enter retrieval, the prompt, or a citation. The pipeline rewriter stays as a second, fail-closed guard.

## Block 2 — Broad strokes

Retrieval is now bounded to the corpus root at the store, not merely refused later. Open these four spots in order:

- [src/janbot/store/chroma.py](../../../src/janbot/store/chroma.py) — the scope, the containment helper, and the filtered query.
- [src/janbot/api/main.py](../../../src/janbot/api/main.py) — where the corpus root is handed to the store.
- [tests/test_store_scope.py](../../../tests/test_store_scope.py) — the store-level proof.
- [tests/test_chat.py](../../../tests/test_chat.py) — the port-level proof.

## Block 3 — Slice: the store-boundary scope

The store can be told a corpus root; a scoped `query` keeps only chunks located inside it.

- [chroma.py:43](../../../src/janbot/store/chroma.py) — `_within_scope`: fail-closed, symlink-aware containment mirroring `ingest.scope.within` without importing it (avoids the `ingest → store` cycle); a non-string or missing path returns `False`.
- [chroma.py:85](../../../src/janbot/store/chroma.py) — optional `scope` on the constructor, resolved once.
- [chroma.py:163](../../../src/janbot/store/chroma.py) — `query`: `k <= 0` returns `[]`; when scoped it over-fetches every stored chunk and filters to scope before truncating to `k`; unscoped is unchanged global top-k.

## Block 4 — Slice: wiring the scope from config

- [api/main.py:59](../../../src/janbot/api/main.py) — `VectorStore(..., scope=config.corpus_path)`; the root is already absolute/resolved. No other call site is scoped (ingestion keeps an unscoped store).

## Block 5 — Slice: proving the boundary (store + port)

- [test_store_scope.py](../../../tests/test_store_scope.py) — unscoped global top-k; an out-of-scope chunk that ranks highest is excluded; only-out-of-scope → `[]`; missing `source_path` excluded; non-string `source_path` excluded; `query(k=0)` → `[]`; filtering happens before truncation so `k` in-scope chunks return.
- [test_chat.py:428](../../../tests/test_chat.py) — foreign-only index → 503 (`/srv/elsewhere` never emitted); [test_chat.py:450](../../../tests/test_chat.py) — foreign + public → 200 citing only the public source; [test_chat.py:298](../../../tests/test_chat.py) — sourceless-only → 503 (the 3.3 pin this story supersedes, per the review ruling).

## Block 6 — Periphery

- [README.md](../../../README.md) / [ARCHITECTURE.md](../../../ARCHITECTURE.md) — retrieval is scoped to `JANBOT_CORPUS_PATH` at the store boundary; the false "Collection per domain scope" claim is removed.
- [story-grounding-boundary-no-answer-outside-the-public-corpus-plan.md](../epic-rag-chat/story-grounding-boundary-no-answer-outside-the-public-corpus-plan.md) — the plan, now `built`; carries two dated decisions from planning and review.
