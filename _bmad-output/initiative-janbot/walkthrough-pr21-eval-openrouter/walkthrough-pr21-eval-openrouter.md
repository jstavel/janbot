# Walkthrough — PR #21: "route the eval snapshot through OpenRouter"

Target: PR https://github.com/jstavel/janbot/pull/21 · branch `route-eval-via-openrouter` · commit `5b783a9`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the routing (`resolve_model` + `build_lm`)
- [x] Block 4 — Slice: the key env + test pins
- [x] Block 5 — Periphery

## Status

All blocks accepted: 5 of 5. Review complete: PR #21 squash-merged (`d83c570`), plan set to done.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-route-eval-via-openrouter-plan.md](../story-route-eval-via-openrouter-plan.md).

> **Problem:** the service pays two providers. In `production` mode `build_lm` sends `openrouter/auto` to OpenRouter with `OPENROUTER_API_KEY`; in `eval` mode it builds `dspy.LM(model=<snapshot>)` with **no** `api_base`/`api_key`, so the OpenAI client sends the call to OpenAI's endpoint using an ambient `OPENAI_API_KEY`. A single provider (OpenRouter) is wanted for both modes.
>
> **Approach:** route the eval snapshot through OpenRouter too — same `api_base`, keep the pinned snapshot `openai/gpt-4o-mini-2024-07-18` and the eval `seed`, and make LiteLLM use its **OpenRouter provider** by wrapping the eval wire model id in the `openrouter/` transport prefix. That prefix is required: with the bare `openai/` id plus an `api_base`, LiteLLM's OpenAI provider falls back to an ambient `OPENAI_API_KEY` and would send it to the OpenRouter host.

## Block 2 — Broad strokes

An adapter change plus test/doc updates — two spots:

- [src/janbot/llm/__init__.py:43](../src/janbot/llm/__init__.py#L43) — `resolve_model` (the `openrouter/` prefix).
- [src/janbot/llm/__init__.py:59](../src/janbot/llm/__init__.py#L59) — `build_lm` (the `api_base` + key).

## Block 3 — Slice: the routing

`resolve_model` now returns `openrouter/<snapshot>` for eval and `openrouter/auto` for production, so LiteLLM always uses its OpenRouter provider. `build_lm` sets `api_base = https://openrouter.ai/api/v1` in every mode and passes a caller-supplied `api_key` when present; production still fails fast without one.

- [llm/__init__.py:43](../src/janbot/llm/__init__.py#L43) — `resolve_model`; [llm/__init__.py:55](../src/janbot/llm/__init__.py#L55) — the `openrouter/` prefix.
- [llm/__init__.py:59](../src/janbot/llm/__init__.py#L59) — `build_lm`; [llm/__init__.py:74](../src/janbot/llm/__init__.py#L74) — `api_base`; [llm/__init__.py:80](../src/janbot/llm/__init__.py#L80) — production fail-fast.

## Block 4 — Slice: the key env + test pins

The keyed e2e rows skip on `OPENROUTER_API_KEY` now; the LM-construction pins in the in-process tests carry the new `api_base` and prefixed model id.

- [test_chat_e2e.py:21](../../../tests/e2e/test_chat_e2e.py#L21) and [test_determinism_e2e.py:30](../../../tests/e2e/test_determinism_e2e.py#L30) — the env constant.
- [test_llm.py](../../../tests/test_llm.py) and [test_chat.py](../../../tests/test_chat.py) — `DEFAULT_SNAPSHOT` = `openrouter/openai/gpt-4o-mini-2024-07-18`; eval kwargs now include `api_base`.

## Block 5 — Periphery

- [README.md:122](../../../README.md#L122) — the port-only happy-path run now names `OPENROUTER_API_KEY`.
- [story-route-eval-via-openrouter-plan.md](../story-route-eval-via-openrouter-plan.md) — the plan (`built`); Review Triage Log records the credential-leak fix.
