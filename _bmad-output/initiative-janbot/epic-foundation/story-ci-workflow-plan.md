---
title: 'CI workflow'
type: 'chore'
ticket: '3'
created: '2026-10-05'
status: done
baseline_revision: '6795fc7549fc082d9447f119019028d163edd438'
route: 'oneshot'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-janbot/epic-foundation/epic-foundation.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The test suite only runs locally, so a broken response contract or failing test can be merged; E4 requires CI to run pytest on every change.

**Approach:** Add `.github/workflows/ci.yml` using `actions/checkout@v7` and `astral-sh/setup-uv@v10` (verified current 2026-10-05), installing the pinned Python and dependencies via `uv sync --locked`, then running `uv run pytest -q` on `push` and `pull_request`.

</frozen-after-approval>

## Implementation Notes

Oneshot: one new ~40-line YAML file, mechanical, no Python code touched.

Post-review fix: `astral-sh/setup-uv@v10` was not a resolvable tag (GitHub API `GET /git/ref/tags/v10` → 404); pinned to the real release tag `v10.2.0`. `actions/checkout@v7` verified to resolve.

## Review Triage Log

- high | patch | `.github/workflows/ci.yml:18` — `astral-sh/setup-uv@v10` is a dead ref (verified: tag `v10` → 404, `v10.2.0` → 200), so every run fails before any step; fixed to `astral-sh/setup-uv@v10.2.0`.
- low | patch | `CHANGELOG.md` — the CI workflow lacked an `[Unreleased]` entry; added one.
- low | rejected | `.github/workflows/ci.yml` — toolchain not pinned (uv floating latest, Python patch) — developers rarely hit it (dependencies are locked, CI still runs) and the fix adds parameters; not worth it.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: 12 passed (the suite the workflow runs)
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"` -- expected: `yaml ok` (manual read of the workflow as fallback if PyYAML is unavailable)
