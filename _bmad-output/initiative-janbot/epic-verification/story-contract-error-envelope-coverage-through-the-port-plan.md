---
title: 'Contract & error-envelope coverage through the port'
type: 'feature'
ticket: 2
created: '2026-10-13'
status: 'built'
baseline_revision: 'd3a067293f92faf46207da07e6b364aadbdcb97b'
route: 'oneshot'
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

**Problem:** the port-only harness (4.1) proves only the happy path. The contract's error envelope — a malformed/blank question → 422, an empty index → 503 — is verified in-process (`tests/test_chat.py`) but never through the **running service over HTTP**, which is what CAP-7/Done-when 2 require.

**Approach:** add a keyless e2e module asserting `POST /chat` with a malformed/blank question returns `422` (FastAPI `{detail}` list) and, against a service started on an **empty index**, returns `503` (`{detail}` string). Refactor the `tests/e2e` service fixtures so a second service instance can run against an empty index.

## Boundaries & Constraints

**Always:**
- The e2e modules import no `janbot` internals — `httpx`, `pytest`, stdlib only; HTTP only.
- Keyless: no model key is needed and no real model is called (422 is validation; 503 is empty retrieval before any model call).
- Reuse the 4.1 subprocess harness; both error assertions go through the HTTP port.

**Never:**
- No production-code change (`api/`, `pipeline/`, `store/`, `ingest/`, `config.py`).
- Do not modify the existing `tests/*.py` files (the `tests/e2e/` package is this epic's).
- No model-dependent assertions — those belong to the `hitl` entries.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| ERROR | `{}` / `{"question": 123}` / `{"question": "   "}` | `422`, `{detail: [ ... ]}` (list) | validation envelope |
| ERROR | empty index, any question | `503`, `{detail: "<string>"}` | empty-retrieval envelope |

</frozen-after-approval>

## Verification

**Commands:**
- `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` -- expected: the keyless contract/error rows pass (the 4.1 happy path skips).

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: `tests/e2e/conftest.py` — extracted a `_serve(index_path, ...)` context manager; added `empty_service_base_url` (an empty index) alongside `service_base_url`. `tests/e2e/test_contract_e2e.py` (new) — three malformed/blank bodies → 422 (list detail) and an empty index → 503 (string detail).
- 2026-10-13: both error rows use `empty_service_base_url`, so the keyless suite builds no fixture index and calls no model (the 422 row is index-independent).
- Verification: keyless `uv run pytest -q` → 151 passed, 1 skipped.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 1 medium / 0 low / 0 false / 0 maybe-false.** One finding, patched.
- **The malformed-question rows reused the populated-index service, coupling the keyless suite to the model build** — **verdict: medium**. Verified: `service_base_url` → `fixture_index` → the ingestion CLI → `default_embedder()`; a machine without the cached model would fail rather than skip, contradicting the keyless/hitl split. **route: patch** — the 422 rows now use `empty_service_base_url`; the keyless run builds no index (e2e time dropped 5.9s → 3.0s).

