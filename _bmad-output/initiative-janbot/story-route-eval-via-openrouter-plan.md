---
title: 'Route the eval snapshot through OpenRouter'
type: 'chore'
ticket: ''
created: '2026-10-13'
status: 'built'
baseline_revision: '3b44025474f79c6b9473a220530bffc254b20518'
route: 'oneshot'
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

**Problem:** the service pays two providers. In `production` mode `build_lm` sends `openrouter/auto` to OpenRouter with `OPENROUTER_API_KEY`; in `eval` mode it builds `dspy.LM(model=<snapshot>)` with **no** `api_base`/`api_key`, so the OpenAI client sends the call to OpenAI's endpoint using an ambient `OPENAI_API_KEY`. A single provider (OpenRouter) is wanted for both modes.

**Approach:** route the eval snapshot through OpenRouter too — give `build_lm` the same `api_base = https://openrouter.ai/api/v1`, keep the pinned snapshot `openai/gpt-4o-mini-2024-07-18` and the eval `seed`, and make LiteLLM use its **OpenRouter provider** by wrapping the eval wire model id in the `openrouter/` transport prefix in `resolve_model`. That prefix is required: with the bare `openai/` id plus an `api_base`, LiteLLM's OpenAI provider falls back to an ambient `OPENAI_API_KEY` and would send it to the OpenRouter host, whereas the `openrouter/` provider reads only `OPENROUTER_API_KEY`. Update the keyed e2e skip to `OPENROUTER_API_KEY`.

## Boundaries & Constraints

**Always:**
- Model wiring stays pure configuration (AD-5): no code path selects a provider by caller identity.
- Eval keeps the **locked snapshot** and its `seed`; production stays seed-free and keeps `openrouter/auto`.
- Production behaviour is unchanged (same `api_base`, same fail-fast on a missing key).

**Never:**
- No change to the configured snapshot (`config.model_snapshot` stays `openai/gpt-4o-mini-2024-07-18`); only the LiteLLM transport prefix is added when the model is routed.
- No new secret handling or `.env` support; the key stays an env-read, explicitly-passed value.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | eval mode, key present | LM kwargs carry `api_base`, `api_key`, `model=<snapshot>`, `temperature`, `seed` | No error |
| EDGE | eval mode, no key | `api_base` set, no `api_key`; build does not fail (no call is made in keyless runs) | unchanged |
| EDGE | production mode, no key | `ValueError` before building | unchanged |

</frozen-after-approval>

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: `build_lm` now always sets `api_base = https://openrouter.ai/api/v1` (eval and production) and passes a caller-supplied `api_key` when present; production fail-fast on a missing key is unchanged. The snapshot id is unchanged (`openai/gpt-4o-mini-2024-07-18` — OpenRouter serves it; probed `dspy.LM(model=…, api_base=openrouter, api_key=<OR key>)` completes with `OPENAI_API_KEY` unset). Keyed e2e skip switched from `OPENAI_API_KEY` to `OPENROUTER_API_KEY`; README updated. `tests/test_llm.py` and `tests/test_chat.py` eval-kwargs pins updated (+`api_base`).
- Verified: keyless (both keys unset) `uv run pytest -q` → 158 passed, 2 skipped; keyed via OpenRouter only (`-u OPENAI_API_KEY`) `uv run pytest tests/e2e -q` → **8 passed** (both keyed rows run through OpenRouter).
- 2026-10-13 (review fix): `resolve_model` now wraps the eval snapshot in the `openrouter/` transport prefix (`openrouter/openai/gpt-4o-mini-2024-07-18`). With the bare `openai/` id, LiteLLM's OpenAI provider falls back to an ambient `OPENAI_API_KEY` and would send it to the OpenRouter host; the prefix forces the OpenRouter provider (reads only `OPENROUTER_API_KEY`). No-leak probe (OR unset, OPENAI set) now fails fast: `LMNotConfiguredError: no API key found for provider 'openrouter'`. Test pins (`test_llm.py`, `test_chat.py`) updated to the prefixed id.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 1 medium / 2 low / 0 false / 0 maybe-false.** Two patched, one rejected.
- **Eval could send an ambient `OPENAI_API_KEY` to the OpenRouter host** — **verdict: medium**. Verified: with the bare `openai/gpt-4o-mini-2024-07-18` id + `api_base=openrouter` and no explicit key, LiteLLM's OpenAI provider falls back to `get_secret_str("OPENAI_API_KEY")` (`litellm/llms/openai/common_utils.py`), so an eval run keyed only by OpenAI would send that secret to `openrouter.ai`. **route: patch** — `resolve_model` now returns `openrouter/<snapshot>`, forcing LiteLLM's OpenRouter provider; probed (OR unset, OPENAI set): `LMNotConfiguredError: no API key found for provider 'openrouter'` — no fallback, no leak.
- **README misstated how the key is sourced** — **verdict: low**. Verified: `create_app` reads `OPENROUTER_API_KEY` and passes it explicitly (`api/main.py:76,83`), it is not "read by LiteLLM". **route: patch** — README reworded.
- **Story-3.1 plan/walkthrough records still describe eval as secret-free** — **verdict: low**, **rejected**. Historical artifacts recording 3.1's then-current state; the current wiring is documented in the `llm` module docstring and this plan (same treatment as the epic retrospective's decision to leave historical plans as written).

## Verification

**Commands:**
- `env -u OPENAI_API_KEY uv run pytest -q` -- expected: every existing test passes (keyed e2e rows skip).
- keyed via OpenRouter only: `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` (with `OPENROUTER_API_KEY` set) -- expected: the keyed rows run and pass, proving eval routes through OpenRouter.
