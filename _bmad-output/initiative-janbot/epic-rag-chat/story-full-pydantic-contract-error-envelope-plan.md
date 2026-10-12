---
title: 'Full Pydantic contract & error envelope'
type: 'feature'
ticket: 3
created: '2026-10-12'
status: 'built'
baseline_revision: 'e3a9a54'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The `/chat` contract is skeletal: schemas carry no constraints or documentation, a blank question reaches retrieval, and in-flight failures escape as raw plaintext 500s — not the standard error envelope the architecture pins. The port is not yet the finished AD-4 source of truth a future consumer can codegen from.

**Approach:** Complete the Pydantic schemas (field constraints, strip-and-reject for a blank question, ≥ 1 citation, field descriptions) and make every `/chat` error response carry FastAPI's standard `{detail}` envelope — malformed requests via the default 422, pipeline failures mapped through `HTTPException` in the route.

## Boundaries & Constraints

**Always:**
- The contract keeps the pinned shape: single request field `question`; response `{answer, citations[]}`; each `Citation.source` names the source document path (architecture convention). `response_model=ChatResponse` validation stays on the route.
- Errors use FastAPI's standard error envelope, never a custom shape: malformed requests → default 422 `{detail: [...]}`; pipeline failures → `HTTPException` with a `{detail}` body raised in the route handler.
- A blank/whitespace-only `question` is malformed: stripped and rejected at the schema (422), never sent to retrieval.
- `citations` requires ≥ 1 entry at the schema level — the epic's citation invariant made contractual (story 3.4 still owns derived-from correctness and rejection semantics).
- Tests exercise only the HTTP port via `TestClient` with the existing seams (stub embedder, `lm_factory`, `VectorStore.upsert` for crafted metadata); plus a schema-level unit module for the contract itself.
- Preserve story 3.2's pinned behaviors: `janbot.store` before `dspy` import order, the whitespace-key boot gate, module-level `app = create_app()`, `GET /health`.

**Never:**
- No new contract fields (no `breadcrumb`, title, or question echo — no planning doc names them; extend only when a consumer demands it).
- No custom error envelope, no app-level exception handlers beyond the route's `HTTPException` mapping.
- No changes to `store/`, `ingest/`, or `llm/` internals; no citation-path rewrite (3.4), no determinism work (3.5), no scope filter (3.6).
- No `.env` support, no new env vars.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | valid question, indexed corpus | 200 `ChatResponse`, schema-conforming, ≥ 1 citation | No error |
| ERROR | missing / wrong-type `question` | rejected | 422, FastAPI default `{detail: [...]}` |
| ERROR | blank or whitespace-only `question` | rejected at the schema | 422, `{detail: [...]}` |
| ERROR | empty index (0 chunks) | refused | 503, body `{"detail": ...}` naming the no-corpus condition |
| ERROR | retrieved chunk lacks `source_path` | refused | 500, body `{"detail": ...}` naming the integrity failure |
| HAPPY | invalid `ChatResponse` payload (e.g. empty citations) | cannot leave the port | schema-level `ValidationError` |

</frozen-after-approval>

## Code Map

- `src/janbot/api/contract.py` — today bare models (:15-31). Add `Field` constraints + a strip-and-reject validator on `question`, `min_length=1` on `citations`, field `description`s for OpenAPI consumers.
- `src/janbot/pipeline/chat.py` — `ValueError` at :47-51 (0 chunks) and :53-57 (source-less chunk). Introduce two `ValueError` subclasses (e.g. `EmptyRetrieval`, `UnattributableContext`) raised from the same guards — forward logic unchanged, existing tests keep passing.
- `src/janbot/api/main.py` — route handler :81-83. Wrap the program call: `EmptyRetrieval` → status per decision; other `ValueError`s → 500; both via `HTTPException(detail=...)` so bodies are the standard envelope. Keep the key gate (:61-68), import order, module-level `app`.
- `tests/test_chat.py` — extend the port tests: assert the `{detail}` shape for 422/503/500 rows; craft the source-less chunk via public `VectorStore.upsert` with `source_path=None` (verified: chroma 1.5.9 stores and returns `None`).
- `tests/test_contract.py` (new) — schema-level pins: blank `question` raises, empty `citations` rejected, valid construction conforms.
- `README.md` — update the Chat section's error behaviors to the envelope shapes; nothing else.
- Do not touch: `store/`, `ingest/`, `llm/`, `config.py`.

## Tasks & Acceptance

**Execution:**
- [x] `src/janbot/api/contract.py` -- constraints, strip-reject validator, `citations` min 1, field descriptions -- the finished AD-4 single source of truth.
- [x] `src/janbot/pipeline/chat.py` -- two `ValueError` subclasses raised from the existing guards -- machine-readable failure kinds, no message matching.
- [x] `src/janbot/api/main.py` -- map pipeline failures to `HTTPException` on the route (`EmptyRetrieval` → 503, other `ValueError`s → 500) -- every `/chat` error body is the standard `{detail}` envelope.
- [x] `tests/test_contract.py` -- schema-level validation pins -- the contract rejects malformed models by itself.
- [x] `tests/test_chat.py` -- port tests per the matrix incl. `{detail}` shape assertions -- envelope behavior proven through the port.
- [x] `README.md` -- document the error behaviors -- docs match the contract.

