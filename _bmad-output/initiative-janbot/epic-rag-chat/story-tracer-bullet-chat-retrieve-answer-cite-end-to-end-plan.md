---
title: 'Tracer bullet: /chat retrieve -> answer + cite end to end'
type: 'feature'
ticket: 2
created: '2026-10-12'
status: 'built'
baseline_revision: '616ac11'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** JanBot has an LM seam (story 3.1) but no `/chat` endpoint, no response contract, and no DSPy program — so a recruiter question has no path from HTTP to a grounded, cited answer. This story is the epic's tracer bullet: the thinnest path through every layer, and the only in-epic live proof of Done when 1.

**Approach:** Add a minimal Pydantic `ChatRequest`/`ChatResponse`/`Citation` contract, a `POST /chat` FastAPI route, and a manual-prompt DSPy module that retrieves `top_k` chunks from the existing Chroma index via `build_lm`/`resolve_model` and returns an answer with at least one citation naming a retrieved chunk's source. The OpenRouter key is `OPENROUTER_API_KEY`, read once at startup by the composition root (operator-supplied env var); the live HitL proof runs in production mode.

## Boundaries & Constraints

**Always:**
- Callers reach JanBot only through `POST /chat` with the Pydantic contract (AD-1); `ChatResponse`/`Citation` are defined once in Pydantic (AD-4).
- Model selection stays configuration-only (AD-5): the route builds the LM through `build_lm(config, api_key=...)` — eval → locked snapshot at `config.temperature`, production → `openrouter/auto` + OpenRouter `api_base`. `top_k` retrieval comes from `config.top_k` via `VectorStore.query(text, k=config.top_k)`.
- Citations come from the retrieved chunks' `source_path` metadata (at least one); the tracer cites what it retrieved — strict derived-from and uncited-answer rejection are story 3.4.
- The DSPy program is a `dspy.Module` with a manual-prompt signature (question + retrieved context → answer); no compilation/optimization (Milestone 2).
- Tests exercise only the HTTP port via `TestClient` (AD-7): stubbed LM (never a real `dspy.LM`, no network), temp corpus + the deterministic stub embedder from `conftest.py`.
- The API key is `OPENROUTER_API_KEY`: read once at app startup by the composition root and passed explicitly to `build_lm(config, api_key=...)`; the operator sets it in the environment before starting the server (no `.env` support; config stays secret-free). In production, a missing key fails fast at startup — it can never surface as a per-request error.

**Never:**
- No changes to `store/` or `ingest/` internals (scope filter is 3.6; citation-path rewrite is 3.4); no custom error envelope (3.3 completes it — FastAPI's default validation/500 responses are the tracer's error surface).
- No uncited-answer rejection (3.4), no determinism-across-runs proof (3.5), no grounding-boundary change (3.6), no prompt optimization (Milestone 2).
- No new secret fields or secret env vars in `config.py`; no `.env` support.
- Do not break `GET /health` or the existing suite.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | `POST /chat` with `{"question": "..."}` against an indexed corpus, key per decision | 200 `ChatResponse`: non-empty `answer`, `citations` with ≥ 1 entry, each `source` matching an indexed chunk's `source_path` | No error |
| HAPPY | mode switched eval ↔ production by env only | same route, different routed model (`config.snapshot` vs `openrouter/auto`), no code change | No error |
| ERROR | body missing `question` (or wrong type) | request rejected | FastAPI default 422 envelope |
| ERROR | production mode, `OPENROUTER_API_KEY` absent | server fails fast at startup | boot-time `ValueError` (uvicorn exits before serving) |
| ERROR | retrieval returns 0 chunks (empty index) | no answer without context | `ValueError` → 500 |

</frozen-after-approval>

## Code Map

