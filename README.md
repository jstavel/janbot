# JanBot

An autonomous AI career assistant that answers recruiter questions accurately and contextually from personal org-mode documentation — built spec-first, verified by tests from day one.

JanBot parses an org-mode corpus into semantically intact units, indexes them, and exposes a single `POST /chat` endpoint that returns a grounded answer with citations. Private notes are provably never indexed: the ingestion boundary is fail-closed over an explicit public folder.

## Status

Work in progress, built with the [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD). The contract for every capability, constraint and decision lives in `_bmad-output/` — the spec is the source of truth, not the code.

- **Milestone 1** — DSPy core + FastAPI MVP (in progress; project scaffold landed)
- **Milestone 1.5** — TypeScript test harness (Zod schemas, codegen from OpenAPI)
- **Milestone 2** — AI evaluation, golden dataset, staged prompt optimization
- **Milestone 3** — Clojure orchestrator (Ring/Reitit)

## Architecture

Ports-and-adapters: every caller reaches JanBot only through the `POST /chat` JSON contract; retrieval, embeddings and the LLM live inside an isolated Python core.

| Layer | Technology |
| --- | --- |
| API | FastAPI, Pydantic (`ChatResponse`, `Citation` as the single contract source) |
| Pipeline | DSPy program: retrieve → answer + cite |
| Store | ChromaDB + `all-MiniLM-L6-v2` embeddings |
| Ingestion | `orgparse` — one chunk per org subtree (headings, PROPERTIES, LOGBOOK, tags, parent breadcrumbs) |
| LLM | OpenRouter — locked deterministic snapshot for CI/eval, `openrouter/auto` for production |
| Tests | pytest + httpx (Milestone 1); TypeScript/Zod harness (Milestone 1.5) |

Key invariants: fail-closed scope filter (only `public_profile_org/` is indexed), org subtree chunking (no naive text splitters), Pydantic as the single source of truth for the API contract, and a test layer that is never modified to accommodate a change in the AI core.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```sh
uv sync
uv run pytest -q
uv run uvicorn janbot.api.main:app --reload
```

Then open `http://127.0.0.1:8000/health` — you should see `{"status":"ok"}`.

## Development

```sh
uv run pytest -q          # run the test suite
uv sync                   # rebuild the environment (pins are locked in uv.lock)
```

The package layout mirrors the architecture:

```text
src/janbot/
  api/          # FastAPI app, the /chat contract (the port)
  pipeline/     # DSPy program: retrieve -> answer + cite
  ingest/       # orgparse reader, subtree chunker, fail-closed scope filter
  store/        # ChromaDB client + embedding adapter
  llm/          # OpenRouter adapter + model-mode config
tests/          # endpoint tests through the HTTP port only
```

Planning artifacts live in `_bmad-output/`: `spec-janbot/` (the capability contract), `architecture-janbot/` (the architecture spine with decision records), and the ticket tree for Milestone 1.

## License

[MIT](LICENSE)
