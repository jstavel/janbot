---
tracker_id: ""
key: ""
type: epic
title: "End-to-end tests & CI"
parent: initiative-janbot
covers: ["CAP-7"]
after: []
assignee: ""
risk: medium
---

# End-to-end tests & CI

## Description

An end-to-end pytest + httpx suite exercises the running service through its HTTP port only — no TypeScript, no access to Python internals — and runs green in CI on every push. It covers the contract happy path, malformed input, the citation requirement, and a determinism check against the locked snapshot. This is the Milestone 1 verification layer and the closing suite across the initiative.

## Outcome

Every change to JanBot is verified by an automated, deterministic endpoint suite that turns red when the contract or grounding breaks — the spec's CAP-7.

## Requirements

- CAP-7: CI runs automated endpoint tests on every change (pytest + httpx in Milestone 1). (`spec-janbot.md`, Capabilities)

## Done when

1. A pytest + httpx suite starts the service and exercises `/chat` end to end through HTTP.
2. It asserts the contract shape, the at-least-one-citation rule, and standard error handling for malformed input.
3. A determinism test passes twice under the locked snapshot at `temperature=0`.
4. The suite runs green in CI on every push; a deliberately broken contract turns it red.
5. The suite imports no Python-internal modules — it interacts only through the HTTP port.

## Boundaries

`tests/` and the CI workflow only. Not the TypeScript/Zod harness or vitest (Milestone 1.5); not the Golden Dataset or MLFlow evaluation (Milestone 2). Tests are written for the port defined by `epic-rag-chat`.

## References

- parent — `../initiative-janbot.md`, section Requirements
- spec — `../spec-janbot/spec-janbot.md`, capability CAP-7
- architecture — `../architecture-janbot/architecture-janbot.md`, AD-1 (port-only), AD-4 (generated schemas), AD-7 (test-layer isolation and invariance)
- roadmap — `../spec-janbot/roadmap.md`, Milestone 1 Testing and CI/CD

## Notes

- Decision (2026-10-05, slicing): kept as its own epic rather than folded into `epic-rag-chat`, because verification is the project's stated USP and the closing end-to-end suite spans the whole initiative.
