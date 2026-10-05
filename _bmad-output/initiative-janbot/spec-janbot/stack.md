# JanBot — Stack & Architecture

Companion to `spec-janbot.md`. Load-bearing technology and boundary decisions. Prose rationale lives in `decisions.md` (ADRs) and the source document.

## Phase 1 — AI Core & MVP Backend (Python)

- **Python** service. FastAPI as a thin HTTP wrapper over the DSPy program; `POST /chat`.
- **DSPy** is the core RAG pipeline: programmatic module composition, automatic prompt optimization (not hand-tuned prompts).
- **ChromaDB** is the vector store (embedding + retrieval) underneath DSPy. Embedding model: `all-MiniLM-L6-v2`.
- **Org-mode AST parsing:** `orgparse`. Chunk by org subtrees (heading + content + PROPERTIES + children) with parent-heading breadcrumbs, so naive text splitters do not break semantic units.
- **Retrieval:** `dspy.Retrieve` over ChromaDB.
- **Program definition:** `dspy.Module` with a *query → answer + source citation* signature; output signature as Pydantic models (`ChatResponse`, `Citation`) for a guaranteed JSON contract.
- **FastAPI** endpoint `POST /chat` with `response_model` (Pydantic) validating output at the API boundary.
- **LLM layer:** OpenRouter, two modes — (a) deterministic locked snapshot (e.g. `openai/gpt-4o-mini-2024-07-18`) for CI and evaluation; (b) `openrouter/auto` for production.
- **Security boundary:** fail-closed whitelist; only `public_profile_org/` is indexed. Anonymization and guardrails land only before real recruiter deployment.
- **Baseline:** start with a manual prompt; DSPy compilation is deferred to Milestone 2.

## Testing layers (phased)

- **Milestone 1:** `pytest` + `httpx` for immediate testing of the FastAPI endpoint. No TypeScript; focus on reaching a working result fast.
- **Milestone 1.5:** TypeScript test harness (`reactive-testing` models, Zod schemas) — only after the Python pipeline stabilizes.
- **CI/CD:** GitHub Actions for Python tests (Milestone 1); extended with Zod validation in Milestone 1.5.

## Phase 2 — Evolution (Clojure)

- Add a **Clojure orchestrator** (Ring/Reitit, deterministic data parsing) as the primary API gateway in front of the existing Python AI microservice.

## Separation of concerns

AI and vector search run in an isolated Python layer. Testing is strictly separated (TypeScript via API contracts and schemas). The Clojure orchestration layer is deliberately deferred so the AI core stabilizes first.
