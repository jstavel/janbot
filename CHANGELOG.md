# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Configuration module `janbot.config`: stdlib-only `JANBOT_*` environment loading (model mode, locked snapshot, corpus and index paths) with documented defaults and fail-fast mode validation.
- CI workflow (GitHub Actions): installs uv, syncs locked dependencies, and runs `pytest` on every push and pull request.
- Milestone 1, epics 2–4: org-mode ingestion with fail-closed scope, the DSPy answer + citation pipeline via `/chat`, and the end-to-end test suite (planned, not yet built).

### Documentation

- `README.md`: a **Configuration** section documenting the `JANBOT_*` variables, and updated status and package-layout sections.
- `ARCHITECTURE.md`: a cross-cutting **Configuration** subsection; added GitHub issue and PR templates.

## [0.1.0] - 2026-10-05

### Added

- Project scaffold: `uv`-managed Python project with the `src/janbot` layout (`api`, `pipeline`, `ingest`, `store`, `llm`) and pinned Milestone 1 dependencies.
- FastAPI application with a `GET /health` endpoint returning `{"status": "ok"}`.
- pytest + httpx smoke tests covering package import, pinned dependency versions, and the health endpoint.
- Specification and planning artifacts under `_bmad-output/`: the capability spec, the architecture spine (ports-and-adapters) with decision records, and the Milestone 1 ticket tree.
- `README.md` and the MIT `LICENSE`.
