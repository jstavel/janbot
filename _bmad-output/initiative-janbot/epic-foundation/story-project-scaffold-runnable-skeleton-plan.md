---
title: 'Project scaffold & runnable skeleton'
type: 'chore'
ticket: '1'
created: '2026-10-05'
status: done
baseline_revision: 'NO_VCS'
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

**Problem:** JanBot has no code. Every later Milestone 1 epic needs a runnable, reproducible Python project with the architecture spine's package layout and a test entry point before it can land anything.

**Approach:** Create a `uv`-managed Python project with a `src/janbot` layout matching the spine (`api`, `pipeline`, `ingest`, `store`, `llm`), pin the Milestone 1 dependencies, add a minimal FastAPI app with a `GET /health` route, and a pytest smoke test that imports the package and checks the route.

## Boundaries & Constraints

**Always:** deps pinned per the spine's Stack table; `src/` layout; package dirs match the spine (api, pipeline, ingest, store, llm); the smoke test imports only the public package and exercises the app through `TestClient`; no business logic yet.

**Never:** no ingestion, retrieval, DSPy program, or `/chat` endpoint (later epics); no configuration module (entry 1.2); no TypeScript tooling; no deployment/container files.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Clean install | no `.venv` | `uv sync` creates the env and installs pinned deps | Fail visibly if a pin is unsatisfiable |
| Health check | `GET /health` | `200` with `{"status": "ok"}` | No error expected |
| Package import | `import janbot` | succeeds without side effects | No error expected |

</frozen-after-approval>

## Code Map

Greenfield — nothing to reuse; all files are created. Tooling present: `uv 0.11.13`; Python 3.12+ available on the machine.

- `pyproject.toml` -- project metadata, `src` layout, pinned deps, pytest config
- `.python-version` -- pin the interpreter minor
- `src/janbot/__init__.py` -- package root
- `src/janbot/api/__init__.py`, `api/main.py` -- FastAPI app + `GET /health`
- `src/janbot/pipeline/__init__.py`, `ingest/__init__.py`, `store/__init__.py`, `llm/__init__.py` -- spine layout placeholders
- `tests/test_smoke.py` -- import + health smoke test
- Reference: `_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md` (Stack table, Structural Seed)

## Tasks & Acceptance

**Execution:**
- [ ] `pyproject.toml` -- declare project, `[project].dependencies` pinned per the spine (fastapi 0.142.2, uvicorn 0.54.0, pydantic 2.13.5, dspy 3.4.0, chromadb 1.5.9, orgparse 0.5.20260926) plus `[dependency-groups].dev` (pytest 9.1.1, httpx 0.28.1), configure `[tool.pytest.ini_options]` and the `src` layout -- E1
- [ ] `.python-version` -- pin `3.12` -- E1
- [ ] `src/janbot/__init__.py` and the five subpackage `__init__.py` files -- create the spine layout -- E2
- [ ] `src/janbot/api/main.py` -- FastAPI `app` with `GET /health` returning `{"status": "ok"}` -- E1/E2
- [ ] `tests/test_smoke.py` -- assert `import janbot` works and `TestClient(app).get("/health")` is 200 -- E1/E2

**Acceptance Criteria:**
- Given a clean checkout, when `uv sync` runs, then the environment installs with no unsatisfied pins.
- Given the synced environment, when `uv run pytest -q` runs, then the smoke test passes.
- Given the synced environment, when the app is exercised, then `GET /health` returns 200 `{"status": "ok"}`.

## Implementation Notes

- Added a `.gitignore` (Python artifacts) beyond the Code Map — a scaffold needs it so `__pycache__`/`.venv` never get committed.
- `uv sync` generated `uv.lock` (unavoidable, needed for reproducible installs); included in the change.
- Review patches applied: `test_dependencies_importable` now checks pinned versions via `importlib.metadata.version` (no driven-adapter imports); removed `pythonpath = ["src"]` so imports come from the installed package.
- Verified: `uv sync` ok; `uv run pytest -q` → 3 passed; `/health` TestClient one-liner exit 0.

## Plan Change Log

## Review Triage Log

Verdict counts: low 3.

- low | patch | `tests/test_smoke.py:11` — `test_dependencies_importable` imports chromadb/dspy/orgparse/fastapi/pydantic modules, coupling the test layer to driven adapters; contradicts the plan boundary and AD-2/AD-7. Verified real. Smallest fix: check pinned versions via `importlib.metadata` instead of importing modules.
- low | patch | `pyproject.toml:30` — `pythonpath = ["src"]` path-hacks imports and masks whether the package installs; contradicts the plan's design intent. Verified real. Smallest fix: remove the line, rely on the hatchling install.
- low | patch | diff artifact — `uv.lock` exists in the tree but is absent from the staged diff, so E1's reproducibility is not evidenced in the change under review. Verified real. Fix: include `uv.lock` in the staged diff.

## Design Notes

`uv` with a `src/` layout matches the spine and keeps imports honest (the package must be installed, not path-hacked). Deps are pinned exactly so later epics inherit a fixed substrate. The app is a module-level `app` object so `uvicorn janbot.api.main:app` and `TestClient(app)` both work without an app factory yet.

## Verification

**Commands:**
- `uv sync` -- expected: environment created, exit 0
- `uv run pytest -q` -- expected: smoke test passes
- `uv run python -c "from fastapi.testclient import TestClient; from janbot.api.main import app; assert TestClient(app).get('/health').status_code == 200"` -- expected: exit 0
