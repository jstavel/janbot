---
tracker_id: ""
key: ""
type: epic
title: "Thin TypeScript contract harness"
parent: initiative-janbot
covers: ["CAP-7"]
after: []
assignee: ""
risk: low
---

# Thin TypeScript contract harness

## Description

A `janbot-model` TypeScript package holds Zod schemas for the `/chat` endpoint, generated from the FastAPI OpenAPI (which derives from the Pydantic contract), with vitest regression tests wired into CI. It proves the Python contract and its TypeScript consumers cannot drift — the thin harness the re-scope kept, with reactive-testing deferred out of JanBot.

## Outcome

CI runs a TypeScript harness that validates `/chat` against generated Zod schemas and goes red on a broken contract, with zero hand-maintained schema drift — the spec's CAP-7 at Milestone 1.5.

## Requirements

- E1 (CAP-7): `janbot-model` holds Zod schemas for `/chat` generated from the FastAPI OpenAPI, never hand-written. (`roadmap.md`, Milestone 1.5; `architecture-janbot.md`, AD-4)
- E2 (CAP-7): CI runs TypeScript regression tests (vitest) against `/chat`. (`roadmap.md`, Milestone 1.5)
- E3 (CAP-7): A deliberately broken `/chat` response turns the TypeScript run red. (`spec-janbot.md`, CAP-7 success)
- E4 (CAP-7): Regenerating the schema from OpenAPI produces no diff — zero drift. (`spec-janbot.md`, Constraints; `decisions.md`, ADR-005)

## Done when

1. `janbot-model` Zod schemas are generated from the `/chat` OpenAPI, not hand-written.
2. CI runs vitest contract tests against a running `/chat` and passes green.
3. A deliberately broken `/chat` response turns the TypeScript run red.
4. Regenerating the schemas from OpenAPI produces no diff.
5. No reactive-testing dependency exists anywhere in JanBot.

## Boundaries

A new `janbot-model` TypeScript package and its CI job. Not the Python core, not the pytest/httpx suite, not any reactive-testing package. Consumes the `/chat` OpenAPI emitted by `epic-rag-chat`.

## References

- parent — `../initiative-janbot.md`, section Requirements
- spec — `../spec-janbot/spec-janbot.md`, capability CAP-7 and section Constraints
- roadmap — `../spec-janbot/roadmap.md`, Milestone 1.5
- decision — `../spec-janbot/decisions.md`, ADR-005 (Milestone 1.5 re-scope)
- architecture — `../architecture-janbot/architecture-janbot.md`, AD-1 (contract-first port), AD-4 (Pydantic as the single contract source)

## Notes

- Decision (2026-10-14, slicing): Milestone 1.5 is placed right after Milestone 2 in build order; it blocks nothing and waits only on the `/chat` contract from `epic-rag-chat`.
- Decision (2026-10-14): the harness is thin (Zod + vitest); the reactive-testing core/model split is deferred to a separate project (ADR-005), so no reactive-testing is used in any JanBot milestone.
- Unknown: the TypeScript toolchain and package manager for `janbot-model`; entries wait on it.
