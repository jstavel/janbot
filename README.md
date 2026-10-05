# JanBot

An autonomous AI career assistant that answers recruiter questions accurately and contextually from personal org-mode documentation — built spec-first, verified by tests from day one.

JanBot parses an org-mode corpus into semantically intact units, indexes them, and exposes a single `POST /chat` endpoint that returns a grounded answer with citations. Private notes are provably never indexed: the ingestion boundary is fail-closed over an explicit public folder.

## Status

Work in progress, built with the [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD). The contract for every capability, constraint and decision lives in `_bmad-output/` — the spec is the source of truth, not the code.

- **Milestone 1** — DSPy core + FastAPI MVP (in progress; project scaffold and configuration landed)
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

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```sh
uv sync
uv run pytest -q
uv run uvicorn janbot.api.main:app --reload
```

Then open `http://127.0.0.1:8000/health` — you should see `{"status":"ok"}`.

## Configuration

JanBot is configured entirely through environment variables prefixed `JANBOT_`, loaded by [`janbot.config`](src/janbot/config.py). Every value has a documented default, so the service runs with none set.

| Variable | Default | Meaning |
| --- | --- | --- |
| `JANBOT_MODEL_MODE` | `eval` | `eval` uses the locked deterministic snapshot (CI/evaluation); `production` uses `openrouter/auto`. An unknown value fails fast. |
| `JANBOT_MODEL_SNAPSHOT` | `openai/gpt-4o-mini-2024-07-18` | The locked model used in `eval` mode. |
| `JANBOT_CORPUS_PATH` | `public_profile_org` | The only corpus the ingestion pipeline will index (fail-closed). |
| `JANBOT_INDEX_PATH` | `chroma_db` | Where the vector index is written. |
| `JANBOT_PROJECT_ROOT` | the repository root | Base for relative `JANBOT_CORPUS_PATH`/`JANBOT_INDEX_PATH`; override for packaged deployments or tests. |

Path values are `~`-expanded and resolved to absolute paths under the project root, so they do not depend on the process working directory. A blank or whitespace-only value for any variable counts as unset and takes its documented default.

```sh
JANBOT_MODEL_MODE=production uv run uvicorn janbot.api.main:app
```

No secrets are read from the environment here; the OpenRouter key is a separate, later concern.

## Development

```sh
uv run pytest -q          # run the test suite
uv sync                   # rebuild the environment (pins are locked in uv.lock)
```

The package layout mirrors the architecture:

```text
src/janbot/
  config.py     # env-driven settings (JANBOT_*), fail-fast validation
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
