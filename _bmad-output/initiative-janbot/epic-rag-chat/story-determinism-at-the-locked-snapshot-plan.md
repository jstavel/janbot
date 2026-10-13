---
title: 'Determinism at the locked snapshot'
type: 'feature'
ticket: 5
created: '2026-10-13'
status: 'built'
baseline_revision: '4110fa170d29239a641aa804fd2d764cad8af0a5'
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

**Problem:** The eval/CI model mode is already selected by configuration (AD-5), but nothing pins *sampling reproducibility*: `build_lm` assembles only `model` + `temperature`, so eval determinism rests entirely on the provider's temperature-0 behavior, and no test proves that two runs of the same query at the locked snapshot return identical output. A mis-set `JANBOT_TEMPERATURE` silently breaks eval comparability — the exact failure ADR-004/AD-5 exist to prevent (CAP-6).

**Approach:** Pin determinism at the LM seam and prove it at the port. Add a fixed, configuration-driven `seed` applied to the locked eval snapshot, keep the documented `temperature=0` default, then add tests that (a) the same question returns identical `/chat` output across runs and (b) switching to `openrouter/auto` is an environment-only change. Production (`openrouter/auto`) stays flexible and seed-free.

## Boundaries & Constraints

**Always:**
- Model mode, snapshot, temperature and seed come from configuration only; no code branch selects a model or its parameters by caller identity (AD-5).
- The determinism pin applies in `eval` mode (`resolve_model` → locked snapshot); production routing is unchanged.
- Two app instances built from identical env produce identical LM construction kwargs; one app returns byte-identical `/chat` JSON for the same question.
- Preserve all story 3.1/3.2/3.3/3.4 pins: the exact eval/production `build_lm` kwargs shape, `janbot.store` before `dspy` import order, boot key gate, `/health`, 422/503/500 envelope shapes, and the corpus-relative citation form.
- The documented default `JANBOT_TEMPERATURE` stays `0.0`.

**Never:**
- No changes to `pipeline/chat.py`, `store/`, `ingest/`, `api/contract.py`, or `api/main.py` (routing is already config-only; touching it would break the "configuration only" intent).
- No DSPy compilation or prompt optimization (Milestone 2); no response caching; no new contract fields or routes.
- Do not require, set, or document a seed for production `openrouter/auto`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | eval config, same question posted twice to one app | two identical `200` bodies (`answer` + `citations`) | No error |
| HAPPY | two apps built from identical env | identical LM construction kwargs both times | No error |
| EDGE | production config | kwargs carry `openrouter/auto`, `api_base`, `api_key`; no seed | No error |
| EDGE | `JANBOT_SEED` unset | default seed applied in eval; identical to explicit default | No error |
| ERROR | `JANBOT_SEED` non-integer | fail-fast at config load naming the variable | `ValueError` |

Decision (2026-10-13): the determinism pin is a fixed, configurable seed (`JANBOT_SEED`, default `0`) applied in `eval` mode only, at the `build_lm` seam — option A. Production `openrouter/auto` remains seed-free and flexible. `temperature` stays configuration-owned at the documented default `0.0` (not force-overridden), so a mis-set temperature stays visible rather than silently corrected.

</frozen-after-approval>

- `src/janbot/config.py` — add `SEED_ENV = "JANBOT_SEED"` beside `:48`, `DEFAULT_SEED` beside `:55`, a `seed: int` field on `Config` (`:61-70`), and integer parsing in `load_config` (`:120-133` block is the pattern); extend the module docstring var list (`:1-30`, currently "seven variables").
- `src/janbot/llm/__init__.py` — `build_lm` kwargs dict (`:57-60`): add `seed` only when `config.model_mode != MODEL_MODE_PRODUCTION`; leave the production branch (`:62-69`) untouched; update the docstring (`:9-14`).
- `tests/test_config.py` — seed default, override, and invalid rows modelled on the temperature rows (`:157-182`); extend the `_clear_janbot_env` fixture (`:17-28`).
- `tests/test_llm.py` — update the exact-kwargs pins (`:75`, `:84`, `:97-102`) for the eval seed and assert production stays seed-free; extend `_clear_janbot_env` (`:33-44`).
- `tests/test_chat.py` — new determinism rows: double-post to one app → identical JSON; two identical-env apps → identical JSON; assert `factory.history` eval entry includes seed and production entry does not. Reuse `indexed_corpus` (`:80-96`), `_chat_env` (`:99-104`), `create_app`, `StubLMFactory` (`:35-49`), `TestClient`.
- `README.md` — Chat/model-mode section: state the locked snapshot is pinned at `temperature=0` with a fixed seed; production is `openrouter/auto`, unprefixed by a seed.
- Do not touch: `pipeline/chat.py`, `store/`, `ingest/`, `api/main.py`, `api/contract.py`.

## Tasks & Acceptance