- `src/janbot/api/contract.py` (new) — `ChatRequest{question}`, `Citation{source}`, `ChatResponse{answer, citations}`; the AD-4 single source of truth.
- `src/janbot/api/main.py` — today only `app = FastAPI(title="JanBot")` + `GET /health` (:5-10). Add a `create_app(...)` composition root (builds config → store → LM → program at startup; `app.state.program`) and the `POST /chat` route with `response_model=ChatResponse`; keep the module-level `app = create_app()` so `uvicorn janbot.api.main:app` and `test_smoke.py` keep working.
- `src/janbot/pipeline/chat.py` (new; `pipeline/` is empty) — the DSPy program: `dspy.Module` with a manual-prompt signature, retrieval `VectorStore.query(question, k=config.top_k)`, answer + citations mapped from retrieved chunks.
- `src/janbot/store/chroma.py` — reuse only: `VectorStore(index_path, embedder)` (:56), `query(text, k=3) -> [{id, text, source_path, breadcrumb}]` (:135), `default_embedder()` (:42). Query is global top-k — scope is trust-in-index until 3.6. DO NOT MODIFY.
- `src/janbot/llm/__init__.py` — reuse only: `build_lm(config, api_key=None, *, lm_factory=dspy.LM)` (:45), `resolve_model` (:36). DO NOT MODIFY.
- `src/janbot/config.py` — reuse only: `load_config`, `Config` fields incl. `temperature`/`top_k`. No changes.
- `tests/test_chat.py` (new) — `TestClient` tests per the matrix; stub LM via the injectable seams (`lm_factory`-style stub, `dspy.Module.set_lm`), temp corpus via `conftest.py` `embedder`/`write_org` fixtures.
- `tests/test_smoke.py`, `tests/conftest.py` — patterns to mimic (TestClient :4/:39; deterministic 64-dim embedder stub :22-47); extend conftest only if the env-clear fixture needs the new key var name.
- `README.md` — document the key env var (per decision) and a `/chat` curl example.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/api/contract.py` -- define `ChatRequest`, `Citation`, `ChatResponse` in Pydantic -- the port's contract, one source of truth (AD-4).
- [ ] `src/janbot/pipeline/chat.py` -- implement the manual-prompt DSPy module: retrieve `k=config.top_k`, build context from chunk text, produce answer + citations from the retrieved `source_path`s -- the tracer's core layer-crossing path.
- [ ] `src/janbot/api/main.py` -- add `create_app` composition root + `POST /chat` (response_model=ChatResponse); wire config → store → `build_lm` → program at startup -- the port, with injectable driven adapters for tests.
- [ ] `tests/test_chat.py` -- port-level tests per the I/O matrix (happy path with stub LM + temp index; 422; production-without-key raises at startup; zero-chunks 500) -- proves the route through HTTP only (AD-7).
- [ ] `README.md` -- document `OPENROUTER_API_KEY` + `/chat` usage -- operators can run the live check.

**Acceptance Criteria:**
- Given a temp-indexed corpus and a stubbed LM, when `POST /chat` carries a real question, then the 200 response has a non-empty `answer` and ≥ 1 citation whose `source` equals a `source_path` of a retrieved chunk.
- Given a body without `question`, when `POST /chat`, then the response is FastAPI's default 422 envelope.
- Given production mode and `OPENROUTER_API_KEY` absent, when the app is created, then startup raises a `ValueError` naming the missing key (fail fast before serving).
- Given eval mode with no key supplied, when `POST /chat`, then the stubbed LM records `model` = locked snapshot and `temperature` = 0 with no `api_base`/`api_key`.
- Given only an env change (eval → production), when the same route runs, then the routed model changes with no code change.
- Given a live recruiter-style question (HitL run in production mode), when posted to a running server started with `OPENROUTER_API_KEY` set, then a coherent answer with at least one citation is returned.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-12: Implemented per Code Map — `api/contract.py` (ChatRequest/Citation/ChatResponse), `pipeline/chat.py` (`ChatProgram`: `dspy.Predict` over a docstring `GroundedAnswer` signature; `VectorStore.query(question, k=top_k)`; citations = deduped retrieved `source_path`s, ValueError on 0 chunks or source-less chunks), `api/main.py` (`create_app(env=None, *, embedder=None, lm_factory=dspy.LM)` composition root: config -> store -> key check -> `build_lm` -> program -> `app.state.program`; module-level `app = create_app()` kept; key read once from `OPENROUTER_API_KEY`, production-missing-key raises at boot naming the env var), `tests/test_chat.py` (5 HTTP-only tests via `create_app` with conftest stub embedder + recording factory returning `dspy.utils.DummyLM`), README (key env var + Chat section). `store/`, `llm/`, `config.py` untouched.
- 2026-10-12: dspy 3.4.0 pitfall found by live boot failure: `import dspy` installs a lazy numpy proxy; if chromadb/numpy initializes after it, numpy import breaks (`TypeError: data type 'bool' not understood`). pytest masked it (conftest loads `janbot.ingest` -> chromadb first). Fixed by importing `janbot.store` before `dspy` in `pipeline/chat.py` and `api/main.py` — do not reorder those imports.
- 2026-10-12: Verification — `uv run pytest -q`: 88 passed (83 baseline + 5); contract import check `ok`; live HitL run in production mode (real `OPENROUTER_API_KEY`, real `chroma_db`): coherent grounded answer + 3 citations naming `public_profile_org/` sources; production boot without the key exits before serving with `ValueError: OPENROUTER_API_KEY is required in 'production' model mode`.

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-12 — quick lens

- **`src/janbot/api/main.py:61-67` — whitespace-only `OPENROUTER_API_KEY` passes the production fail-fast gate.** Verified empirically: `create_app` with `OPENROUTER_API_KEY="   "` in production boots; the truthiness checks in `main.py` and `build_lm` (`llm/__init__.py:63`) both pass it to `dspy.LM`, contradicting the frozen "fails fast at startup — never per-request" promise and the README's blank-as-unset convention. **verdict: low** (misconfiguration edge, confusing failure mode). **route: patch.**
- **`src/janbot/pipeline/chat.py:245-257` — source-less chunks ground the context but are silently dropped from citations (partial case).** Verified by read: the `if chunk["source_path"]` filter under-cites while `context` includes all chunks; the guard only raises when ALL lack `source_path`. Unreachable via the real ingest (always sets `source_path`), but it violates the plan's Design Notes invariant "cites exactly the chunks it passed as context". **verdict: low** (correctness invariant, latent). **route: patch.**
- **`tests/test_chat.py:113-162` — routing test never runs the route; AC-5's "when the same route runs" verified only at app-construction time.** Verified by read: `test_chat_model_routing_changes_with_environment_only` asserts `factory.history` with no HTTP request; a production-mode `POST /chat` is never exercised by the suite (happy path covers eval only). The startup-test half of the claim is **refuted as plan-sanctioned** — the frozen AC explicitly requires a `create_app`-level boot-failure test, which cannot be HTTP-only. **verdict: medium** (AC coverage gap on the epic's core capability through the port). **route: patch** (test-only: POST /chat in both modes and assert 200 + routed kwargs).
- **`tests/test_chat.py:15-18` — dspy-before-chromadb import order, safe only via conftest masking.** Refuted: pytest always loads `tests/conftest.py` before any test module, and conftest:17 → `janbot.ingest.__init__` → `janbot.store` → chromadb initializes the safe order for every current and future test module; the lens itself verified no supported invocation breaks. No reachable bad outcome at the cited location. **verdict: false.**

**Grouped entries & routes:** three patch items (whitespace-key gate; citation-context invariant; AC-5 port-level routing coverage), no intent_gap/bad_plan — no loopback. The `false` finding is rejected on its refutation.

## Design Notes

- Composition root: `create_app()` is the single place where driven adapters are chosen (real store/LM by default; injected stubs in tests). Tests construct their own app instance and only speak HTTP — keeps AD-7 intact without monkeypatching internals.
- Citation honesty: the tracer cites exactly the chunks it passed as context (retrieved `source_path`s), not LM-claimed sources — the thinnest correct-by-construction path; story 3.4 hardens to strict derived-from with rejection.
- DSPy wiring guidance: build the program once with `dspy.Predict` over a docstring-instruction signature; set the LM once at startup (`module.set_lm(lm)`), so the handler stays a single call.
- dspy stub for tests: a minimal fake LM object whose completions return a canned answer works through `dspy.Predict`; prefer that (or `dspy.utils.DummyLM` if it fits) over any network-touching construction.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (83 baseline + new chat tests)
- `uv run python -c "from janbot.api.contract import ChatRequest, ChatResponse, Citation; print('ok')"` -- expected: `ok`

**Manual checks (HitL live run, production mode):**
- Start: `JANBOT_MODEL_MODE=production OPENROUTER_API_KEY=... uv run uvicorn janbot.api.main:app`
- `curl -s -X POST localhost:8000/chat -H 'content-type: application/json' -d '{"question":"<real recruiter-style question>"}'` -- expected: coherent answer + ≥ 1 citation naming a `public_profile_org/` source
