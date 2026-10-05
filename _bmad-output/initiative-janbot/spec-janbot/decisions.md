# JanBot — Architecture Decision Records

Companion to `spec-janbot.md`. Historical decision log; older ADRs are not edited — new ADRs supersede or extend them.

## ADR-001: LlamaIndex + ChromaDB as RAG base — SUPERSEDED by ADR-002

- **Status:** Superseded. **Date:** 2026-09 (founding decision).
- **Decision:** Python + FastAPI as API gateway; LlamaIndex as RAG orchestrator (chunking, embedding, retrieval, synthesis); ChromaDB as vector store; OpenRouter (`openrouter/auto`) for LLM routing.
- **Consequences:** Fast start, broad community/docs. Cost: manual prompt engineering; weak experiment traceability.

## ADR-002: Revise AI stack — DSPy as core pipeline, MLFlow for evaluation — ADOPTED 2026-10-04

- **Status:** Adopted. **Date:** 2026-09-22 (proposed), 2026-10-04 (adopted).
- **Logbook:** 2026-09-22 proposed after the *SuperAgentic AI Show* podcast and stack analysis; 2026-10-04 adopted, roadmap updated, architecture unified, ADR-001 officially superseded.
- **Context:** LlamaIndex requires manual prompt engineering, contradicting the spec-driven, anti-"vibe coding" philosophy.
- **Decision:** Hybrid — DSPy replaces LlamaIndex as the core RAG pipeline (programmatic module composition, automatic prompt optimization); ChromaDB stays as vector store; OpenRouter stays for routing; MLFlow Tracking added only in Milestone 2; SuperOptiX not a core dependency; the TypeScript/Zod/reactive-testing test layer is unchanged and untouchable; FastAPI wrapper stays but calls DSPy instead of LlamaIndex.
- **Reasons:** DSPy is principled — write a program that optimizes itself, fitting spec-driven work. MLFlow only matters at evaluation. SuperOptiX is little-known; a core dependency in Milestone 1 is unjustified. The TypeScript testware is the key USP and SDET signal.
- **Consequences:** 🟢 automatic prompt optimization; 🟢 stronger portfolio signal; 🟢 experiment traceability from Milestone 2. 🟡 higher initial investment (DSPy+ChromaDB+org parsing not off-the-shelf); 🟡 Milestone 1 must be reworked from LlamaIndex to DSPy. 🟢 test layer untouched.
- **Fixed boundaries:** separation of AI and test layers; OpenRouter routing; TypeScript reactive-testing as primary verification; Clojure orchestrator as future Phase 2 (independent of the Python AI stack choice).
- **Addendum — cost of DSPy optimization (2026-09-22):** MIPROv2 costs $6–15 per compilation (30 trials × ~10 LLM calls). Do not use it immediately. Start manual prompt → `BootstrapFewShot` (near-free) → MIPROv2 only when production accuracy demands it. Compilation amortizes over repeated operation; for one-off extraction manual prompting is cheaper.

## ADR-003: Clojure orchestrator — FUTURE

- **Status:** Planned (do not start before the AI core stabilizes). **Date:** unspecified (Phase 2).
- **Decision:** Unchanged from the original assignment.
- **Consequences:** Unchanged.

## ADR-004: Model routing — deterministic for CI/eval, auto for production — PROPOSED 2026-10-05

- **Status:** Proposed. **Date:** 2026-10-05.
- **Logbook:** 2026-10-05 proposed following external project review (`pripominky-k-projektu.org`).
- **Context:** External review flagged `openrouter/auto` in CI/CD and golden-dataset evaluation. Automatic routing changes the model underneath, making it impossible to tell whether quality dropped or the model changed — flaky tests and incomparable metrics.
- **Decision:** Two model modes — CI/CD regression tests (TypeScript) and golden-dataset evaluation use a locked deterministic snapshot at `temperature=0` (recommended `openai/gpt-4o-mini-2024-07-18` or `anthropic/claude-3.5-sonnet`); production `/chat` uses `openrouter/auto` or a defined fallback sequence. Pydantic output signatures (`ChatResponse`, `Citation`) are the source of truth for the JSON contract; FastAPI OpenAPI → Zod codegen (single source of truth, zero drift).
- **Consequences:** 🟢 deterministic CI/evaluation (metric change = pipeline change); 🟢 no Python↔TS contract drift; 🟡 two model configurations to maintain; 🟢 codegen is one-time then runs in CI.
- **Fixed:** OpenRouter as provider (only routing strategy changes); test layer stays TypeScript; Pydantic as the single API-contract source of truth.
