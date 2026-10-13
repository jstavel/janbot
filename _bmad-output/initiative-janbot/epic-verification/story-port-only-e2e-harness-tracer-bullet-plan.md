---
title: 'Port-only e2e harness (tracer bullet)'
type: 'feature'
ticket: 1
created: '2026-10-13'
status: 'done'
baseline_revision: '43ae8157ce47311f242dcddf9e02233ec2393eb6'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Verification is the initiative's stated USP, but every current test builds the app in-process (`create_app` + `TestClient`) and imports Python internals — it never proves the **shipped service answers through its HTTP port**, and it violates the epic's Done-when 5 ("the suite imports no Python-internal modules"). CAP-7 wants an automated endpoint suite that exercises the running service end to end.

**Approach:** a port-only e2e harness: a pytest module importing only `httpx` + stdlib that (a) starts the service as a **subprocess** against a committed **fixture index**, (b) waits on `GET /health`, and (c) posts a question to `POST /chat` over HTTP, asserting `200 {answer, citations}` with at least one corpus-relative citation. A keyed (hitl) run supplies the real-model proof.

## Boundaries & Constraints

**Always:**
- The e2e test module imports no `janbot` internals — `httpx`, `pytest`, and stdlib only; it talks HTTP only.
- The service runs as a subprocess (`uv run uvicorn janbot.api.main:app`); the fixture index is **built at session setup for this checkout** and lies within the fixture corpus scope (the startup check must pass).
- The hitl happy path is skipped cleanly when no model key is present, so a keyless run (CI, entry 5) stays green.
- Every existing test still passes.

**Never:**
- No production-code change (`api/`, `pipeline/`, `store/`, `ingest/`, `config.py`).
- No TypeScript/Zod harness, no MLFlow (Milestone 1.5 / 2).
- Do not modify the existing `tests/*.py` files.

Decision (2026-10-13, review): the fixture index is **built at session setup** via the ingestion CLI subprocess, **not committed** — a committed ChromaDB index bakes absolute `source_path` values that only match the author's checkout, so the startup scope check would fail on any other machine (incl. CI). The test module still imports no `janbot` (the CLI runs in a subprocess). This supersedes the earlier "committed fixture index" decision.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | service up, key present, question posted | `200 {answer, citations[]}`, ≥1 corpus-relative citation | No error |
| EDGE | service not yet ready | harness polls `/health` until ready (bounded) | fail with a clear timeout if never ready |
| EDGE | no model key | the happy-path test is skipped, not failed | clean skip |
| EDGE | fixture index missing | harness fails with a clear message | actionable error |

</frozen-after-approval>

## Code Map

- `tests/e2e/__init__.py` (new) — makes the package; no imports.
- `tests/e2e/conftest.py` (new) — fixtures: build the fixture index at session setup via the ingestion CLI subprocess (`uv run python -m janbot.ingest`); start `uv run uvicorn janbot.api.main:app` on an ephemeral port with `JANBOT_CORPUS_PATH`, `JANBOT_INDEX_PATH`, `JANBOT_MODEL_MODE=eval`, logging to a file (not a pipe); poll `GET /health` (bounded); yield the base URL; terminate in teardown. Imports: `subprocess`, `socket`, `time`, `pathlib`, `os`, `httpx`, `pytest` only.
- `tests/e2e/test_chat_e2e.py` (new) — one keyed test: `POST /chat` → `200`, body validates against the JSON shape (`answer: str`, `citations: [{source}]`), every `source` is corpus-relative (no leading `/`). Decorated to skip when the model key is absent.
- `tests/e2e/fixture_corpus/*.org` (new) — a tiny public corpus (a couple of `.org` files, subtree headings).
- `README.md` — a short "End-to-end tests" note: the index is built at setup; how to run the suite keyed.
- Do not touch: `src/janbot/**`, existing `tests/*.py`.

## Tasks & Acceptance

**Execution:**
- [ ] `tests/e2e/fixture_corpus/*.org` -- add a tiny public corpus -- the served fixture.
- [ ] `tests/e2e/__init__.py` + `tests/e2e/conftest.py` -- build the fixture index at session setup and run the service as a subprocess with a `/health` poll and teardown -- the port-only seam.
- [ ] `tests/e2e/test_chat_e2e.py` -- the keyed happy-path test over HTTP -- the tracer proof.
- [ ] `README.md` -- document the harness -- docs match behaviour.

