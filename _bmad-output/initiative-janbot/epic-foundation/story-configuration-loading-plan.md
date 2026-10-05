---
title: 'Configuration loading'
type: 'feature'
ticket: '2'
created: '2026-10-05'
status: done
baseline_revision: 'b0693022a78c224192aa9ae8ba7a8ef89371bb58'
route: 'full'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md'
  - '_bmad-output/initiative-janbot/epic-foundation/epic-foundation.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The service has no way to select its model mode (CI/eval vs production), locked snapshot, or corpus/index locations — AD-5 requires these to be configuration, not code, before any later epic wires a model or an index.

**Approach:** Add a dependency-free configuration module (`janbot.config`) that reads four `JANBOT_*` environment variables with documented defaults into a frozen dataclass, validates the mode value, and is overridable per-call for testability.

## Boundaries & Constraints

**Always:** stdlib only (`os`, `dataclasses`, `pathlib`, `typing`) — no new dependency; env names prefixed `JANBOT_`; `load_config()` accepts an optional env mapping so tests never mutate the real environment; defaults documented in the module docstring and exercised by tests; invalid `JANBOT_MODEL_MODE` fails fast.

**Never:** no wiring into the FastAPI app or any adapter (later epics); no secrets in config (no API keys — the OpenRouter key is a later, separately-managed concern); no `.env` file support; no config file format (TOML/YAML) — environment only, per the spine's AD-5 and the epic's scope.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Defaults | no `JANBOT_*` variables | `model_mode="eval"`, snapshot `openai/gpt-4o-mini-2024-07-18`, corpus `public_profile_org`, index `chroma_db` | No error expected |
| Override | any `JANBOT_*` variable set | that field carries the provided value | No error expected |
| Invalid mode | `JANBOT_MODEL_MODE=bogus` | `load_config` raises before returning | ValueError naming the variable and allowed values |
| Path coercion | `JANBOT_CORPUS_PATH=some/dir` | field is a `pathlib.Path` | No error expected |

</frozen-after-approval>

## Code Map

Continuity from story 1.1 (same epic): `pyproject.toml` pins deps and owns `[tool.pytest.ini_options]` (`testpaths=["tests"]`); `tests/test_smoke.py` is the existing suite entry — new tests go in a separate `tests/test_config.py`; imports resolve from the installed package, not `pythonpath`.

- `src/janbot/config.py` -- NEW: `Config` frozen dataclass, `load_config(env=None)`, env-name constants, defaults
- `tests/test_config.py` -- NEW: defaults, per-field override, invalid-mode failure, path coercion
- `src/janbot/api/main.py` -- UNTOUCHED (no wiring this story)
- Reference: `_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md` (AD-5, Consistency Conventions "State & cross-cutting: all tunables come from config/env")

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/config.py` -- define `MODEL_MODE_EVAL`/`MODEL_MODE_PRODUCTION` constants, env-name constants with documented defaults, `Config` frozen dataclass (`model_mode`, `model_snapshot`, `corpus_path: Path`, `index_path: Path`), and `load_config(env: Mapping[str, str] | None = None)` that validates the mode -- E3
- [ ] `tests/test_config.py` -- cover the four matrix scenarios with `monkeypatch`-clean environment isolation -- E3

**Acceptance Criteria:**
- Given no `JANBOT_*` variables, when `load_config()` is called, then it returns the documented defaults.
- Given one variable set (each in turn), when `load_config()` is called, then exactly that field changes and the others keep their defaults.
- Given `JANBOT_MODEL_MODE=bogus`, when `load_config()` is called, then it raises `ValueError` naming the variable and the allowed values.

## Implementation Notes

- `janbot/config.py` placed at package root as the cross-cutting env substrate (spine Consistency Conventions row "State & cross-cutting"); `llm/` keeps CAP-6 mode logic per the spine's Capability Map.
- Review patches applied: added `test_process_environment_variable_is_picked_up` (bare `load_config()` after `monkeypatch.setenv`) and a `[Unreleased]` CHANGELOG entry.
- Verified: `uv run pytest -q` → 12 passed; `load_config({})` prints defaults; `/health` unaffected.

## Plan Change Log

## Review Triage Log

Verdict counts: false 2, low 2.

- false | — | `src/janbot/config.py` placement vs spine — refuted: the spine's Consistency Conventions treat config as cross-cutting ("State & cross-cutting … All tunables (model mode, snapshot, index path, top-k) come from config/env"), so the env substrate is not llm-owned; the Structural Seed's `llm/` comment is scaffold guidance ("the code owns the detail"), and CAP-6 still maps to `llm/` for the adapter/mode logic this module does not implement. Epic E2's layout (story 1.1) is intact.
- false | — | `src/janbot/config.py:19,22` stdlib module set — refuted: the rule's substance (stdlib-only, no new dependency) is fully satisfied; `collections.abc.Mapping` is the stdlib home of `Mapping`, `from __future__ import annotations` is a stdlib feature, and importing `typing` would add nothing (its `Mapping` is the deprecated alias).
- low | patch | `tests/test_config.py` — the `env=None → os.environ` path is only exercised for defaults; no test sets a real process variable and calls `load_config()` bare, so a regression that ignores the environment would pass. Smallest fix: one test using `monkeypatch.setenv` + bare `load_config()`.
- low | patch | `CHANGELOG.md` — the new configuration module is not recorded under `[Unreleased]` despite the repo's Keep-a-Changelog convention. Smallest fix: one Added line.

## Design Notes

`load_config(env=None)` reads `os.environ` when no mapping is given, so production calls stay one line while tests pass an explicit mapping — no `monkeypatch` of process state needed. The mode is validated at load time (fail fast, AD-5's two modes are the only legal values). Path fields become `pathlib.Path` so adapters never string-split. The snapshot default is ADR-004's recommendation, not a hard pin: it is overridable, and CI/eval determinism comes from pinning it in CI configuration later.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass (existing smoke tests unaffected)
- `uv run python -c "from janbot.config import load_config; c = load_config({}); print(c)"` -- expected: defaults printed, exit 0
