# Walkthrough — PR #9: "map all /chat processing failures into the error envelope"

Target: PR https://github.com/jstavel/janbot/pull/9 · branch `hardening-chat-error-envelope` · commit `352a525`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the route's exception mapping
- [x] Block 4 — Slice: response-validation envelope + port-only tests
- [x] Block 5 — Periphery

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [plan-chat-error-envelope-robustness.md](../plan-chat-error-envelope-robustness.md).

> **Problem:** the `/chat` route maps only `EmptyRetrieval` → 503 and `ValueError` → 500. A `dspy` exception on the real-model path — e.g. `AdapterParseError` (`DSPyError → Exception`, **not** a `ValueError`) — escapes as a plain-text 500 with no `{"detail"}`, breaking the CAP-3 error-envelope contract. The suite never sees it: every LM stub is a scripted `DummyLM` that always parses.
>
> **Approach:** extend the route's exception mapping so *every* program failure yields the `{detail}` envelope — keep `EmptyRetrieval` → 503 and `ValueError` → 500, add `dspy.DSPyError` → 500, and a final catch-all → 500 whose message leaks no internals. Add port tests that make the program raise and assert a 500 `{detail}`; document the guarantee in README.

## Block 2 — Broad strokes

One route in [src/janbot/api/main.py](../../../src/janbot/api/main.py) plus two tests and a README line. Open these spots:

- [api/main.py:89](../../../src/janbot/api/main.py) — the `/chat` exception mapping.
- [api/main.py:109](../../../src/janbot/api/main.py) — the `ResponseValidationError` handler.
- [tests/test_chat.py](../../../tests/test_chat.py) — the two port-only tests.
- [README.md](../../../README.md) — the documented envelope guarantee.

## Block 3 — Slice: the route's exception mapping

Order matters: the specific mappings first, then a pass-through, then a catch-all.

- [api/main.py:96](../../../src/janbot/api/main.py) — `except HTTPException: raise` — a program-raised `HTTPException` keeps its status/detail instead of being swallowed.
- [api/main.py:98](../../../src/janbot/api/main.py) — `except dspy.DSPyError` → 500 with a fixed detail ("the model response could not be processed").
- [api/main.py:103](../../../src/janbot/api/main.py) — `except Exception` → 500 with a fixed, non-leaking detail.

## Block 4 — Slice: response-validation envelope + port-only tests

- [api/main.py:109](../../../src/janbot/api/main.py) — a `ResponseValidationError` handler so a program returning a non-conforming body still carries the envelope.
- [tests/test_chat.py](../../../tests/test_chat.py) — a genuine adapter parse failure injected through the `lm_factory` seam (unparseable `DummyLM`), and an unexpected error injected through the `embedder` seam (raises during retrieval) — both port-only, no `app.state` mutation.

## Block 5 — Periphery

- [README.md](../../../README.md) — the errors paragraph now states every `/chat` error, including the real-model path, carries the envelope.
- [plan-chat-error-envelope-robustness.md](../plan-chat-error-envelope-robustness.md) — the plan (`built`); Triage Log records the review fixes.
