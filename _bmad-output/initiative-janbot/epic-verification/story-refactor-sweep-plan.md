---
title: 'Refactor sweep'
type: 'feature'
ticket: 6
created: '2026-10-13'
status: 'done'
baseline_revision: '0bdf93425f908e3480aa23da3f5555057378a6b4'
route: 'oneshot'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the epic's stories left the `tests/e2e` harness with duplicated plumbing and one deferred finding: `_serve` and `_start_service_expecting_exit` build the same `uvicorn` command twice, and story 4.1's review **accepted (did not fix)** the `_free_port()` bind/close race. The stale DW4 "citation ordering" deferred item also still reads as open though the code already emits citations in retrieval order.

**Approach:** a cleanup-only pass over `tests/e2e` — factor the shared `uvicorn` command, close the `_free_port()` race with a bounded retry on a fresh port, and reconcile the stale deferred item. No behaviour change to the service or the tests' assertions.

## Boundaries & Constraints

**Always:**
- Cleanup only: no production-code change (`api/`, `pipeline/`, `store/`, `ingest/`, `config.py`), no change to what any test asserts.
- The harness keeps importing no `janbot` internals; the keyless suite still builds no fixture index.
- The retry is bounded and only fires on a real bind failure ("address already in use"); every other startup failure still surfaces with captured logs.

**Never:**
- No new test coverage, no new CI behaviour, no formatting-only churn across unrelated files.
- Do not modify the existing `tests/*.py` files outside `tests/e2e/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | a service start | one shared `uvicorn` command builder; identical behaviour | No error |
| EDGE | the chosen port is taken at bind time | `_serve` retries on a fresh port (bounded) | after the last attempt, the startup error surfaces with logs |
| EDGE | any other startup failure | no retry; the error surfaces with captured logs | unchanged |

</frozen-after-approval>

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 0 medium / 3 low / 0 false / 0 maybe-false.** Two patched, one rejected (plan-verification wording, corrected as hygiene).
- **The `_serve` retry only covers the fail-to-bind case** — **verdict: low**. Verified: `_wait_for_health` accepts any `200` without confirming the responder is the spawned uvicorn, so a foreign process that grabbed the port and answers `/health` during startup could be adopted (no retry). Astronomically narrow — it needs a local process to take the exact ephemeral port and serve `/health`. **route: patch** — the `_serve` docstring no longer claims the race "cannot fail a run"; the residual is accepted.
- **Three consecutive blank lines (E303) after `_port_was_taken`** — **verdict: low**. Verified (`conftest.py:71-73`). **route: patch** — reduced to two.
- **The plan's own verification (`grep -c 'janbot.api.main:app' → 1`) did not hold (returns 2)** — **verdict: low**, **rejected** (fix edits the plan). Corrected as hygiene: the check now names the single argv construction and the docstring mention.

## Verification

**Commands:**
- `env -u OPENAI_API_KEY uv run pytest -q` -- expected: every existing test passes (the keyed e2e rows skip).
- `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` -- expected: keyless e2e rows pass.
- `grep -n '"uvicorn"' tests/e2e/conftest.py` -- expected: one argv construction (inside `_uvicorn_command`); the only other match is the module docstring.