**Execution:**
- [x] `src/janbot/config.py` -- add `JANBOT_SEED` env, default, `Config.seed` field, parsing/validation -- the seed becomes configuration, not code.
- [x] `src/janbot/llm/__init__.py` -- add `seed` to eval `build_lm` kwargs, leave production seed-free -- the determinism pin lands at the LM seam the epic assigns to `llm/`+config.
- [x] `tests/test_config.py` -- seed default/override/invalid rows -- config contract proven.
- [x] `tests/test_llm.py` -- eval kwargs pin includes seed; production pin unchanged -- seam contract proven.
- [x] `tests/test_chat.py` -- double-post and two-app determinism rows -- CAP-6 proven through the port.
- [x] `README.md` -- document the pin -- docs match behavior.

**Acceptance Criteria:**
- Given an eval-configured app and the stub LM, when the same question is posted twice, then the two JSON bodies are identical.
- Given two apps built from identical env, when their LM kwargs are inspected, then the eval kwargs are identical and include the configured seed.
- Given a production-configured app, when its LM kwargs are inspected, then `model` is `openrouter/auto` with `api_base`/`api_key` and no `seed`.
- Given `JANBOT_SEED` is not an integer, when config loads, then it fails fast with a `ValueError` naming `JANBOT_SEED`.
- Given the full suite, when run, then every 3.1/3.2/3.3/3.4 pin passes unchanged.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- `config.py`: added `SEED_ENV`/`DEFAULT_SEED`, a `seed: int` field, and integer parsing modelled on the temperature path (no positivity constraint, matching the plan; negative seeds are accepted). Module docstring updated to "eight variables".
- `llm/__init__.py`: `seed` is added to the kwargs when `config.model_mode != MODEL_MODE_PRODUCTION`, so eval (the only non-production mode) carries it and production stays seed-free. Production branch untouched.
- `tests/test_chat.py`: one app builds one `DummyLM` at startup and `DummyLM` consumes scripted answers, so a second `/chat` to the same app exhausted the single-script stub with `AdapterParseError`. `StubLMFactory` now scripts `REPEATS=16` identical canned answers, giving every request the same deterministic output. This keeps the existing single-request tests unchanged while enabling the double-post determinism row.
- Existing `test_chat` kwargs pins (happy path and routing) were extended with `"seed": 0`, and the routing row now also asserts the production entry carries no `seed`.
- Verification: `uv run pytest -q` -> 119 passed (107 baseline + 12 new). No ruff/mypy configured in `pyproject.toml`.

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 0 medium / 1 low / 0 false / 0 maybe-false.** One finding routed to patch; one to defer.
- **README.md:69 eval determinism claim overstates the guarantee** — **verdict: low**. Verified: the sentence asserts the snapshot "is pinned at `temperature=0` … so the same question returns the same answer across runs", but `JANBOT_TEMPERATURE` is configuration-owned and passed through unmodified (`src/janbot/config.py:114-123`; `src/janbot/llm/__init__.py:62-68`) and the plan's Design Notes explicitly record that it is *not* force-overridden. A valid `JANBOT_TEMPERATURE=0.7` in eval breaks the implied guarantee while the README states it as unconditional. **route: patch** — qualify the wording to the documented default and drop the absolute cross-run promise.
- **CHANGELOG.md `[Unreleased]` gained no entry** — **verdict: low**. Verified: the repo policy ("All notable changes … are documented in this file") is not followed for the new `JANBOT_SEED` variable. But the section is stale since story 2.1 (`git log -- CHANGELOG.md` ends at `2d1aa2d`) and stories 3.1–3.4 also added none, so this is a pre-existing repo-wide gap the diff perpetuates, not one caused by this change. **route: defer** — recorded in `deferred-work.md`.

## Design Notes

- Why a seed at the LM seam: temperature 0 removes most sampling variance but does not *guarantee* identical output across runs; a fixed seed is the standard hardening. It rides the existing `build_lm` kwargs assembly, so it is configuration, not a new code path — consistent with the epic's "entry 5 stays in `llm/`+config".
- Why eval only: `openrouter/auto` routes across providers where a seed is meaningless or rejected; production is meant to stay flexible. The seed is therefore a property of the deterministic mode, like `model_snapshot`.
- Why not force `temperature=0` in eval: AD-5 makes every tunable configuration-owned; silently overriding an operator's setting would hide the misconfiguration instead of surfacing it. The default stays `0.0` and is asserted.
- Caveat: the port determinism test uses the stub `DummyLM`, so it proves the pipeline adds no per-request nondeterminism (ordering, dedup) — it cannot prove provider-level reproducibility. Real reproducibility is a keyed manual check below.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (107 baseline + new seed/determinism rows)

**Manual checks (keyed, eval mode):**
- Start: `JANBOT_MODEL_MODE=eval uv run uvicorn janbot.api.main:app`
- Post the same question twice (or run the process twice) and diff the bodies -- expected: identical `answer` and `citations`.
- Re-run with `JANBOT_MODEL_MODE=production` (and `OPENROUTER_API_KEY`) -- expected: routing switches with no code change.
