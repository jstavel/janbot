---
id: SPEC-janbot
companions:
  - stack.md
  - roadmap.md
  - decisions.md
sources:
  - ~/org/h1_horizon/janbot.org
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# JanBot — Autonomous AI Career Assistant

## Why

A **vision to realize**, carrying an **opportunity to capture**. The owner wants an autonomous AI career assistant (JanBot) that answers recruiters accurately and contextually from personal documentation (org-mode files) and a professional profile, replacing manual, repetitive self-representation. The same body of work is a deliberately rigorous demonstration of modern AI engineering and SDET practice: spec-driven development, verification from day one, and test-first quality as an explicit rejection of "vibe coding". The result is both a working service and a portfolio-grade artifact.

## Capabilities

- **CAP-1**
  - **intent:** A recruiter can ask a natural-language question about the owner's professional profile and receive an answer grounded in the owner's public documentation.
  - **success:** A real recruiter-style question posted to the service returns a coherent, factually correct answer drawn from indexed public-profile content.

- **CAP-2**
  - **intent:** Every answer names the source document(s) it was derived from.
  - **success:** Each response carries at least one citation whose target is the document actually used; an answer with no citations is rejected.

- **CAP-3**
  - **intent:** The service exposes a single `/chat` HTTP endpoint with a stable, machine-validated JSON contract (answer + citations).
  - **success:** The endpoint validates its response against the Pydantic contract and returns schema-conforming JSON for both a valid question and a malformed request.

- **CAP-4**
  - **intent:** Only documents under the explicitly designated public profile folder are indexed; private notes are excluded.
  - **success:** Adding a private note outside the public folder changes no retrieval result; an automated check fails closed when a non-whitelisted path is offered.

- **CAP-5**
  - **intent:** org-mode hierarchical semantics are preserved during ingestion so answers respect the document's heading structure, properties and tags.
  - **success:** A question whose answer is scoped to a nested subtree retrieves that subtree's content as one semantic unit, not fragments split across headings.

- **CAP-6**
  - **intent:** The system supports two model modes: a locked deterministic snapshot for CI/evaluation and a flexible auto-routed mode for production.
  - **success:** The same query under the locked snapshot at temperature 0 yields identical output across runs; production routing is selectable by configuration without code change.

- **CAP-7**
  - **intent:** CI runs automated endpoint tests on every change.
  - **success:** A green CI run executes endpoint tests against the service; a deliberately broken response contract turns the run red (Milestone 1: pytest + httpx; Milestone 1.5: TypeScript regression harness).

- **CAP-8**
  - **intent:** Evaluation runs against a golden recruiter Q&A dataset with metrics for retrieval accuracy, citation correctness and hallucination detection, and applies cost-staged prompt optimization.
  - **success:** A recorded evaluation run reports the defined metrics against the golden dataset; each optimization stage (manual → BootstrapFewShot → MIPROv2) is applied only after the prior stage shows a need.

- **CAP-9**
  - **intent:** A future Clojure orchestrator fronts the Python AI service as the primary API gateway (Phase 2).
  - **success:** The existing test harness passes unchanged against the orchestrated API, proving backward compatibility.

## Constraints

- Fail-closed whitelist: the pipeline indexes only `public_profile_org/`; private notes must never enter the vector store.
- Evaluation determinism: the golden dataset and CI run against a locked model snapshot at `temperature=0` so metrics are comparable across iterations.
- Production `/chat` uses flexible auto-routing (`openrouter/auto`); CI/eval uses the locked snapshot.
- Strict separation of the Python AI/vector layer from the test layer (TypeScript via API contracts); the test layer is invariant across all milestones.
- org-mode chunking must respect subtree hierarchy, PROPERTIES drawers, LOGBOOK and tags; naive text splitters are forbidden.
- Pydantic is the single source of truth for the API contract; FastAPI OpenAPI feeds Zod codegen with zero drift.
- Prompt optimization is cost-staged (manual → BootstrapFewShot → MIPROv2); each stage only if the previous confirms the need.
- MLFlow tracking is introduced no earlier than Milestone 2.
- Clojure orchestration is deferred until the AI core is stable.

## Non-goals

- No LlamaIndex (superseded by ADR-002).
- No TypeScript test harness, Zod schemas, or vitest in Milestone 1.
- No MLFlow in Milestone 1.
- No SuperOptiX as a core dependency.
- No MIPROv2 before BootstrapFewShot proves a need.
- No Clojure orchestrator before the Python AI core is stable.
- No anonymization or guardrail layer in Milestone 1 (required only before real recruiter deployment).

## Success signal

A recruiter sends a real question to `/chat` and receives an accurate, cited answer drawn only from the owner's public profile, while CI runs deterministic, green endpoint tests over the same pipeline end-to-end from org-mode files.

## Assumptions

- The owner maintains personal documentation in org-mode, and a public profile corpus lives under `public_profile_org/`.
- Anonymization and guardrails are required before real recruiter deployment but are out of scope for Milestone 1.

## Open Questions

- Which locked model snapshot for CI/eval: `openai/gpt-4o-mini-2024-07-18` or `anthropic/claude-3.5-sonnet`?
- Does an existing `public_profile_org/` corpus exist, or must the public profile be assembled before ingestion?
- What is the deployment/hosting target for the FastAPI service and its index?
