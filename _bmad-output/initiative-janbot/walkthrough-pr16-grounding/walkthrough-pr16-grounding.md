# Walkthrough — PR #16: "grounding coverage through the port (story 4.3)"

Target: PR https://github.com/jstavel/janbot/pull/16 · branch `e2e-4.3-grounding` · commit `35be5e5`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the crafted-index helper
- [x] Block 4 — Slice: the port seams
- [x] Block 5 — Slice: the grounding rows
- [x] Block 6 — Periphery

## Status

All blocks accepted: 6 of 6. Review complete: PR #16 squash-merged (`c0919dc`), story 4.3 marked done; entry 4.4 unblocked.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-grounding-coverage-through-the-port-plan.md](../epic-verification/story-grounding-coverage-through-the-port-plan.md).

> **Problem:** the port-only suite does not prove the grounding boundary through the **running service**: that an index holding an **out-of-scope** chunk makes the service **refuse to start** (the goal-5 startup check), and that a **sourceless-only** index yields a grounded-less `503` at the port. The in-process tests cover these; CAP-7 wants the running-service path proven too.
>
> **Approach:** add keyless e2e cases — (a) start the service against an index built with an out-of-scope chunk and assert the **process exits** (startup refusal) with the error in its log; (b) start it against a **sourceless-only** index and assert `POST /chat` → `503` `{detail}`. Crafted indexes are built by a committed helper run as a **subprocess** (the test modules import no `janbot`).

## Block 2 — Broad strokes

A new e2e module, a non-test helper, and fixture additions — no production code. Open these three spots:

- [tests/e2e/test_grounding_e2e.py](../../../tests/e2e/test_grounding_e2e.py) — the two grounding rows.
- [tests/e2e/make_index.py](../../../tests/e2e/make_index.py) — the crafted-index helper (run as a subprocess).
- [tests/e2e/conftest.py:65](../../../tests/e2e/conftest.py#L65) — the port seams (`_make_index`, the fixtures, `_start_service_expecting_exit`).

## Block 3 — Slice: the crafted-index helper

The ingestion CLI writes only in-scope, sourced chunks, so it cannot produce the two shapes the grounding rows need. `make_index.py` imports `janbot.store` in its own interpreter and writes a one-chunk index: `foreign` stores an absolute `source_path` outside the served corpus, `sourceless` stores `source_path=None`. Because it runs as a subprocess, the test modules stay `janbot`-free; because its name is not `test_*`, pytest never collects it.

- [make_index.py:54](../../../tests/e2e/make_index.py#L54) — `build(index_path, kind, corpus)` writes the crafted chunk via `VectorStore.upsert`; [make_index.py:48](../../../tests/e2e/make_index.py#L48) — `_foreign_source` places it at `<corpus>.parent/elsewhere/foreign.org`; [make_index.py:67](../../../tests/e2e/make_index.py#L67) — the `argparse` CLI.

## Block 4 — Slice: the port seams

`conftest.py` gains a subprocess wrapper for the helper and the fixtures the rows consume. The service env is factored into `_service_env` so both the serving and the exit-expecting starters use the same corpus/index wiring.

- [conftest.py:65](../../../tests/e2e/conftest.py#L65) — `_make_index` runs the helper as a subprocess.
- [conftest.py:202](../../../tests/e2e/conftest.py#L202) — `_start_service_expecting_exit` starts the service and waits for it to exit, returning `(returncode, log_text)`; [conftest.py:244](../../../tests/e2e/conftest.py#L244) — the `start_service_expecting_exit` fixture.
- [conftest.py:250](../../../tests/e2e/conftest.py#L250), [conftest.py:258](../../../tests/e2e/conftest.py#L258), [conftest.py:266](../../../tests/e2e/conftest.py#L266) — `foreign_index`, `sourceless_index`, `sourceless_service_base_url`.

## Block 5 — Slice: the grounding rows

Two keyless rows prove the boundary at the port. The first asserts the process exits non-zero and its log names the out-of-scope count (a served `503` would not prove the boundary, because the service never gets to serve). The second starts the service on a sourceless-only index and asserts `POST /chat` → `503` with a non-empty `{detail}` string mentioning the corpus — before any model call.

- [test_grounding_e2e.py:26](../../../tests/e2e/test_grounding_e2e.py#L26) — `test_foreign_index_refuses_to_start`: non-zero exit, log contains `"1 chunk(s) whose source_path lies outside"` and `"refusing to start"`.
- [test_grounding_e2e.py:39](../../../tests/e2e/test_grounding_e2e.py#L39) — `test_sourceless_index_returns_503_with_detail_envelope`: `503`, string `detail` mentioning the corpus.

## Block 6 — Periphery

- [README.md:116](../../../README.md#L116) — one line noting the grounding cases and the crafted-index helper.
- [story-grounding-coverage-through-the-port-plan.md](../epic-verification/story-grounding-coverage-through-the-port-plan.md) — the plan (`built`); its Review Triage Log records the one review fix (the leaked temp log dir).
- [epic-verification.md](../epic-verification/epic-verification.md) — a decision recording the grounding re-scope (out-of-scope index → startup refusal; the uncited-answer assertion dropped); [tickets.toml](../epic-verification/tickets.toml) — entry 3 re-scoped and flipped to keyless.