**Acceptance Criteria:**
- Given the committed fixture index and a model key, when the suite runs, then the e2e module starts the service as a subprocess and `POST /chat` returns `200` with ≥1 corpus-relative citation.
- Given no model key, when the suite runs, then the e2e happy-path test is skipped and the rest of the suite is green.
- Given the e2e module, when its imports are inspected, then it imports no `janbot` module.
- Given the whole suite, when run, then every existing test still passes.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: First pass added `tests/e2e/` with a **committed** ChromaDB fixture index. Review found the index bakes absolute `source_path` values, so it only matches the author's checkout — the startup scope check fails elsewhere (CI). Rewritten per the review decision: the index is **built at session setup** via the ingestion CLI subprocess and never committed; the service logs to a file, not an undrained pipe.
- 2026-10-13: `tests/e2e/{__init__.py,conftest.py,test_chat_e2e.py}` + `fixture_corpus/{profile,projects}.org`; README "End-to-end tests". No production code; existing `tests/*.py` untouched.
- Verification: keyless `uv run pytest -q` → all pre-existing tests pass, the e2e happy path skips; keyed `uv run pytest tests/e2e -q` → the port-only happy path passes.

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

- 2026-10-13: Review found the frozen "committed fixture index" decision unworkable (absolute paths pin the author's checkout). **Trigger:** a committed index fails the startup scope check off-box. **Amended:** the fixture index is built at setup, not committed (frozen decision superseded; Code Map, Tasks, Design Notes, README updated). **Known-bad state avoided:** an e2e suite that only ever passes on the author's machine. **KEEP:** the port-only subprocess harness, the keyed skip-when-no-key behaviour, the tiny fixture corpus, and the no-`janbot`-imports test module.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 1 high / 2 medium / 2 low / 1 false / 0 maybe-false.** One loopback (intent_gap), resolved; the rest patched or rejected.
- **Committed fixture index is not portable (absolute paths)** — **verdict: high**. Verified: a ChromaDB index bakes absolute `source_path` values; `_within_scope` requires them under `JANBOT_CORPUS_PATH`, so on any other path the startup check fails. **route: intent_gap** — the frozen decision was renegotiated; the index is now built at setup.
- **The "avoids the embedder-model download" rationale is wrong** — **verdict: medium**. Query-time embedding still needs all-MiniLM. **route: patch** — rationale corrected; the local build keeps the model dependency explicit.
- **Subprocess stderr→stdout pipe is never drained** — **verdict: medium**. Could hang a long `/chat` run. **route: patch** — the service now logs to a file.
- **`_free_port()` bind/close race** — **verdict: low**. Real but narrow. **route: accept as-is** (the failure surfaces with captured logs).
- **`issue.md` in the diff** — **verdict: false**. An untracked user artifact swept in by `git add -A`; unstaged, not committed.
- **Staged plan shows `in-progress`** — **verdict: false**. A staging-timing artifact; the committed plan is finalized as `built`.


## Design Notes

- Why a subprocess and not `TestClient`: Done-when 1/5 demand the running service over HTTP with no Python internals; only a real subprocess proves the deployed path (uvicorn + env config + the startup checks).
- Why the fixture index is built at setup, not committed: a ChromaDB index bakes absolute `source_path` values, so a committed index only matches the author's checkout (the startup scope check would fail elsewhere, incl. CI). Building it locally keeps the absolute-path trust anchor and stays portable; the test module imports no `janbot` (the CLI runs in a subprocess).
- Why keyed/hitl: the shipped eval mode calls a real model to answer; there is no keyless LM seam (adding one is a production change outside this epic's boundary). The happy path is skipped cleanly without a key.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all existing tests pass; the e2e happy path is skipped without a key.

**Manual checks (keyed):**
- `OPENAI_API_KEY=... uv run pytest tests/e2e -q` -- expected: the port-only happy path passes with a cited answer (the fixture index is built automatically at session setup).
