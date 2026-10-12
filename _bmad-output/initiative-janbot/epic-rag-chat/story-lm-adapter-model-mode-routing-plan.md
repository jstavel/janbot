---
title: 'LM adapter & model-mode routing'
type: 'feature'
ticket: 1
created: '2026-10-12'
status: 'built'
baseline_revision: '731036f'
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

**Problem:** JanBot's LLM layer does not exist: `src/janbot/llm/` is an empty package, and `Config` carries model mode + snapshot but no LM adapter and no temperature/top-k routing knobs — so the `/chat` DSPy pipeline (story 3.2) has nothing to build its LM on.

**Approach:** Add `janbot.llm` with pure-config model-mode routing (`resolve_model`) and a `build_lm` factory behind an injectable LM-construction seam; extend `Config` with `temperature` (default `0.0`) and `top_k` (default `3`) read from new `JANBOT_TEMPERATURE` / `JANBOT_TOP_K` vars.

## Boundaries & Constraints

**Always:**
- Model mode is configuration only (AD-5): `eval` resolves to `config.model_snapshot` at `config.temperature`; `production` resolves to `openrouter/auto` with the OpenRouter base URL; switching modes changes only environment, never code.
- `Config` reads no secrets: the OpenRouter key is an explicit `api_key` parameter to `build_lm` (sourcing is story 3.2's open `unknown`), never a `Config` field.
- New config vars follow the established `JANBOT_*` prefix; a blank/whitespace value counts as unset (existing `_clean` behavior).
- Tests never construct a real `dspy.LM` (no network): the seam is an injectable `lm_factory`.

**Never:**
- No changes to `store/`, `ingest/`, or `api/` (wiring `top_k` into retrieval is 3.2).
- No DSPy program, no `/chat` route (3.2).
- No prompt compilation/optimization (Milestone 2).
- No hardcoded API key, and no decision on the OpenRouter env var name (that is 3.2's `unknown`).
- Do not rewrite `test_config.py`'s existing literal-contract assertions; extend them.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | no env | `load_config()` → `eval`, snapshot default, `temperature == 0.0`, `top_k == 3`; `resolve_model` → snapshot | No error |
| HAPPY | `JANBOT_TEMPERATURE=0.7`, `JANBOT_TOP_K=5` | parsed into config | No error |
| HAPPY | `JANBOT_MODEL_MODE=production`, `api_key` given | `resolve_model` → `openrouter/auto`; stub `lm_factory` records `api_base` + `api_key` | No error |
| HAPPY | `eval` mode | `build_lm` stub records `model` = snapshot, `temperature` from config, no `api_base`/`api_key` | No error |
| ERROR | blank `JANBOT_TEMPERATURE` / `JANBOT_TOP_K` | defaults applied | No error |
| ERROR | `JANBOT_TEMPERATURE=abc` / `JANBOT_TOP_K=0` | `ValueError` naming the env var | raise |
| ERROR | `production` without `api_key` | `build_lm` fails fast | `ValueError` |

</frozen-after-approval>

## Code Map

- `src/janbot/config.py` — add `temperature`/`top_k` to `Config`, env consts `JANBOT_TEMPERATURE`/`JANBOT_TOP_K`, defaults `0.0`/`3`; parse + validate in `load_config`; update module docstring. Existing `_clean` reused; `MODEL_MODE_EVAL`/`MODEL_MODE_PRODUCTION` exported (llm imports them).
- `tests/test_config.py` — extend the `_clear_janbot_env` autouse fixture with the two new env names; add literal-default, override, blank→default, invalid→`ValueError` tests (same style as the existing literal `JANBOT_*` contract tests).
- `src/janbot/llm/__init__.py` — new module: `OPENROUTER_MODEL = "openrouter/auto"`, `OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"`, `LMFactory` type alias, `resolve_model(config)`, `build_lm(config, api_key=None, *, lm_factory=dspy.LM)`.
- `tests/test_llm.py` — new module: routing-by-config tests + stub-factory kwargs tests (model, temperature, api_base, api_key).
- `README.md` — add the two new rows to the Configuration table (documented defaults are part of the contract).

## Tasks & Acceptance

**Execution:**
- [x] `src/janbot/config.py` -- add `temperature`/`top_k` fields, env consts, defaults, parse+validate in `load_config`, update docstring -- the config contract is the single source for model routing.
- [x] `tests/test_config.py` -- extend env-clear fixture + add literal default / override / blank / invalid tests -- the suite asserts the documented `JANBOT_*` contract literally.
- [x] `src/janbot/llm/__init__.py` -- implement `resolve_model` + `build_lm` with the injectable `lm_factory` seam -- the adapter story's core deliverable.
- [x] `tests/test_llm.py` -- routing + stub-factory tests, incl. production-without-key raising -- proves "switches by configuration alone" and "callable with a stubbed LM".
- [x] `README.md` -- add `JANBOT_TEMPERATURE` and `JANBOT_TOP_K` rows -- documentation matches the code contract.

**Acceptance Criteria:**
- Given no environment, when `load_config({})`, then `temperature == 0.0` and `top_k == 3` and `resolve_model` returns the default snapshot.
- Given `JANBOT_TEMPERATURE=0.7` and `JANBOT_TOP_K=5`, when `load_config`, then the parsed values are used; blank values fall back to defaults; invalid values raise `ValueError`.
- Given a `production` config and an `api_key`, when `build_lm(config, api_key, lm_factory=stub)`, then the stub records `model == "openrouter/auto"`, `temperature` from config, the OpenRouter `api_base`, and the `api_key`.
- Given an `eval` config, when `build_lm(config, lm_factory=stub)`, then the stub records the locked snapshot and `temperature`, with no `api_base`/`api_key`.
- Given a `production` config with no `api_key`, when `build_lm`, then a `ValueError` is raised (fail fast).
- Given only an environment change (`eval` → `production`), when `resolve_model` runs again, then the routed model changes with no code change.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

### 2026-10-12 — implementation

- All five execution tasks done. `uv run pytest -q`: 83 passed (61 baseline + 22 new: 14 config, 8 llm). Verification command prints `openai/gpt-4o-mini-2024-07-18`.
- Validation strictness beyond the matrix, kept minimal: `JANBOT_TEMPERATURE` raises only on unparseable values (no range check — `nan`/negative parse fine); `JANBOT_TOP_K` raises for any non-integer or value `< 1` (matrix only pins `0`, but negatives are equally invalid for a top-k).
- `resolve_model` carries a defensive `ValueError` for a mode outside `MODEL_MODES`: unreachable through `load_config` (which validates) but reachable if a `Config` is constructed directly.
- Test detail worth remembering: the default-factory seam is keyword-only, so its default lives in `build_lm.__kwdefaults__` (`{"lm_factory": dspy.LM}`), not `__defaults__` (which holds `api_key=None`). The identity check only reads the signature default — no test ever constructs a real `dspy.LM`.
- `build_lm` ignores a supplied `api_key` in `eval` mode (eval kwargs stay secret-free); a dedicated test pins that.
- README's `JANBOT_TOP_K` row describes the knob's eventual `/chat` role; actual wiring into retrieval is story 3.2 (default `3` matches `store/chroma.py` `query(k=3)`, so no behavior change).

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-12 — quick lens

- **README.md:56 — `JANBOT_TOP_K` row documents retrieval behavior no code implements yet.** Verified: `top_k` has no consumer outside `config.py` (grep of `src/`); `store/chroma.py` keeps its own `k=3` default. Setting `JANBOT_TOP_K=10` changes nothing today while the row reads as live. **verdict: low** — doc-only harm. **route: patch.**
- **`src/janbot/config.py:109-118` — temperature validation is parse-only (`nan`/`inf`/negative parse fine) while the sibling `top_k` knob range-checks, and README:55 "An invalid value fails fast" reads broader than the code.** Verified: only unparseable strings raise; the plan matrix pins only `abc`, and the docstring's "must parse as a number" is accurate, but the README row (part of the documented contract) overpromises. **verdict: low** — marginal in everyday use. **route: patch.**

**Grouped entry** (shared root cause: README/doc wording written for the end-state rather than the shipped contract): **patch** — smallest fix is a direct wording correction, no new guards or public surface. The step-03 implementer subagent from the interrupted session cannot be re-engaged, so patches were applied directly.

## Design Notes

The seam is `lm_factory: Callable[..., Any] = dspy.LM`. `build_lm` assembles kwargs from pure config (`model`, `temperature`) plus, only in `production`, `api_base` and a caller-supplied `api_key`; it returns `lm_factory(**kwargs)`. Tests inject a stub factory that captures kwargs, so routing is verified without ever touching the network or `dspy.LM`. `top_k` is added to `Config` but deliberately not consumed here — retrieval wiring is story 3.2; its default (`3`) matches `VectorStore.query`'s default `k` so no behavior changes until then.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (existing 61 + new config/llm tests)
- `uv run python -c "from janbot.llm import resolve_model; from janbot.config import load_config; print(resolve_model(load_config({})))"` -- expected: `openai/gpt-4o-mini-2024-07-18`
