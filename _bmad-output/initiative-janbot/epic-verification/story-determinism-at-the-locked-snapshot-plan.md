---
title: 'Determinism at the locked snapshot'
type: 'feature'
ticket: 4
created: '2026-10-13'
status: 'done'
baseline_revision: '1a3d45c6d53e9aeec32f9a77f268dd6664a97b9f'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the in-process tests prove the eval LM is *built* with the pinned snapshot, temperature `0.0` and a seed (`tests/test_llm.py`, `tests/test_config.py`), but nothing proves the **running service generates** the same answer for the same question — the determinism CAP-7/Done-when 3 asks for is a property of the shipped HTTP path, not just the adapter. A naive "post twice and compare" cannot prove it: DSPy caches responses by default and the LM is built once per app, so the second identical POST is a **cache hit** and the bodies match even when generation is nondeterministic.

**Approach:** start **two cache-cold service processes** (each with its own `DSPY_CACHEDIR`, exactly **one** POST each) under the locked eval snapshot at temperature `0`, seed `0`. Compare the two first-generation response bodies and assert they are **byte-identical**. Skipped cleanly without a model key.

## Boundaries & Constraints

**Always:**
- The e2e test module imports no `janbot` internals — `httpx`, `pytest`, the standard library only; HTTP only.
- Keyed (hitl): the real eval snapshot answers; the row is **skipped cleanly** when no model key is present.
- Each run is a **cache-cold** service start: a distinct `DSPY_CACHEDIR` and exactly one `POST /chat`, so the response is a real generation (DSPy caches by default — memory and disk).
- Pin the determinism service's config explicitly: `JANBOT_MODEL_MODE=eval`, `JANBOT_TEMPERATURE=0`, `JANBOT_SEED=0`, `JANBOT_MODEL_SNAPSHOT=openai/gpt-4o-mini-2024-07-18` — never inherit ambient values.

**Never:**
- No production-code change (`api/`, `pipeline/`, `store/`, `ingest/`, `config.py`).
- Do not modify the existing `tests/*.py` files.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | two cold eval service runs (temp `0`, seed `0`, pinned snapshot), the same question posted once per run | both `200`; the two response bodies are byte-identical | No error |
| EDGE | no model key | the row is **skipped**, not failed | clean skip |

</frozen-after-approval>

## Code Map

- `tests/e2e/conftest.py` — thread an `extra_env` override through `_service_env`/`_serve`, and add a `cold_service` **factory fixture** that starts an eval service with the pinned config and a unique `DSPY_CACHEDIR`, yielding its base URL. Existing helpers: `_serve` (`conftest.py:154`), `_service_env` (`conftest.py:144`), `fixture_index` (`conftest.py:134`).
- `tests/e2e/test_determinism_e2e.py` (new) — the keyed row: two `cold_service()` runs, one `POST /chat` each, byte-identical bodies.
- `README.md` — one line noting the determinism row and its cache-cold property.
- Do not touch: `src/janbot/**`, existing `tests/*.py`.

## Tasks & Acceptance

**Execution:**
- [x] `tests/e2e/conftest.py` -- thread `extra_env` through the service env/serve helpers and add the `cold_service` factory fixture (unique `DSPY_CACHEDIR`, pinned config) -- the cache-isolated port seam.
- [x] `tests/e2e/test_determinism_e2e.py` -- the two-cold-run determinism row -- the generation-determinism proof.
- [x] `README.md` -- note the determinism row -- docs match behaviour.

**Acceptance Criteria:**
- Given two cache-cold eval service starts at temperature `0`, seed `0` and the locked snapshot, when the same question is posted once to each, then both return `200` and the two response bodies are byte-identical.
- Given no model key, when the suite runs, then the determinism row is skipped and the rest of the suite is green.
- Given the e2e modules, when their imports are inspected, then none imports `janbot`.
- Given the whole suite keyless, when run, then every existing test passes.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13 (replan): the first pass (oneshot) reused the session `service_base_url` and posted twice; review found the second POST is a DSPy cache hit (dspy 3.4.0 defaults `cache=True`; LM built once at `api/main.py:83`), so the row proved cache stability, not generation determinism — and it asserted a temperature/seed premise it never pinned. Gap recorded here; plan re-derived to two cache-cold runs.
- 2026-10-13 (build): implemented as planned. `_service_env`/`_serve` gained an optional `extra_env` override; `cold_service` returns a factory that starts a fresh subprocess with `extra_env={**DETERMINISM_ENV, "DSPY_CACHEDIR": <unique tmp>}`. `test_determinism_e2e.py` runs `cold_service()` twice, one `POST /chat` each, and compares `response.content` bytes. Verified keyless (`153 passed, 2 skipped`) and keyed (`1 passed`, two cold runs byte-identical).

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

