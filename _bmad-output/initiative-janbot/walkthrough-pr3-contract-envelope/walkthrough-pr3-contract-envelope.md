# Review: PR #3 — full /chat contract & error envelope (story 3.3)

**Target:** PR [#3](https://github.com/jstavel/janbot/pull/3) — head `story-3.3-contract-envelope` → base `main`, single commit `8a75873` — "feat: complete /chat contract and standard error envelope (story 3.3)".

## Block 1 — Intent

- [x] accepted

The frozen Intent below comes verbatim from the story-3.3 plan file ([story-full-pydantic-contract-error-envelope-plan.md](../epic-rag-chat/story-full-pydantic-contract-error-envelope-plan.md#L20-L24)):

> **Problem:** The `/chat` contract is skeletal: schemas carry no constraints or documentation, a blank question reaches retrieval, and in-flight failures escape as raw plaintext 500s — not the standard error envelope the architecture pins. The port is not yet the finished AD-4 source of truth a future consumer can codegen from.
>
> **Approach:** Complete the Pydantic schemas (field constraints, strip-and-reject for a blank question, ≥ 1 citation, field descriptions) and make every `/chat` error response carry FastAPI's standard `{detail}` envelope — malformed requests via the default 422, pipeline failures mapped through `HTTPException` in the route.

Situating: story 3.2's tracer bullet sketched the `/chat` port end-to-end but left the contract skeletal and errors raw — this story completes that port into the finished AD-4 single source of truth. The 503 status for an empty index is a deliberate human choice (recorded in the plan's Design Notes) that supersedes 3.2's pinned 500. The ≥1-citation invariant pinned here at schema level sets up story 3.4, which owns citation correctness (derived-from checking and rejection semantics).

## Block 2 — Broad strokes

- [x] accepted

Entry points a reviewer opens first:

- [src/janbot/api/contract.py](../../../src/janbot/api/contract.py) — the finished AD-4 models, self-validating and documented.
- [src/janbot/pipeline/chat.py](../../../src/janbot/pipeline/chat.py) — the two `ValueError` subclasses giving failures machine-readable kinds.
- [src/janbot/api/main.py](../../../src/janbot/api/main.py) — the route's `HTTPException` mapping to the standard envelope.
- [tests/test_contract.py](../../../tests/test_contract.py) + [tests/test_chat.py](../../../tests/test_chat.py) — the two test layers (schema-level pins; port-level envelope asserts).

## Block 3 — Slice: contract completion (schema-level)

- [x] accepted

Mechanism: the models are now self-validating. A strip-and-reject `field_validator` on `question` strips surrounding whitespace and raises on an all-blank value — so a blank question becomes a `ValidationError`, which FastAPI surfaces as the default 422, and padded values are normalized before retrieval ever sees them. `Field(min_length=1)` on `citations` pins the epic's ≥1-citation invariant at the schema level. Every field also carries a `description` for OpenAPI consumers. The shape is unchanged and no new fields were added — deliberate, since no planning doc names any ([plan, Never list](../epic-rag-chat/story-full-pydantic-contract-error-envelope-plan.md#L37)).

Places to look:

- The validator: [src/janbot/api/contract.py:25-32](../../../src/janbot/api/contract.py#L25-L32)
- The `min_length` pin: [src/janbot/api/contract.py:45-48](../../../src/janbot/api/contract.py#L45-L48)
- One test showing the pin: [tests/test_contract.py:41-45](../../../tests/test_contract.py#L41-L45)

## Block 4 — Slice: failure kinds & envelope mapping

- [x] accepted

Mechanism: two `ValueError` subclasses — `EmptyRetrieval` and `UnattributableContext` — are raised from the unchanged retrieval guards, giving failures machine-readable kinds instead of message matching. The route maps `EmptyRetrieval` → 503 and any other `ValueError` → 500, both via `HTTPException(detail=str(exc))`, so every `/chat` error body is FastAPI's standard `{detail}` envelope, never a raw traceback. Ordering matters: `except EmptyRetrieval` must precede `except ValueError` because `EmptyRetrieval` *is* a `ValueError` — reversed, the generic clause would swallow the kind and collapse the 503 into 500. The 503 itself is a human decision (2026-10-12, recorded in the plan) superseding story 3.2's pinned 500 for the empty-index case.

Places to look:

- The class definitions: [src/janbot/pipeline/chat.py:28-33](../../../src/janbot/pipeline/chat.py#L28-L33)
- The unchanged guards: [src/janbot/pipeline/chat.py:55-65](../../../src/janbot/pipeline/chat.py#L55-L65)
- The except chain: [src/janbot/api/main.py:83-88](../../../src/janbot/api/main.py#L83-L88)

## Block 5 — Slice: test layers

- [x] accepted

Mechanism: coverage runs on two layers. Schema-level pins in [tests/test_contract.py](../../../tests/test_contract.py) construct models directly — blank/mistyped/missing `question`, zero-citations response — and never touch HTTP. Port-level tests in [tests/test_chat.py](../../../tests/test_chat.py) assert the `{detail}` envelope shapes (422/503/500) through `TestClient`. One mechanism note: the source-less chunk is crafted via the public `VectorStore.upsert` with a stand-in carrying `source_path=None`; verified live, chroma drops `None`-valued metadata keys at upsert, and `query` maps the missing key back to `None` via `.get()` (`store/chroma.py:154`) — the correction recorded in the plan's triage log, and the reason the guard still fires exactly as intended.

Places to look:

- A schema pin: [tests/test_contract.py:21-26](../../../tests/test_contract.py#L21-L26)
- A port-level envelope test: [tests/test_chat.py:189-207](../../../tests/test_chat.py#L189-L207)
- The envelope asserts (422 loop, 500 row): [tests/test_chat.py:110-119](../../../tests/test_chat.py#L110-L119), [tests/test_chat.py:210-228](../../../tests/test_chat.py#L210-L228)

## Block 6 — Periphery

- [x] accepted

- README: the Chat section's error paragraph rewritten to the envelope shapes — [README.md:85](../../../README.md#L85).
- Plan file: status flipped to `built` with implementation notes appended — [plan status](../epic-rag-chat/story-full-pydantic-contract-error-envelope-plan.md#L6).
- Verification record: suite 99 passed (89 baseline + 10 new); keyless curl manual checks against a live server — [plan, Verification record](../epic-rag-chat/story-full-pydantic-contract-error-envelope-plan.md#L90-L94).

## Status

All blocks accepted: 6 of 6. Review complete: PR #3 merged (4c5d7d3), stories 3.2 and 3.3 marked done.
