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

## ADR-005: Milestone 1.5 re-scope — thin TS harness, reactive-testing deferred — PROPOSED 2026-10-13

- **Status:** Proposed. **Date:** 2026-10-13.
- **Context:** the SentinelOne MVP needs the `/chat` endpoint, the evaluation pipeline (Milestone 2) and architecture docs — not a TypeScript harness. The `reactive-testing` framework carries Playwright/Kraken coupling (`CollectorFn` typed to `Page`, engine importing Kraken data), so a general core split is expensive and unlikely to be a clean "core vs model" cut.
- **Decision:** re-scope Milestone 1.5 to a **thin TypeScript harness** — `janbot-model` with Zod schemas for `/chat`, OpenAPI→Zod codegen (`openapi-zod-client`), vitest in CI — and sequence it **after Milestone 2**. The `reactive-testing` core/model split is deferred to a **separate project** (not part of JanBot); no reactive-testing is used in any JanBot milestone.
- **Supersedes:** ADR-002's "TypeScript reactive-testing as primary verification" framing — JanBot's TypeScript layer is a Zod/vitest contract harness, not reactive-testing.
- **Consequences:** 🟢 the highest-signal slice (TS contract-testing, zero drift) at ~20% of the effort; 🟢 M1.5 no longer waits on a core refactor and blocks nothing; 🟡 the fuller general core story moves to its own project with two real consumers (Kraken UI + JanBot API).

## ADR-006: Metric selection — construct orthogonality from the failure taxonomy, not from correlation — ADOPTED 2026-10-15

- **Status:** Adopted (owner decision). **Date:** 2026-10-15.
- **Context:** the evaluation harness (Milestone 2, epic `epic-evaluation`, entries 17 and 18 in `_bmad-output/initiative-janbot/epic-evaluation/tickets.toml`) selects several metrics — `retrieval_accuracy`/`retrieval_mrr` (data-level) and `citation_correctness`/`citation_precision`, `faithfulness`, `answer_coverage` (program/judge-level), registered in `src/janbot/eval/metrics.py`. The optimization gate in `gate-rule.md` gates on two of them (`citation_correctness`, `faithfulness`) with a symmetric floor, and its Goodhart guard forbids buying one with the other. The owner has settled *why* these metrics and not others.
- **Decision:** metrics are chosen **a priori from a failure taxonomy** — each metric answers a distinct question about a distinct failure mode: retrieval miss (`retrieval_*`), attribution error (`citation_*`), grounding/hallucination (`faithfulness`), non-answer (`answer_coverage`). The orthogonality that matters is **orthogonal constructs**, not empirically uncorrelated numbers. The same metrics are nevertheless **coupled under optimization** through a shared resource — the program's behavior, prompt budget, or model capacity — so a change that raises one can lower the other (emitting more citations vs. staying faithful). That coupling is the *precondition* for the gate's symmetric floor in `gate-rule.md`: without it the Goodhart guard would be vacuous, and the gate rule exists *because* the metrics are not independent in optimization. **Correlation is not a selection criterion** — it is only a later *diagnostic* for redundancy (false orthogonality), usable once the val set is powered (the "breadth gates optimization" of `gate-rule.md`, ≈100 val items to detect a ~5% effect); at the current val n=15 it is unmeasurable. Construct orthogonality is therefore a **pre-registered hypothesis, verified later — never derived from data**. If a metric is later found redundant, **remove it from the gate** (multiplicity cost — `gate-rule.md` already limits the gate to two metrics) while keeping it for **diagnosis**.
- **Reasons:** a metric chosen because it correlates with another at n=15 would be chosen on noise; a construct chosen because it names a distinct failure mode is defensible before any data exists. Metrics coupled under optimization are exactly the ones the Goodhart guard must police.
- **Consequences:** 🟢 metric choice is legible from the failure taxonomy, not from a post-hoc coefficient; 🟢 construct orthogonality is pre-registered and falsifiable once val is powered. 🟡 false orthogonality cannot be detected at n=15, so a redundant metric may survive until the val set grows.
- **Fixed:** the gate stays small (two metrics, per `gate-rule.md`); metric choice is a **spec-level decision**, not a data-driven one.
