# JanBot

An autonomous AI career assistant that answers recruiter questions accurately and contextually from personal org-mode documentation — built spec-first, verified by tests from day one.

JanBot parses an org-mode corpus into semantically intact units, indexes them, and exposes a single `POST /chat` endpoint that returns a grounded answer with citations. Private notes are provably never indexed: the ingestion boundary is fail-closed over an explicit public folder.

> **Operating it:** [`RUNBOOK.md`](RUNBOOK.md) is the single source for *how* — local run, tests, index rebuild, answer-cache regeneration, deploy, the post-deploy live check and rollback. The stack procedure is [`terraform/RUNBOOK.md`](terraform/RUNBOOK.md). Which decisions bind is [`DECISIONS.md`](DECISIONS.md); what and why stay in `_bmad-output/`.

## Status

Work in progress, built with the [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD). The contract for every capability, constraint and decision lives in `_bmad-output/` — the spec is the source of truth, not the code.

- **Milestone 1** — DSPy core + FastAPI MVP (in progress; project scaffold and configuration landed)
- **Milestone 2** — AI evaluation, golden dataset, staged prompt optimization
- **Milestone 1.5** — thin TypeScript harness (Zod schemas via OpenAPI codegen, vitest; sequenced after Milestone 2)
- **Milestone 3** — Clojure orchestrator (Ring/Reitit)

## Architecture

Ports-and-adapters: every caller reaches JanBot only through the `POST /chat` JSON contract; retrieval, embeddings and the LLM live inside an isolated Python core.

| Layer | Technology |
| --- | --- |
| API | FastAPI, Pydantic (`ChatResponse`, `Citation` as the single contract source) |
| Pipeline | DSPy program: retrieve → answer + cite |
| Store | ChromaDB + `all-MiniLM-L6-v2` embeddings; retrieval scoped to `JANBOT_CORPUS_PATH` at the store boundary |
| Ingestion | `orgparse` — one chunk per org subtree (headings, PROPERTIES, LOGBOOK, tags, parent breadcrumbs) plus one file-root chunk per document (drawer with `:SYNOPSIS:` + text above the first heading) |
| LLM | OpenRouter — locked deterministic snapshot for CI/eval, `openrouter/auto` for production |
| Tests | pytest + httpx (Milestone 1); thin TypeScript/Zod contract harness (Milestone 1.5) |

Key invariants: fail-closed scope filter (only `public_profile_org/` is indexed) and scoped retrieval (only chunks located within `JANBOT_CORPUS_PATH` can be retrieved, so an out-of-corpus chunk never reaches the prompt or a citation), org subtree chunking with a retrievable file-root chunk (no naive text splitters), Pydantic as the single source of truth for the API contract, and a test layer that is never modified to accommodate a change in the AI core.

`public_profile_org/` is JanBot's source of truth, itself an extract of the wider personal corpus SSOT (`~/org/corpus/views/work-profile/index.org`); it is updated only by re-extraction, never edited in place. It carries two document kinds: `.org` files are evidence and are indexed; `.md` files are meta documents, kept for readers and never indexed.

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

JanBot is configured through environment variables loaded by [`janbot.config`](src/janbot/config.py): everything prefixed `JANBOT_`, plus one plain operator variable, `OPENROUTER_API_KEY`. Every `JANBOT_` value has a documented default (for `JANBOT_PROGRAM_PATH` the default is unset — no compiled program), so the service runs with none set.

