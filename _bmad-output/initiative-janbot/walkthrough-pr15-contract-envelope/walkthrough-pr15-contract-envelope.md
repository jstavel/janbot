# Walkthrough — PR #15: "contract & error-envelope coverage over the HTTP port (story 4.2)"

Target: PR https://github.com/jstavel/janbot/pull/15 · branch `e2e-4.2-contract-envelope` · commit `f0516b6`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the service fixtures
- [x] Block 4 — Slice: the error-envelope tests
- [x] Block 5 — Periphery

## Status

All blocks accepted: 5 of 5. Review complete: PR #15 squash-merged (`4a82919`), story 4.2 marked done; entry 4.3 unblocked.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-contract-error-envelope-coverage-through-the-port-plan.md](../epic-verification/story-contract-error-envelope-coverage-through-the-port-plan.md).

> **Problem:** the port-only harness (4.1) proves only the happy path. The contract's error envelope — a malformed/blank question → 422, an empty index → 503 — is verified in-process but never through the **running service over HTTP**, which is what CAP-7/Done-when 2 require.
>
> **Approach:** add a keyless e2e module asserting `POST /chat` with a malformed/blank question returns `422` (FastAPI `{detail}` list) and, against a service started on an **empty index**, returns `503` (`{detail}` string). Refactor the `tests/e2e` service fixtures so a second service instance can run against an empty index.

## Block 2 — Broad strokes

A new e2e test module plus a fixture refactor. Open these spots:

- [tests/e2e/test_contract_e2e.py](../../../tests/e2e/test_contract_e2e.py) — the error-envelope rows.
- [tests/e2e/conftest.py:120](../../../tests/e2e/conftest.py) — the `_serve` helper.
- [tests/e2e/conftest.py:166](../../../tests/e2e/conftest.py) — `empty_service_base_url`.

## Block 3 — Slice: the service fixtures

- [conftest.py:120](../../../tests/e2e/conftest.py) — `_serve(index_path, ...)` starts (and tears down) the service against a given index; [conftest.py:157](../../../tests/e2e/conftest.py) — `service_base_url` uses the fixture index; [conftest.py:166](../../../tests/e2e/conftest.py) — `empty_service_base_url` starts it against an empty index (no fixture-index build, no model).

## Block 4 — Slice: the error-envelope tests

- [test_contract_e2e.py:23](../../../tests/e2e/test_contract_e2e.py) — three malformed/blank bodies → `422` with a non-empty `{detail}` list; it uses `empty_service_base_url`, so the row is index- and model-free.
- [test_contract_e2e.py:35](../../../tests/e2e/test_contract_e2e.py) — an empty index → `503` with a non-empty `{detail}` string mentioning the corpus.

## Block 5 — Periphery

- [story-contract-error-envelope-coverage-through-the-port-plan.md](../epic-verification/story-contract-error-envelope-coverage-through-the-port-plan.md) — the plan (`built`); Triage Log records the one review fix (422 rows moved off the populated-index service).
