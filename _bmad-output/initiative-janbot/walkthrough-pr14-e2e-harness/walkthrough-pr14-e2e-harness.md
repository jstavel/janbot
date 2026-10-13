# Walkthrough — PR #14: "port-only e2e harness (story 4.1)"

Target: PR https://github.com/jstavel/janbot/pull/14 · branch `e2e-4.1-port-only-harness` · commit `af8d34b`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the harness (conftest)
- [x] Block 4 — Slice: the happy path + fixture corpus
- [x] Block 5 — Slice: what the review changed
- [x] Block 6 — Periphery

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-port-only-e2e-harness-tracer-bullet-plan.md](../epic-verification/story-port-only-e2e-harness-tracer-bullet-plan.md).

> **Problem:** Verification is the initiative's stated USP, but every current test builds the app in-process (`create_app` + `TestClient`) and imports Python internals — it never proves the **shipped service answers through its HTTP port**, and it violates the epic's Done-when 5. CAP-7 wants an automated endpoint suite that exercises the running service end to end.
>
> **Approach:** a port-only e2e harness: a pytest module importing only `httpx` + stdlib that starts the service as a **subprocess** against a fixture index, waits on `GET /health`, and posts a question to `POST /chat` over HTTP, asserting `200 {answer, citations}` with ≥1 corpus-relative citation. A keyed (hitl) run supplies the real-model proof.

## Block 2 — Broad strokes

A new `tests/e2e/` package that talks HTTP only. Open these spots:

- [tests/e2e/conftest.py](../../../tests/e2e/conftest.py) — the subprocess service fixture.
- [tests/e2e/test_chat_e2e.py:30](../../../tests/e2e/test_chat_e2e.py) — the keyed happy path.
- [tests/e2e/fixture_corpus/](../../../tests/e2e/fixture_corpus/) — the tiny public corpus.
- [README.md](../../../README.md) — the End-to-end tests note.

## Block 3 — Slice: the harness (conftest)

- [conftest.py:109](../../../tests/e2e/conftest.py) — `fixture_index` builds a ChromaDB index at session setup via the ingestion CLI subprocess (`_build_fixture_index`, `:45`).
- [conftest.py:119](../../../tests/e2e/conftest.py) — `service_base_url` starts `uv run uvicorn janbot.api.main:app` against that index, logs to a file, and polls `/health` (`_wait_for_health`, `:80`) before yielding the URL. Imports are stdlib + `httpx` + `pytest` only.

## Block 4 — Slice: the happy path + fixture corpus

- [test_chat_e2e.py:30](../../../tests/e2e/test_chat_e2e.py) — `POST /chat` → `200`, non-empty `answer`, ≥1 citation, every `source` corpus-relative (no leading `/`); skipped when `OPENAI_API_KEY` is absent.
- [fixture_corpus/](../../../tests/e2e/fixture_corpus/) — two small `.org` files with subtree headings.

## Block 5 — Slice: what the review changed

- The first draft committed a ChromaDB fixture index; review found it bakes **absolute** `source_path` values, so it only matches the author's checkout and fails the startup scope check off-box. The index is now **built at setup**, never committed ([conftest.py:109](../../../tests/e2e/conftest.py)).
- The subprocess now logs to a file rather than an undrained pipe (a long `/chat` could otherwise hang).

## Block 6 — Periphery

- [README.md](../../../README.md) — the End-to-end tests section (index built at setup; keyed run command).
- [story-port-only-e2e-harness-tracer-bullet-plan.md](../epic-verification/story-port-only-e2e-harness-tracer-bullet-plan.md) — the plan (`built`); Plan Change Log + Triage Log record the review-driven rewrite.