| Variable | Default | Meaning |
| --- | --- | --- |
| `JANBOT_MODEL_MODE` | `eval` | `eval` uses the locked deterministic snapshot (CI/evaluation); `production` uses `openrouter/auto`. An unknown value fails fast. |
| `JANBOT_MODEL_SNAPSHOT` | `openai/gpt-4o-mini-2024-07-18` | The locked model used in `eval` mode. |
| `JANBOT_JUDGE_MODEL` | the locked snapshot | The LLM-as-a-judge model used by the eval to score answer faithfulness (routed through OpenRouter at `temperature=0`). Defaults to `JANBOT_MODEL_SNAPSHOT`; a stronger judge is a change here, not code. |
| `JANBOT_TEMPERATURE` | `0.0` | LM sampling temperature passed to the model in every mode. A value that is not a finite number fails fast. |
| `JANBOT_SEED` | `0` | Sampling seed pinning determinism in `eval` mode only. `production` (`openrouter/auto`) is seed-free. A value that is not an integer fails fast. |
| `JANBOT_TOP_K` | `4` | Retrieval top-k: how many corpus chunks ground an answer. An invalid or non-positive value fails fast. |
| `JANBOT_RETRIEVAL_MODE` | `hybrid` | Retrieval ranking: `hybrid` (the shipped default — dense cosine similarity fused with a deterministic BM25 lexical ranking by reciprocal-rank fusion; adopted on the breadth gate's ACCEPT, citation_correctness +9 items) or `dense` (embedder cosine similarity alone). An unknown value fails fast. |
| `JANBOT_RETRIEVAL_WINDOW` | `chunks` | Retention window over the ranking: `chunks` (the shipped default — the top-k ranked chunks) or `sources` (up to k distinct sources, each represented by its best-ranked chunk). Orthogonal to `JANBOT_RETRIEVAL_MODE`. An unknown value fails fast. |
| `JANBOT_RELEVANCE_THRESHOLD` | `0.26` | Low-relevance decline gate: when non-zero and the **two best** retrieved chunks' cosine similarities both fall below it, `/chat` declines with the `insufficient` reply before calling the model (a deterministic function of the embeddings; the second-best guard keeps a lexical-winner top chunk from falsely declining an in-corpus question). The default `0.26` is the measured value that raises `refusal_pass_rate` with no false declines; `0.0` disables the gate. A value that is not a finite, non-negative number fails fast. |
| `JANBOT_OUTPUT_GUARD` | `on` | The deterministic output guard (ADR-010): `on` drops fabricated citation labels and ungrounded over-claim clauses, or declines when no grounded answer remains; `off` isolates the lever for measurement. It never calls a model. An unknown value fails fast. |
| `JANBOT_CORPUS_PATH` | `public_profile_org` | The corpus root: the only tree the ingestion pipeline will index (fail-closed) and the scope retrieval is bounded to at the store. |
| `JANBOT_INDEX_PATH` | `chroma_db` | Where the vector index is written. |
| `JANBOT_PROGRAM_PATH` | unset | Path to a compiled DSPy program (the `BootstrapFewShot` output). When set, the app loads it instead of the freshly built program; the eval labels such runs `fewshot:<sha>` rather than `baseline`. A set path that does not name a file fails fast. |
| `JANBOT_PROJECT_ROOT` | the repository root | Base for relative `JANBOT_CORPUS_PATH`/`JANBOT_INDEX_PATH`; override for packaged deployments or tests. |
| `JANBOT_CORS_ORIGINS` | unset | Exact origins, comma-separated, allowed to call `POST /chat` from a browser (CORS preflights are answered at the middleware edge; POST-only, no credentials header). Unset/blank = no CORS middleware and today's behavior. The deployed stack sets the GitHub Pages origin `https://jstavel.github.io`; no other origin is allowed. |
| `OPENROUTER_API_KEY` | — | The OpenRouter key, read once at startup by the app (never stored in config). Required in `production` mode — a missing key fails fast at boot — and optional in `eval` mode, where it also authenticates the LLM-as-a-judge (a keyless eval leaves every item unjudged). |

Path values are `~`-expanded and resolved to absolute paths under the project root, so they do not depend on the process working directory. A blank or whitespace-only value for any variable counts as unset and takes its documented default. At startup the app verifies that every indexed chunk which records a source lies within `JANBOT_CORPUS_PATH` and fails fast otherwise, so an index built from a different corpus root cannot be served silently.

```sh
JANBOT_MODEL_MODE=production OPENROUTER_API_KEY=... uv run uvicorn janbot.api.main:app
```

Model mode is configuration only: switching `eval` ↔ `production` is an environment change, with no code change. In `eval` mode the locked snapshot is paired with a fixed seed (`JANBOT_SEED`, default `0`) and the documented default `temperature=0`; both remain configuration-owned, so a non-zero `JANBOT_TEMPERATURE` is honored rather than overridden. `production` uses `openrouter/auto`, unprefixed by a seed, and stays flexible.

## Chat

With the corpus indexed and a running server in `production` mode:

```sh
uv run python -m janbot.ingest   # index public_profile_org/ into chroma_db/
JANBOT_MODEL_MODE=production OPENROUTER_API_KEY=... uv run uvicorn janbot.api.main:app
```

```sh
curl -s -X POST localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question":"What search infrastructure have you built?"}'
```

The response is a `ChatResponse` carrying a `status` field. An answer grounded in the corpus is `{"status": "answered", "answer": "...", "citations": [{"source": "<corpus-root-relative path>"}, ...]}` — every citation is the path of a retrieved corpus chunk the answer is derived from, relative to `JANBOT_CORPUS_PATH` (e.g. `profile.org`): the model names the labeled context blocks it used, the program validates those claims against the retrieved chunks' metadata, and emits citations only from that metadata — one entry per distinct source. When JanBot cannot ground the question — nothing in the public corpus, a model answer that claims no sources, or (unless `JANBOT_RELEVANCE_THRESHOLD` is `0`) a best retrieved chunk below the relevance threshold — it declines gracefully with a `200` reply `{"status": "insufficient", "answer": "I answer only from my public profile — for anything beyond it, please contact Jan Stavel directly.", "citations": []}` rather than failing. The contract pins the shape: an `answered` reply must carry at least one citation and an `insufficient` reply must carry none; a **fabricated cited label** — one naming a source outside the retrieved set — is dropped by the deterministic output guard, and if no valid citation remains the reply declines; a citation outside the retrieved set is never emitted.

Errors use FastAPI's standard `{detail}` envelope: a missing, mistyped, or blank (whitespace-only) `question` is rejected with the default 422; retrieval is scoped to `JANBOT_CORPUS_PATH` at the store, so a chunk outside the corpus root or without a `source_path` is never retrieved and an index with no in-corpus grounding yields the `insufficient` reply above (not an error); a citation outside the retrieved set is dropped by the output guard (or the reply declines when none remain); and a model-response or unexpected processing failure is refused with 500 and a fixed (non-leaking) `{detail}` — every `/chat` error response, including the real-model path, carries the envelope.

## Evaluation

Milestone 2 measures the pipeline against a version-controlled golden dataset (`eval/golden_dataset.yaml`, with a per-item train/val split) and records every run in MLflow:

```sh
uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val
uv run python -m janbot.eval.optimize --dataset eval/golden_dataset.yaml --split train --out eval/compiled_fewshot.json
uv run python -m janbot.eval.public_urls
```

`python -m janbot.eval` scores each item and logs the metrics — `answer_coverage`, `public_references`, `retrieval_accuracy`, `retrieval_mrr`, `citation_correctness`, `citation_precision`, `faithfulness`, `refusal_pass_rate`, `spurious_refusal_rate` — each with its denominator (`<metric>__n`); `--split {all,train,val}` selects the split (the optimization gate runs `val`); `--answers` dumps each item's answer text for diagnosing judge verdicts. A program decline (an empty retrieval, a low-relevance gate, or an uncited answer) is a defined, contract-conforming outcome — the runner maps it to the API's `insufficient` `ChatResponse` rather than an error — so `refusal_pass_rate` (the share of out-of-corpus `should_refuse` items cleanly declined; higher is better) and `spurious_refusal_rate` (the share of in-corpus items falsely declined; higher is better **off**, polarity `higher_is_better=False`) score how the program declines, while a refusal item never dilutes the other metrics (they exclude `should_refuse` items). `python -m janbot.eval.optimize` compiles the `/chat` program over the train split against a multi-objective objective (the answer cites its sources **and** the judge finds it faithful) and persists it as a DSPy program pinned by `JANBOT_PROGRAM_PATH`. `python -m janbot.eval.public_urls` regenerates the public-reference allow-list (`eval/public_urls.yaml`), keyless.

`python -m janbot.eval` runs keyless — a keyless run leaves every item unjudged, so `faithfulness` stays `0`. `python -m janbot.eval.optimize` needs a judge for its faithfulness term, so it requires `OPENROUTER_API_KEY` (honoring `JANBOT_JUDGE_MODEL`) and fails fast without one.

The eval reads the full configuration surface — `JANBOT_MODEL_MODE`, `JANBOT_MODEL_SNAPSHOT`, `JANBOT_TEMPERATURE`, `JANBOT_SEED`, `JANBOT_TOP_K`, `JANBOT_CORPUS_PATH`, `JANBOT_INDEX_PATH`, `JANBOT_JUDGE_MODEL`, `JANBOT_PROGRAM_PATH`, `JANBOT_RETRIEVAL_MODE`, `JANBOT_RETRIEVAL_WINDOW`, `JANBOT_RELEVANCE_THRESHOLD`, `JANBOT_OUTPUT_GUARD` — and every run records the params that pin it: the model mode, snapshot, judge model, temperature, seed, top-k, retrieval mode, retrieval window, relevance threshold, output guard, and `program`, plus the dataset `sha256`, so runs are comparable. Runs go to the MLflow store at `MLFLOW_TRACKING_URI` (default `sqlite:///mlflow.db`, with artifacts under `mlruns/`); both are gitignored. The optimization gate is judged against a pre-registered rule in `_bmad-output/initiative-janbot/epic-evaluation/gate-rule.md`.

## Development

```sh
uv run pytest -q          # run the test suite
uv sync                   # rebuild the environment (pins are locked in uv.lock)
```

> **File descriptors:** the full suite runs green at the common default soft limit
> (`ulimit -n 1024`; 2026-10-22: **3354 passed, 0 failed**). An autouse fixture in
> [`tests/conftest.py`](tests/conftest.py) releases the chroma systems and mlflow engines
> each test creates, so the old `ulimit -n 16384` wrapper is retired. If the suite fails
> with `EMFILE` / SQLite `CANTOPEN`, a new resource leak was introduced — fix the leak,
> do not raise the limit.

The package layout mirrors the architecture:

```text
src/janbot/
  config.py     # env-driven settings (JANBOT_*), fail-fast validation
  api/          # FastAPI app, the /chat contract (the port)
  pipeline/     # DSPy program: retrieve -> answer + cite
  ingest/       # orgparse reader, subtree chunker, fail-closed scope filter
  store/        # ChromaDB client + embedding adapter
  llm/          # OpenRouter adapter + model-mode config
  eval/         # golden dataset, metrics, LLM-as-a-judge, MLflow runs, optimization
tests/          # endpoint tests through the HTTP port only
```

Planning artifacts live in `_bmad-output/`: `spec-janbot/` (the capability contract), `architecture-janbot/` (the architecture spine with decision records), and the ticket tree for Milestone 1.

### End-to-end tests

The suite in `tests/e2e/` proves the *shipped service answers through its HTTP port*: it starts `uv run uvicorn janbot.api.main:app` as a subprocess against a fixture index and posts to `POST /chat` over HTTP, importing no `janbot` internals. The fixture index is built at session setup by the ingestion CLI (in a subprocess), so it is never committed — a ChromaDB index bakes absolute `source_path` values and would only match the author's checkout. The real-model happy path needs a model key and is skipped cleanly without one, so a keyless run stays green.

The grounding boundary is proven at the port by `tests/e2e/test_grounding_e2e.py`: a crafted index holding an out-of-scope chunk makes the service exit at startup, and a sourceless-only index answers `/chat` with a `200` `insufficient` reply. Those indexes come from `tests/e2e/make_index.py`, a non-test helper run as a subprocess.

Grounding determinism at the locked snapshot is proven by `tests/e2e/test_determinism_e2e.py`: two **cache-cold** eval service runs (each a fresh process with its own `DSPY_CACHEDIR`, so its single `POST /chat` is a real generation, not a DSPy response-cache hit) are posted the same question once each, and the two `200` runs must ground the answer in the **same corpus sources**. (The provider does not guarantee byte-identical answer *text* at temperature 0, so the row pins grounding, not wording.)

CI (`.github/workflows/ci.yml`) runs the unit/in-process suite and the port-only `tests/e2e` suite as separate named steps, plus a `contract-negative` job that mutates `tests/fixtures/chat_response.json` and requires `tests/test_response_contract.py` to go red — proving the broken-`/chat`-contract check is not vacuous. The keyed rows (which skip in that keyless run) also run in `.github/workflows/e2e-keyed.yml` (weekly + `workflow_dispatch`), which skips cleanly when the `OPENROUTER_API_KEY` secret is unset.

Run the port-only happy path with a key (both the `eval` snapshot and `production` are served through OpenRouter; the service reads `OPENROUTER_API_KEY` and passes it to `dspy`/LiteLLM):

```sh
OPENROUTER_API_KEY=... uv run pytest tests/e2e -q
```

### Merging

Changes land through a pull request; `main` is not pushed to directly.

> **Rebase and merge re-creates commits.** GitHub's rebase merge rewrites every commit SHA
> even when a fast-forward would have been possible, and it **drops empty commits** (this repo
> records an index rebuild as an empty commit, because `chroma_db/` is gitignored).
>
> Consequence for documentation: **never pin the commit SHA of an unmerged branch.** Pin the
> run id and the `dataset_sha256` instead — that is what the reference registration does. If a
> commit SHA must be cited, cite it from `main` *after* the merge.

> **Round branches are single-theme.** A corpus/eval round branch carries only what belongs
> to that round. Documentation, agent-skill and configuration commits go to `main` through
> their own PR (a `docs/*` branch), never onto the round branch. Otherwise the round PR
> carries unrelated files, and as soon as `main` moves the round can no longer
> fast-forward — which forces a merge commit (acceptable) or a rebase that rewrites pinned
> SHAs (not acceptable). Measured 2026-10-25: an `org-keeping` skill commit landed on
> `corpus/10-23-cv-and-honesty` because that branch happened to be checked out.

## License

[MIT](LICENSE)
