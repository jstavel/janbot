---
title: 'Grounding coverage through the port'
type: 'feature'
ticket: 3
created: '2026-10-13'
status: 'built'
baseline_revision: '98c6511c84cbf1d14073b62133bbaeb7dab76498'
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

**Problem:** the port-only suite does not prove the grounding boundary through the **running service**: that an index holding an **out-of-scope** chunk makes the service **refuse to start** (the goal-5 startup check), and that a **sourceless-only** index yields a grounded-less `503` at the port. The in-process tests cover these; CAP-7 wants the running-service path proven too.

**Approach:** add keyless e2e cases — (a) start the service against an index built with an out-of-scope chunk and assert the **process exits** (startup refusal) with the error in its log; (b) start it against a **sourceless-only** index and assert `POST /chat` → `503` `{detail}`. Crafted indexes are built by a committed helper run as a **subprocess** (the test modules import no `janbot`).

## Boundaries & Constraints

**Always:**
- The e2e test modules import no `janbot` internals — `httpx`, `pytest`, stdlib only; HTTP (or subprocess) only.
- Keyless: no model key needed and no real model called (startup refusal; empty retrieval before any model call).
- Reuse the 4.1/4.2 subprocess harness; the crafted-index helper is a subprocess like the ingestion CLI.
- The crafted-index helper is a **non-test** module (not collected by pytest).

**Never:**
- No production-code change (`api/`, `pipeline/`, `store/`, `ingest/`, `config.py`).
- Do not modify the existing `tests/*.py` files.
- No model-dependent assertions (dropped per the ticket re-scope).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| ERROR | index holds an out-of-scope chunk | service **exits at startup** (non-zero), log names the out-of-scope count | no serving |
| ERROR | sourceless-only index, any question | `503`, `{detail: str}` | empty-retrieval envelope |

</frozen-after-approval>

## Code Map

- `tests/e2e/make_index.py` (new) — a non-test CLI helper: `python make_index.py <index_path> --kind foreign|sourceless [--corpus PATH]` builds a ChromaDB index with a crafted chunk (absolute out-of-scope `source_path`, or `source_path=None`) by importing `janbot.store`. Run as a subprocess so the test modules stay `janbot`-free.
- `tests/e2e/conftest.py` — add: `_make_index(index_path, kind, ...)` (subprocess), fixtures `sourceless_index` + `sourceless_service_base_url` (serves → 503), `foreign_index`, and `_start_service_expecting_exit(index_path)` returning `(returncode, log_text)` after the process exits.
- `tests/e2e/test_grounding_e2e.py` (new) — (a) the service refuses to start on a foreign index (exit non-zero; log mentions the out-of-scope count); (b) a sourceless-only index → `503` with a `{detail}` string mentioning the corpus.
- `README.md` — one line: the grounding cases and the crafted-index helper.
- Do not touch: `src/janbot/**`, existing `tests/*.py`.

## Tasks & Acceptance

**Execution:**
- [x] `tests/e2e/make_index.py` -- the crafted-index helper (foreign/sourceless) -- builds fixtures without `janbot` in the test modules.
- [x] `tests/e2e/conftest.py` -- crafted-index + startup-refusal helpers -- the port-only seams.
- [x] `tests/e2e/test_grounding_e2e.py` -- startup-refusal + sourceless-503 rows -- the grounding proof.
- [x] `README.md` -- note the grounding cases -- docs match behaviour.

**Acceptance Criteria:**
- Given an index with an out-of-scope chunk, when the service starts, then the process exits non-zero and its log names the out-of-scope count.
- Given a sourceless-only index, when a question is posted, then `POST /chat` returns `503` with a `{detail}` string mentioning the corpus.
- Given the e2e modules, when their imports are inspected, then none imports `janbot`.
- Given the whole suite, when run keyless, then every existing test passes and the 4.1 happy path skips.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- The crafted-index helper (`tests/e2e/make_index.py`) imports `janbot.store` in its *own* interpreter: run as `uv run python tests/e2e/make_index.py ...` from the repo root, so the e2e modules and `conftest.py` stay `janbot`-free.
- `foreign` places the chunk at `<corpus>.parent/elsewhere/foreign.org`; the served `scope` is the resolved corpus, so `VectorStore.out_of_scope_sources()` reports it and `create_app` raises before uvicorn serves (non-zero exit; log names `1 chunk(s) whose source_path lies outside ... refusing to start`).
- `sourceless` stores `source_path=None`; the scoped `query` filters it out, so `ChatProgram` raises `EmptyRetrieval` and `/chat` answers `503` with a `{detail}` string mentioning the corpus — before any model call.
- Verified keyless: `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` → 6 passed, 1 skipped; full suite → 153 passed, 1 skipped.

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 0 medium / 1 low / 0 false / 0 maybe-false.** One finding, patched.
- **`_start_service_expecting_exit` leaked its temp log directory** — **verdict: low**. Verified: `tempfile.mkdtemp(prefix="janbot-startup-")` (conftest.py:211) is never removed, on success or on the error paths, so the run left a `/tmp/janbot-startup-*` dir behind (six had accumulated locally); the sibling `_serve` uses pytest's `tmp_path_factory`, which prunes. Met on every run and the fix is a direct correction, so it is not rejected. **route: patch** — the helper now uses `tempfile.TemporaryDirectory`, reading the log inside the context; no signature change. Keyless e2e → 6 passed, 1 skipped; full → 153 passed, 1 skipped; no new `/tmp/janbot-startup-*` dirs.

## Design Notes

- Why a crafted-index helper as a subprocess: a foreign/sourceless index cannot come from the ingestion CLI (it only writes in-scope, sourced paths); building one needs a non-ingestion writer, and the test modules must import no `janbot` — so the writer runs as a subprocess (like `python -m janbot.ingest`).
- Why startup-refusal, not a served 503: the goal-5 check refuses to serve an index holding out-of-scope chunks, so the grounding boundary for that case is proven by the process exiting, not by a response.

## Verification

**Commands:**
- `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` -- expected: the keyless grounding rows pass; the 4.1 happy path skips.
