---
tracker_id: ""
key: ""
type: epic
title: "Workspace, tooling & CI baseline"
parent: initiative-janbot
covers: []
after: []
assignee: ""
risk: low
---

# Workspace, tooling & CI baseline

## Description

The Python project exists, runs, and is wired for the rest of Milestone 1: `uv`-managed environment, the package layout from the architecture spine (`api/`, `pipeline/`, `ingest/`, `store/`, `llm/`), configuration loading (model mode, snapshot, index path), and a CI workflow that runs the test suite on every change. No JanBot feature yet — this is the platform the other epics build on.

## Outcome

A developer can clone the repo, run `uv sync`, start the service skeleton, and see CI run the (empty) test suite green — so every later epic lands into a working, checked substrate.

## Requirements

This is the platform baseline and owns no parent capability ids; each line cites its source section.

- E1: A uv-managed Python project builds and installs its dependencies reproducibly. (`roadmap.md`, Milestone 1)
- E2: The package layout matches the architecture spine's Structural Seed. (`architecture-janbot.md`, Structural Seed)
- E3: Configuration for model mode, locked snapshot and index path loads from environment/config with documented defaults. (`spec-janbot.md`, CAP-6 / Constraints)
- E4: A CI workflow runs the test suite on every push. (`roadmap.md`, Testing layers / CI-CD)

## Done when

1. `uv sync` on a clean checkout yields a runnable environment; `uv run uvicorn janbot.api.main:app` starts the service skeleton (the documented start command).
2. The package layout matches the spine and imports resolve.
3. Configuration loads with sane defaults and is overridable by environment.
4. CI runs on push and reports the test suite (green, even if empty).

## Boundaries

Project scaffolding, dependencies, configuration and CI only. Not the ingestion pipeline (`epic-ingestion`), not the RAG pipeline or endpoint (`epic-rag-chat`), not the TypeScript toolchain (Milestone 1.5). Not deployment/hosting — deferred.

## References

- parent — `../initiative-janbot.md`, Milestone 1 scope
- roadmap — `../spec-janbot/roadmap.md`, Milestone 1 and Testing layers
- architecture — `../architecture-janbot/architecture-janbot.md`, Stack and Structural Seed
- constraint — `../spec-janbot/spec-janbot.md`, Constraints (config-driven model mode)

## Notes

- Open question: deployment/hosting target is unresolved; this epic does not need it.
- Decision (2026-10-05, inception): one lane, three entries; entry 1 is the tracer bullet (scaffold → importable package → smoke test). No closing refactor sweep — the epic has three entries, at or below the threshold. Entry 3 needs a person to push and observe CI, so `hitl = true`.
