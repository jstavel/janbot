---
title: 'Config contract & corpus-root hardening'
type: 'feature'
ticket: '1'
created: '2026-10-05'
status: done
baseline_revision: '085f5b3221fd378dcc8c6af7ad53eb10e4229b85'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-janbot/epic-ingestion/epic-ingestion.md'
  - '_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md'
  - '_bmad-output/initiative-janbot/spec-janbot/spec-janbot.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `janbot.config` is the substrate for the fail-closed corpus root and the vector index, but as built it resolves paths against the process CWD, treats an empty env value as set, matches the mode exactly (brittle to case/whitespace), does not validate the snapshot, and its tests assert the module's own constants — so a renamed prefix or changed default stays green while the documented `JANBOT_*` contract silently breaks.

**Approach:** Harden `janbot.config`: trim values and treat blank as unset, normalize the model mode, validate the snapshot, and resolve `corpus_path`/`index_path` against an explicit project root (derived from the package location, overridable by `JANBOT_PROJECT_ROOT`) with `~` expansion. Rewrite the config tests to assert the documented literal contract and its edge cases, and make the smoke tests actually import the dependencies and the spine subpackages.

## Boundaries & Constraints

**Always:** stdlib only; env names prefixed `JANBOT_`; `load_config(env=None)` keeps the mapping seam; the corpus root is the fail-closed root and defaults to `public_profile_org` — this entry supplies and validates the path only; tests assert literal env names and literal default values; `Config` stays frozen.

**Never:** no scope-filter enforcement (entry 2.4); no store, embedding or org parsing (entry 2.2); no DSPy/`/chat`; no production routing, `temperature` or `top-k` (deferred to `epic-rag-chat`); no secrets; no `.env`/config-file support.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Defaults | no `JANBOT_*` | mode `eval`, default snapshot, corpus/index resolved under the project root | No error |
| Blank/whitespace value | `JANBOT_MODEL_MODE=""` or `"  "`, or blank path | treated as unset → the documented default | No error |
| Mode normalization | `"Production"`, `" production "` | `model_mode == "production"` | No error |
| Invalid mode | `"bogus"` | raises `ValueError` naming `JANBOT_MODEL_MODE` and the allowed values | Fail fast |
| Blank snapshot | `JANBOT_MODEL_SNAPSHOT=""` | falls back to the default snapshot | No error |
| Relative path | `JANBOT_CORPUS_PATH="corpus"` | resolved to `<project root>/corpus` (absolute) | No error |
| Tilde path | `JANBOT_CORPUS_PATH="~/x"` | `~` expanded to the home directory (absolute) | No error |
| Absolute path | `JANBOT_CORPUS_PATH="/tmp/x"` | used as-is (resolved, absolute) | No error |
| Project-root override | `JANBOT_PROJECT_ROOT=/tmp/z` + relative path | relative path resolves under `/tmp/z` | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/config.py` -- MODIFY. Current API: constants `MODEL_MODE_EVAL/PRODUCTION/MODES`, env-name constants, `DEFAULT_*` constants, frozen `Config(model_mode, model_snapshot, corpus_path, index_path)`, `load_config(env=None)`. Add: a value-cleaning helper (trim, blank→unset), mode normalization, snapshot validation, a `PROJECT_ROOT`/`JANBOT_PROJECT_ROOT` base, and path resolution (`expanduser` + relative-to-root + `resolve`).
- `tests/test_config.py` -- REWRITE. Currently asserts against module constants (`MODEL_MODE_ENV`, `DEFAULT_*`) — replace with literal `JANBOT_*` names and literal default values, plus the matrix edge cases; keep the autouse env-clearing fixture.
- `tests/test_smoke.py` -- MODIFY. `test_dependencies_importable` currently checks `importlib.metadata.version` only — make it import the modules too; add a test importing `janbot.pipeline`, `janbot.ingest`, `janbot.store`, `janbot.llm`.
- Reference: `architecture-janbot.md` AD-3 (fail-closed boundary), AD-5 (config not code); `spec-janbot.md` Constraints.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/config.py` -- add `_clean` (strip, blank→`None`), `PROJECT_ROOT` (from `__file__`, overridable by `JANBOT_PROJECT_ROOT`), `_resolve_path`, mode normalization + validation, snapshot blank→default; update the docstring -- entry 2.1
- [ ] `tests/test_config.py` -- assert literal env names/defaults + every matrix row -- entry 2.1
- [ ] `tests/test_smoke.py` -- import the dependencies and assert versions; add spine-subpackage import test -- entry 2.1

**Acceptance Criteria:**
- Given no `JANBOT_*` variables, when `load_config()` runs, then mode/snapshot equal the documented literals and `corpus_path`/`index_path` are absolute under the project root.
- Given a blank or whitespace value for any variable, when `load_config()` runs, then that field takes its documented default.
- Given `JANBOT_MODEL_MODE=Production` or `" production "`, when `load_config()` runs, then `model_mode == "production"`; given `"bogus"`, then `ValueError`.
- Given a relative corpus path and `JANBOT_PROJECT_ROOT`, when `load_config()` runs, then the path resolves under that root; `~/x` expands to home.
- Given the test suite, when `pytest` runs, then the dependency modules and the four spine subpackages are actually imported.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Verdict counts: low 4, medium 1.

- low | rejected | `src/janbot/config.py` snapshot — blank→default IS implemented and tested; further format validation is unspecified (no valid-model set exists yet) and premature — belongs with the model set in `epic-rag-chat`. Rejected as low.
- low | patch | `tests/test_smoke.py` — `uvicorn` is a declared dependency but not imported (the retrospective flagged uvicorn untested); add it to the import tuple.
- low | patch | `tests/test_config.py` — the project root is asserted only through the module's own `PROJECT_ROOT` constant, so a regression in the derivation stays green; add an independent anchor assertion from `tests/`.
- medium | defer | `src/janbot/config.py` — eager `.resolve()` canonicalizes symlinks, while the epic's public folder holds symlinked files; the scope filter (entry 2.4) must define the symlink policy (compare against the expanded/configured path, not a symlink-resolved root). Recorded in `deferred-work.md`.
- low | patch | `README.md` / `CHANGELOG.md` — the documented `JANBOT_*` contract is not updated for `JANBOT_PROJECT_ROOT` and the new path semantics.

## Design Notes

Project root is derived from the module location (`Path(__file__).resolve().parents[2]` → repo root) so relative paths no longer depend on the CWD, and is overridable via `JANBOT_PROJECT_ROOT` for tests and for packaged deployments where the file-derived root is meaningless. Paths are `expanduser()`-ed then, if still relative, joined to the root, then `.resolve()`-ed to an absolute canonical path. Blank handling is centralized in `_clean` so "empty means unset" holds for every variable uniformly.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass
- `uv run python -c "from janbot.config import load_config; print(load_config({}))"` -- expected: absolute `corpus_path`/`index_path` under the repo root, mode `eval`
- `JANBOT_MODEL_MODE=Production JANBOT_CORPUS_PATH=~/x uv run python -c "from janbot.config import load_config; c=load_config(); print(c.model_mode, c.corpus_path)"` -- expected: `production` and the absolute home `x` path
