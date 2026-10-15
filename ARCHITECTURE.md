# Architecture

## Overview

JanBot follows a **ports-and-adapters** (hexagonal) architecture. Every caller reaches JanBot only through the `POST /chat` JSON contract; retrieval, embeddings and the LLM live inside an isolated Python core.

```
┌──────────────┐     ┌────────────────────────────────────┐
│   Caller     │     │           JanBot Core               │
│ (HTTP/gRPC)  │────▶│  ┌────────┐  ┌────────┐  ┌─────┐  │
└──────────────┘     │  │ FastAPI │─▶│  DSPy  │─▶│ LLM │  │
                     │  │ /chat  │  │Program │  │     │  │
                     │  └────────┘  └───┬────┘  └─────┘  │
                     │                  │                 │
                     │           ┌──────▼──────┐          │
                     │           │   ChromaDB  │          │
                     │           │ (vektory)   │          │
                     │           └──────┬──────┘          │
                     │                  │                 │
                     │           ┌──────▼──────┐          │
                     │           │  orgparse   │          │
                     │           │ (ingestion) │          │
                     │           └─────────────┘          │
                     └────────────────────────────────────┘
```

## Key Design Decisions

### 1. Single JSON Contract

`POST /chat` with Pydantic `ChatRequest` / `ChatResponse` is the **single source of truth** for the API surface. Documentation, test validation (pytest + TypeScript/Zod), and client codegen all derive from these models.

### 2. DSPy over Manual Prompt Chains

DSPy replaces traditional manual prompt engineering with programmatic module composition and automated optimization (see [ADR-002](_bmad-output/initiative-janbot/spec-janbot/decisions.md)).

### 3. Org-mode AST-aware Ingestion

Chunking preserves semantic structure:

- One chunk per org subtree (heading + content + PROPERTIES + LOGBOOK + children), plus one file-root chunk per document carrying its PROPERTIES drawer (the approved `:SYNOPSIS:` among it) and the text above the first heading, so a document's own summary is retrievable
- Breadcrumb of parent headings preserved in metadata
- No naive text splitters that break semantic boundaries

### 4. Fail-Closed Security Boundary

Only files in `public_profile_org/` are indexed. The ingestion pipeline provably never touches private notes — the scope filter is a whitelist, not a blocklist.

`public_profile_org/` is **JanBot's source of truth**, itself an extract of the wider personal corpus SSOT (`~/org/corpus/views/work-profile/index.org`, 37 approved `REVIEWED`-stamped objects). Updates happen only by re-extracting from the corpus view; the files here are never edited in place. The upstream corpus origin (with harvest log and git-pinned sources) lives in `~/org/corpus/`.

### 5. Deterministic Model Routing

Two LLM modes (see [ADR-004](_bmad-output/initiative-janbot/spec-janbot/decisions.md)):

| Mode | Model | Use Case |
|------|-------|----------|
| Locked | `openai/gpt-4o-mini-2024-07-18` | CI, unit tests, evaluation |
| Flexible | `openrouter/auto` | Production |

## Layer Details

### Configuration (cross-cutting)

Settings are environment-driven (`JANBOT_*`, loaded by `janbot.config`) and never hard-coded: model mode, locked snapshot, corpus and index paths all resolve from a single `load_config()`. This is what keeps CI deterministic (locked snapshot at `temperature=0`) while production routes flexibly — no code branch selects a model by caller. An unknown `JANBOT_MODEL_MODE` fails fast at load time.

### API Layer (FastAPI)

- Thin wrapper — no business logic
- Pydantic models are the contract source
- `GET /health` — liveness probe
- `POST /chat` — main endpoint

### Pipeline Layer (DSPy)

- `retrieve → answer + cite` program
- Phased optimization: manual prompt → `BootstrapFewShot` → `MIPROv2`
- Tracked via MLFlow

### Store Layer (ChromaDB)

- Vector database for semantic search
- Embedding model: `all-MiniLM-L6-v2`
- Retrieval is scoped to the corpus root at the store boundary: only chunks located within `JANBOT_CORPUS_PATH` can be retrieved, so an out-of-corpus chunk never reaches the prompt

### Ingestion Layer (orgparse)

- Reads `.org` files
- Parses AST into chunks
- Excludes private files via whitelist

### LLM Layer (OpenRouter)

- Model locked for determinism in CI
- Flexible routing in production
- Token usage logged for cost analysis

### Eval Layer (janbot.eval)

- The golden dataset (`eval/golden_dataset.yaml`) is the yardstick — a per-item train/val split, version-controlled
- Metrics aggregate per-item outcomes, each declaring its own population and polarity; the runner records one MLflow run per eval with the config that produced it, the dataset `sha256`, the split, and each metric's denominator (`<metric>__n`)
- Faithfulness is scored by an LLM-as-a-judge (`JANBOT_JUDGE_MODEL`), routed through OpenRouter
- Cost-staged optimization: `BootstrapFewShot` (`python -m janbot.eval.optimize`) compiles against a multi-objective (cited **and** faithful) objective; `MIPROv2` is a latent, evidence-gated next stage, adopted only if the pre-registered `gate-rule.md` shows a decidable gain
- The harness runs without a model key: the CLI injects the `ChatProgram` built by `create_app` and tests inject a stub

## Testing Strategy

| Milestone | Layer | Tooling |
|-----------|-------|---------|
| M1 | API smoke + integration | `pytest` + `httpx` |
| M1.5 | Contract verification (thin harness) | TypeScript + Zod (OpenAPI codegen) + vitest |
| M2 | AI evaluation | Golden dataset + metrics |

## Future Evolution

- **Clojure orchestrator** (Ring/Reitit) as primary API gateway over the Python AI microservice
- **Multi-source ingestion** (Markdown, plaintext, PDF)
- **A/B testing** of prompt strategies via MLFlow
