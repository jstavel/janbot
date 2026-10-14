---
id: 1
type: story
title: "Repository docs reflect the Milestone 1.5 re-scope (thin TS harness)"
parent: none
covers: []
after: []
refined: true
hitl: false
risk: low
---

# Repository docs reflect the Milestone 1.5 re-scope

## Description

The spec and its companions already carry the re-scope: Milestone 1.5 is a thin TypeScript harness (`janbot-model` Zod schemas via OpenAPI codegen, vitest), sequenced after Milestone 2, and the reactive-testing core/model split is deferred out of JanBot. Bring the repository's own docs in line with that before Milestone 2 starts, so no doc contradicts the spec.

## Acceptance Criteria

1. **README milestone list matches the spec**
   **Given** `README.md`
   **When** the Status section is read
   **Then** Milestone 1.5 is named a thin TypeScript harness (Zod/vitest) and is listed after Milestone 2
2. **README testing row matches the spec**
   **Given** the README architecture table
   **When** the Tests row is read
   **Then** it names pytest + httpx for Milestone 1 and the thin Zod/vitest contract harness for Milestone 1.5, with no reactive-testing claim
3. **ARCHITECTURE.md testing table matches the spec**
   **Given** `ARCHITECTURE.md`
   **When** the Testing Strategy table is read
   **Then** the M1.5 row names the thin TypeScript/Zod contract harness, not a reactive-testing harness
4. **Issue template milestone checklist matches the spec**
   **Given** `.github/ISSUE_TEMPLATE/feature_request.md`
   **When** the milestone checklist is read
   **Then** Milestone 1.5 is named a thin TS harness and is ordered after Milestone 2
5. **Initiative boundary ordering matches the spec**
   **Given** `_bmad-output/initiative-janbot/initiative-janbot.md`
   **When** the Boundaries paragraph is read
   **Then** it no longer implies Milestone 1.5 precedes Milestone 2

## Boundaries

- Must not change: `_bmad-output/initiative-janbot/spec-janbot/` (already re-scoped), capability semantics, or any code.
- Must not change: claims already present in `README.md` about Milestone 1 behavior, the config table, or the e2e test documentation.

## References

- spec companion — `_bmad-output/initiative-janbot/spec-janbot/roadmap.md` (Milestone 1.5 section)
- ADR — `_bmad-output/initiative-janbot/spec-janbot/decisions.md`, ADR-005
- spec — `_bmad-output/initiative-janbot/spec-janbot/spec-janbot.md`, CAP-7
- initiative — `_bmad-output/initiative-janbot/initiative-janbot.md`

## Notes

- Decision: the spec re-scope landed in commit `f8d66d5`; this ticket is the repo-docs follow-through, done before Milestone 2 planning starts (2026-10-14).
- Open question: none — the docs to touch are named by the criteria above; if another doc contradicts the re-scope, fix it the same way.