**Acceptance Criteria:**
- Given a valid question, when `POST /chat`, then 200 with a body validating against `ChatResponse` and ≥ 1 citation.
- Given a missing, mistyped, or blank `question`, when `POST /chat`, then 422 whose body has FastAPI's standard `detail` shape.
- Given an empty index, when `POST /chat`, then 503 with a `{"detail"}` body naming the no-corpus condition — never a raw traceback.
- Given an indexed chunk without `source_path`, when `POST /chat`, then 500 with a `{"detail"}` body naming the integrity failure.
- Given `ChatResponse(answer=..., citations=[])` at the schema level, when constructed, then `ValidationError` (the ≥ 1 invariant is contractual).
- Given the full suite, when run, then every story-3.2 behavior (happy path, env-only routing, boot key gate, `/health`) still passes unchanged.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-12: Implemented per Code Map. `api/contract.py`: `question` gains a `_reject_blank` `field_validator` that strips surrounding whitespace and raises on an all-blank value (so whitespace-padded questions are also normalized before retrieval); `ChatResponse.citations` gains `Field(min_length=1)`; every field gains an OpenAPI `description`. `pipeline/chat.py`: `EmptyRetrieval` and `UnattributableContext` subclass `ValueError`, raised from the unchanged guards with unchanged messages. `api/main.py`: route wraps the program call — `except EmptyRetrieval` → 503, then `except ValueError` → 500 (subclass ordering makes the mapping kind-based, never message-based), both `HTTPException(detail=str(exc))` with cause chaining; key gate, import order, module-level `app` untouched.
- 2026-10-12: Tests. New `tests/test_contract.py` (9 pins: strip normalization, blank/whitespace-only rejection naming the validator message, missing/mistyped `question`, empty `citations`, valid construction, missing `answer`). `tests/test_chat.py`: the 422 row now loops missing/mistyped/blank bodies asserting `detail` is a list; happy path asserts the body validates against `ChatResponse` with ≥ 1 citation; empty-index test now asserts 503 with `"0 chunks"` in `detail`; new `test_chat_sourceless_chunk_returns_500_with_detail_envelope` crafts the corrupt chunk through public `VectorStore.upsert` with a `SourcelessChunk` stand-in (`source_path=None`, attribute typed `Any` to express the corrupted metadata the `ChunkLike` protocol cannot model) and asserts 500 with `"source_path"` in `detail`. README Chat section rewritten to the envelope shapes only.

## Verification record

- `uv run pytest -q` — 99 passed (89 baseline + 9 contract + 1 new port test), 1 pre-existing Starlette deprecation warning.
- `uv run python -c "from janbot.api.contract import ChatRequest, ChatResponse, Citation; print('ok')"` — `ok`.
- Manual keyless: `uv run uvicorn janbot.api.main:app` + curl — `{}` → 422 `{"detail":[{"type":"missing",...}]}`; `{"question":"   "}` → 422 `{"detail":[{"type":"value_error",...,"question must not be blank"}]}`; `{"question":123}` → 422 `{"type":"string_type",...}`; `/health` → 200 `{"status":"ok"}`. A valid question over the existing real `chroma_db/` returned 200, confirming story 3.2 behavior unchanged. Server stopped after checks.

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-12 — quick lens

- **No unmet acceptance criteria, broken rules, or bugs.** All six ACs verified against the code (contract constraints + strip-reject + `min_length=1`; subclass-first 503/500 mapping; 3.2 pins preserved; suite 99 passed). Zero patch/defer entries.
- **Informational — `tests/test_chat.py` source-less-chunk mechanism note.** The plan's Code Map says chroma 1.5.9 "stores and returns `None`" for `source_path: None`; verified live: chroma *drops* the `None`-valued key at upsert, and `VectorStore.query` maps the missing key to `None` via `.get()` (`store/chroma.py:154`) — so the test and guard behave exactly as intended. **verdict: low** (doc-only inaccuracy, no behavior harm). **route: rejected** — the fix would edit this build's plan; the accurate mechanism is recorded in this row.

## Design Notes

- The two pipeline exceptions subclass `ValueError` so story 3.2's guards, tests, and fail-fast behavior stay intact; the route maps kinds to statuses, never message strings.
- Envelope statuses: 503 = empty retrieval (request well-formed, service lacks grounding material — supersedes 3.2's pinned 500, human-decided 2026-10-12); 500 = integrity failure (chunk without `source_path`). Request-side malformed input stays 422 — never conflated with server-side conditions.
- Schema completion is deliberately shape-only: the architecture pins `source` as the citation's document path; richer fields wait for a real consumer (M1.5 codegen).

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (89 baseline + new contract/chat tests)
- `uv run python -c "from janbot.api.contract import ChatRequest, ChatResponse, Citation; print('ok')"` -- expected: `ok`

**Manual checks (keyless, eval mode):**
- Start: `uv run uvicorn janbot.api.main:app`
- `curl -s -X POST localhost:8000/chat -H 'content-type: application/json' -d '{}'` -- expected: 422 with a `detail` body
- `curl -s -X POST localhost:8000/chat -H 'content-type: application/json' -d '{"question":"   "}'` -- expected: 422 with a `detail` body
