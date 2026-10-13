# Walkthrough — PR #13: "fail fast at startup when the index lies outside the served corpus root"

Target: PR https://github.com/jstavel/janbot/pull/13 · branch `hardening-serve-ingest-alignment` · commit `8644950`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the store method and the startup check
- [x] Block 4 — Slice: the test and docs
- [x] Block 5 — Periphery

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [plan-serve-ingest-root-alignment.md](../plan-serve-ingest-root-alignment.md).

> **Problem:** ingestion writes through an **unscoped** store, so the index carries no record of which corpus root built it, while serving scopes to whatever `JANBOT_CORPUS_PATH` the process got and rewrites citations relative to that root. A serve root that differs from the ingest root is therefore undetected: a **broader** serve root silently changes the citation form; a **narrower** one silently 503s every request. No story owned the ingest↔serve alignment.
>
> **Approach (decision A):** `create_app` performs a **startup cross-check** — it fails fast (`ValueError`) if any indexed `source_path` lies outside `config.corpus_path`, so an index built from a different (narrower or foreign) root is surfaced instead of serving silently.

## Block 2 — Broad strokes

A store helper plus a startup guard. Open these spots:

- [chroma.py:141](../../../src/janbot/store/chroma.py) — `out_of_scope_sources()`.
- [main.py:67](../../../src/janbot/api/main.py) — the startup check in `create_app`.
- [test_chat.py:648](../../../tests/test_chat.py) — the startup-failure test.
- [README.md](../../../README.md) — the documented check.

## Block 3 — Slice: the store method and the startup check

- [chroma.py:141](../../../src/janbot/store/chroma.py) — `out_of_scope_sources()` returns stored chunks whose `source_path` is outside `scope` (empty when unscoped), reusing `_within_scope`.
- [main.py:67](../../../src/janbot/api/main.py) — `create_app` computes it after building the scoped store and raises `ValueError` (naming the count and root) if non-empty; the `Raises` docstring and error message were updated.

## Block 4 — Slice: the test and docs

- [test_chat.py:648](../../../tests/test_chat.py) — an index with an out-of-scope chunk makes `create_app` raise; the in-scope path still starts (all other tests).
- [README.md](../../../README.md) — the Configuration section states the startup verification; the wording is narrowed to "every indexed chunk which records a source" (a sourceless chunk is not in `sources()`).

## Block 5 — Periphery

- [plan-serve-ingest-root-alignment.md](../plan-serve-ingest-root-alignment.md) — the plan (`built`); Triage Log records the two wording patches, two acceptances, and the residual.
- [deferred-work.md](../deferred-work.md) — the residual: a serve root *broader* than the ingest root is not detected (harmless).
