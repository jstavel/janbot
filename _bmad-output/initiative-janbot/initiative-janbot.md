---
tracker_id: ""
key: ""
type: initiative
title: "JanBot — autonomous AI career assistant"
parent: none
covers: [CAP-1, CAP-2, CAP-3, CAP-4, CAP-5, CAP-6, CAP-7, CAP-8, CAP-9]
after: []
assignee: ""
risk: high
---

# JanBot — autonomous AI career assistant

## Description

JanBot answers recruiter questions accurately and contextually from the owner's personal org-mode documentation and professional profile, and does so as a rigor-first demonstration of modern AI engineering and SDET practice. The spec owns the capabilities, constraints and non-goals; this initiative delivers them across Milestones 1–3. This ticket tree currently plans **Milestone 1** as its epics.

## Outcome

A recruiter can send a real question to the service and receive an accurate, cited answer drawn only from the owner's public profile — the spec's success signal.

## Requirements

The requirement source is the spec: `_bmad-output/initiative-janbot/spec-janbot/spec-janbot.md`. Its capability ids `CAP-1`…`CAP-9` are owned by the epics below; constraints live in the spec's Constraints section, and the architecture spine fixes the invariants that keep the epics consistent.

## Done when

1. CAP-1–CAP-7 are delivered to production from Milestone 1 (CAP-8 in Milestone 2, CAP-9 in Phase 2).
2. A real recruiter question returns an answer with correct citations drawn only from `public_profile_org/`.
3. Private notes outside the public folder provably never enter the index.
4. CI runs deterministic endpoint tests that pass green on every change.
5. The Milestone 1 test layer is pytest + httpx only — no TypeScript.

## Boundaries

Milestone 1 is one vertical slice: org-mode corpus → ingestion/scope → DSPy retrieval + answer → `/chat` contract → endpoint tests. Not in M1: the TypeScript/Zod harness (M1.5), evaluation and MLFlow (M2), Clojure orchestration (M3), anonymization/guardrails (pre-deployment). See the spec's Non-goals and `_bmad-output/initiative-janbot/spec-janbot/roadmap.md`.

Tracer path across epics: `epic-foundation` scaffold → `epic-ingestion` indexes one public org file into ChromaDB → `epic-rag-chat` answers one question with a citation through `/chat` → `epic-verification` runs the end-to-end test green in CI.

## References

- spec — `_bmad-output/initiative-janbot/spec-janbot/spec-janbot.md`, section Capabilities
- spec companions — `roadmap.md` (milestones/deliverables), `decisions.md` (ADRs), `stack.md` (stack)
- architecture — `_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md`
- constraint — spec, section Constraints (fail-closed whitelist, eval determinism, layer separation)

## Notes

- Decision (2026-10-05): Milestone 1 is cut into four epics — foundation, ingestion+scope, RAG+chat, verification. The `/chat` contract was kept inside `epic-rag-chat` because a pipeline without an endpoint is not demoable and both are one owner; the contract is fixed as an invariant (AD-1, AD-4) rather than a separate epic.
- Decision (2026-10-05): Epics are sequenced foundation → ingestion → rag-chat → verification; each waits on the populated artifact of the one before.
- Unknown: the deployment/hosting target and the exact locked model snapshot are unresolved; owned at Milestone 1 configuration, neither blocks the epic order.
- Parked: CAP-8 (evaluation/MLFlow) is Milestone 2; CAP-9 (Clojure orchestrator) is Phase 2 — not placed on any Milestone 1 epic.
