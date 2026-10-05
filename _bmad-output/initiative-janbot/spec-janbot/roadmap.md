# JanBot — Roadmap & Deliverables

Companion to `spec-janbot.md`. Milestones and clean outputs. Reframes ADR-002 (DSPy replaces LlamaIndex); the testing layer stays untouched across milestones.

## Milestone 1 — DSPy core + FastAPI MVP (day 1, no TS)

- Python environment (uv/venv) and DSPy pipeline over org-mode files.
- **Org-mode AST parsing (`orgparse`)** into org subtrees; chunking respects heading hierarchy, PROPERTIES drawers, LOGBOOK and tags.
- **Scope filter:** index only `public_profile_org/` (fail-closed). Private notes never enter ChromaDB.
- **DSPy program** (`dspy.Module`) with signature *query → answer + source citation*; output signature as Pydantic `ChatResponse`.
- **Retrieval:** `dspy.Retrieve` over ChromaDB (`all-MiniLM-L6-v2` embedding).
- **Baseline:** manual prompt; compilation deferred to Milestone 2.
- **FastAPI endpoint** `/chat` with Pydantic `response_model`.
- **Testing:** `pytest` + `httpx`; TS harness deferred to Milestone 1.5.

## Milestone 1.5 — TypeScript test harness (after pipeline stabilization)

- Split the `reactive-testing` framework into core and model packages.
- Define `janbot-model` with Zod schemas for the `/chat` endpoint.
- Codegen from the FastAPI OpenAPI spec (`openapi-zod-client`) → Zod from Pydantic, zero drift, single source of truth.
- Extend CI/CD with TypeScript regression tests (vitest).
- Standalone milestone — does not block Milestone 2.

## Milestone 2 — AI evaluation + staged optimization

- **Golden Dataset** — recruiter questions with expected answers and sources (ground truth for DSPy optimizers).
- Evaluation metrics: retrieval accuracy, citation correctness, hallucination detection (LLM-as-a-judge).
- **Cost-staged optimization** — each step only if the previous shows a need:
  1. manual prompt (~$0.10) →
  2. `BootstrapFewShot` (~$0) →
  3. `MIPROv2` ($6–15, one-off, amortized over repeated use).
- **MLFlow Tracking** — experiment tracking and iteration records (introduced here, not earlier).
- *Optional:* validate SuperOptiX in practice only after the DSPy pipeline stabilizes (never a core dependency).

## Milestone 3 — Clojure evolution & orchestration

- Design and implement the Clojure layer (Ring/Reitit), move request orchestration there, and verify backward compatibility of the test harness.
- Independent of the Python AI stack choice; ADR-003 applies unchanged.

## Deliverables

- **Milestone 1:** working FastAPI service in Python with a DSPy RAG pipeline over local data (including the compiled/optimized program).
- **Milestone 1.5:** TypeScript test harness (`reactive-testing` models, Zod schemas) with a CI/CD pipeline.
- **Milestone 2:** AI evaluation + Golden Dataset with MLFlow tracking.
- **Milestone 3:** evolutionary Clojure orchestrator for future event-driven management.
- **Overall:** a finished portfolio project showing a top-tier intersection of AI engineering, Python, TypeScript and functional programming.
