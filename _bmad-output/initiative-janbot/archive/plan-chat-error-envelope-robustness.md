---
title: 'Chat error-envelope robustness'
type: 'bugfix'
ticket: ''
created: '2026-10-13'
status: 'built'
baseline_revision: 'abfbeb2265289880776394b0983727f97f51ada7'
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

**Problem:** the `/chat` route maps only `EmptyRetrieval` → 503 and `ValueError` → 500 (`src/janbot/api/main.py:88-93`). A `dspy` exception on the real-model path — e.g. `AdapterParseError`, whose MRO is `DSPyError → Exception` (**not** a `ValueError`, verified) — escapes as a plain-text 500 with no `{"detail"}`, breaking the CAP-3 error-envelope contract (architecture spine, Consistency Conventions) that every `/chat` error carries FastAPI's standard envelope. The suite never sees it: every LM stub is a scripted `DummyLM` that always parses (`tests/test_chat.py:50-53`). Recorded in the epic-rag-chat retrospective.

**Approach:** extend the route's exception mapping so *every* program failure yields the `{detail}` envelope — keep `EmptyRetrieval` → 503 and `ValueError` → 500, add `dspy.DSPyError` → 500, and a final catch-all → 500 whose message leaks no internals. Add port tests that make the program raise and assert a 500 `{detail}`; document the guarantee in README.

## Boundaries & Constraints

**Always:**
- The 422 (validation), 503 (empty retrieval), and 500 (integrity/parse/internal) envelope shapes are preserved; every `/chat` error body is `{"detail": ...}`.
- The catch-all detail is a fixed, non-leaking message — never a raw traceback, path, or secret.
- `EmptyRetrieval` stays 503 and keeps its existing detail wording (pinned by `tests/test_chat.py:293-295`).
- The suite stays green; 3.1–3.8 pins pass unchanged.

**Never:**
- No change to `pipeline/`, `store/`, `ingest/`, `llm/`, `config.py`, or the contract models; no new route or field.
- Do not swallow `fastapi.HTTPException` or turn a validation 422 into a 500.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| ERROR | program raises `dspy.DSPyError` | 500, `{"detail"}` | envelope preserved |
| ERROR | program raises a non-dspy, non-`ValueError` exception | 500, fixed `{"detail"}` | envelope preserved; no internals |
| HAPPY | program returns a `ChatResponse` | 200 | No error |
| EDGE | empty index (`EmptyRetrieval`) | 503, existing wording | unchanged |

Decision (2026-10-13): catch scope is `dspy.DSPyError` → 500 **plus** a final `except Exception` → 500 (option A), so any program failure yields the envelope. The catch-all detail is a fixed, non-leaking message (option A).

</frozen-after-approval>

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: `src/janbot/api/main.py` — the `/chat` mapping now adds `except HTTPException: raise` (pass-through), `dspy.DSPyError` → 500 (fixed detail), and a final `except Exception` → 500 (fixed, non-leaking detail); plus a `ResponseValidationError` handler so a non-conforming program response still carries the envelope. `README.md` documents the guarantee. `tests/test_chat.py` adds two port-only tests: a genuine adapter parse failure via the `lm_factory` seam (unparseable `DummyLM` → `AdapterParseError`) and an unexpected error via the `embedder` seam (raises during retrieval) — no `app.state` mutation.
- Verification: `uv run pytest -q` → 132 passed. Response-validation handler verified live: a garbage program body → `500 application/json {"detail":"the service failed to process the request"}`.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 3 medium / 2 low / 0 false / 0 maybe-false.** Four fixed, one deferred.
- **Response-validation failures escaped the envelope** (`api/main.py`) — **verdict: medium**. Verified live: a non-conforming program body → plain-text 500. **route: patch** — added a `ResponseValidationError` handler; re-verified (JSON envelope).
- **Catch-all swallowed `HTTPException`** (`api/main.py`) — **verdict: medium**. Verified: a program `HTTPException` was remapped to 500. **route: patch** — added `except HTTPException: raise`.
- **Tests reached into `app.state.program`, violating AD-7** (`tests/test_chat.py`) — **verdict: medium**. Verified the sanctioned seams suffice. **route: patch** — rewrote both tests to use `lm_factory`/`embedder`; the dspy test now raises a genuine `AdapterParseError` through the adapter.
- **Wrong rule citation in the frozen intent** ("CAP-3 / AD-4") — **verdict: low**. AD-4 is "Pydantic as the single contract source"; the envelope is a spine Consistency Convention. **route: patch** — citation corrected.
- **No CHANGELOG entry** — **verdict: low**. Pre-existing repo-wide gap (already tracked in `deferred-work.md` for 2.1–3.5). **route: defer** — not re-recorded.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: 132 passed