- 2026-10-13: **Trigger:** review found the byte-identical assertion was satisfied by DSPy's default response cache (and the premise was ambient). **Amended (route full):** replace "two POSTs to one service" with two cache-cold service processes (distinct `DSPY_CACHEDIR`, one POST each) and pin temperature/seed/snapshot explicitly; add the `cold_service` factory seam. **Known-bad state avoided:** a determinism test that passes regardless of model nondeterminism or sampling settings. **KEEP:** the port-only HTTP harness, the keyed skip-when-no-key behaviour, and the pinned `openai/gpt-4o-mini-2024-07-18` snapshot.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens (full-route re-review)

- **Verdict counts: 0 high / 0 medium / 3 low / 0 false / 0 maybe-false.** Two rejected, one patched.
- **Plan's residual-risk note omits the citation-ordering channel** — **verdict: low**, **rejected** (the only fix edits this plan). Verified: citations are built in LM-claim order (`src/janbot/pipeline/chat.py:137`, `dict.fromkeys(normalized)`), recorded as the DW4 channel in `deferred-work.md:42`; the row compares full bodies, so the channel is in scope. Under deterministic generation at temperature 0 the order is stable, so no present defect; the plan's Design Notes wording is just narrower than reality.
- **Cache isolation rests on the undocumented `DSPY_CACHEDIR` and is never asserted** — **verdict: low**, **rejected**. Verified the mechanism holds today (per-process memory cache + `DSPY_CACHEDIR`-relocated disk cache; probed in `dspy/utils/caching.py:5-16`). The bad outcome (a silently vacuous row) requires a future dspy behavior change that was not shown reachable, and no clean test-side guard exists — reject rather than guard an undemonstrated state.
- **`deferred-work.md` still records the keyed double-run as not performed** — **verdict: low**. Verified: the carry-over entry (`deferred-work.md:26-28`) says the keyed eval double-run was never run, while this story delivers exactly that through the port. **route: patch** — the entry is annotated `resolved` (delivered by story 4.4).

### 2026-10-13 — quick lens — HALT (oneshot pass)

- **Verdicts: 0 high / 2 medium / 1 low / 0 false / 0 maybe-false.** One grouped pair + one finding; both routed to HALT (fix not a trivial patch).
- **DSPy's response cache made the byte-identical assertion vacuous** — **verdict: medium**. Verified: `dspy.LM` defaults to `cache=True` (dspy 3.4.0), `build_lm` never passes `cache=` (`src/janbot/llm/__init__.py:63-69`), the LM is built once and reused (`src/janbot/api/main.py:83,90`), and a persistent disk cache (`~/.dspy_cache`) plus a per-process memory cache are on by default; `DSPY_CACHEDIR` relocates it (`dspy/utils/caching.py:7`). The second identical POST is a cache hit. **route: HALT** → now the two-cold-run approach above.
- **One service instance, not "across runs"** — **verdict: medium** (same root cause; grouped). Both POSTs hit the single session service; with the cache, the second is neither a new process nor a new model call.
- **The temperature/seed/snapshot premise was ambient, not enforced** — **verdict: low**. Verified: `_service_env` spread `os.environ` (`tests/e2e/conftest.py:144-151`) and `load_config` reads `JANBOT_TEMPERATURE`/`JANBOT_SEED`/`JANBOT_MODEL_SNAPSHOT` from it (`src/janbot/config.py:114-140`). **route: HALT** → the `cold_service` fixture pins all three.

## Design Notes

- Why two processes, not two POSTs to one: DSPy caches responses (memory + `~/.dspy_cache`) by default and the LM is built once per app, so a second identical POST never re-generates. A distinct `DSPY_CACHEDIR` per process forces each run's one POST to be a cold generation — the property CAP-7 actually cares about.
- Why the config is pinned explicitly: `load_config` reads temperature/seed/snapshot from the environment, so inheriting ambient values would let the service under test run hot and silently invalidate the premise.
- Residual risk: provider-side nondeterminism at temperature `0` with a fixed seed can still flake on rare occasions; accepted (this is a keyed/hitl row, per the ticket).

## Verification

**Commands:**
- `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` -- expected: the determinism row skips; the keyless rows pass.
- `env -u OPENAI_API_KEY uv run pytest -q` -- expected: every existing test passes.

**Manual checks (keyed):**
- `uv run pytest tests/e2e/test_determinism_e2e.py -q` -- expected: the determinism row passes (two cold runs, byte-identical `200` bodies).
