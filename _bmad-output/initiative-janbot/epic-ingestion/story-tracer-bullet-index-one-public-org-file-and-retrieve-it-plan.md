---
title: 'Tracer bullet: index one public org file and retrieve it'
type: 'feature'
ticket: '2'
created: '2026-10-05'
status: done
baseline_revision: '2d1aa2d55cbd6e50dafa402045e196a6cf6f9765'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-janbot/epic-ingestion/epic-ingestion.md'
  - '_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** No ingestion or store layer exists. Before building them out, we need the thinnest end-to-end path proving the pieces connect: an org file becomes a semantically-intact chunk, it is embedded and stored in ChromaDB, and a query returns it with its source path.

**Approach:** Add a minimal `src/janbot/ingest/` (orgparse read → one chunk per top-level subtree with a parent-heading breadcrumb, and a fail-closed walk of the corpus root) and `src/janbot/store/` (a `VectorStore` over a persistent ChromaDB collection with an **injectable embedder seam**: production uses ChromaDB's default `all-MiniLM-L6-v2`, tests inject a deterministic stub). A tiny `python -m janbot.ingest <corpus> [--index ...]` CLI exercises the real path; the tracer test runs against a committed synthetic fixture.

## Boundaries & Constraints

**Always:** `orgparse` for reading org files; one chunk per org subtree carrying a `source_path` and a parent-heading `breadcrumb`; only files under the configured corpus root are indexed (fail-closed, minimal here — entry 2.4 owns the full filter); embeddings are injected through a seam so tests never load the real model; ChromaDB persistent client under `config.index_path`; stdlib + the already-pinned deps only.

**Never:** no DSPy, no `/chat` (epic-rag-chat); no full heading/property/logbook semantics (entry 2.3); no idempotency guarantees (entry 2.5); no real embedding model in tests; no new dependency; do not commit the real `~/org` corpus.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Index one file | a fixture `.org` under the corpus root + stub embedder | one chunk per top-level subtree stored; chunk carries `source_path` and `breadcrumb` | No error |
| Retrieve | query text matching a subtree heading | the stored chunk is returned with its `source_path` | No error |
| Empty corpus dir | corpus root with no `.org` files | zero chunks stored, no error | No error |
| Non-org files | a `.txt` file under the corpus root | ignored (only `.org` indexed) | No error |

</frozen-after-approval>

## Code Map

Greenfield for this epic. Existing: `src/janbot/config.py` (`Config.corpus_path`/`index_path` are absolute `Path`s; `load_config`); `src/janbot/{ingest,store,llm,pipeline}/__init__.py` empty; deps pinned (`orgparse==0.5.20260926`, `chromadb==1.5.9`). orgparse API: `orgparse.load(path)` → root; `root.children` → top-level nodes; node `.heading`, `.body`, `.children`, `.get_property(k)`, `.tags`. Note: importing `dspy` before `chromadb` in one process triggers a lazy-numpy bug — import `numpy` first if both are loaded (seen in the 2.1 smoke test).

- `src/janbot/ingest/org.py` -- NEW: `Chunk` dataclass (`id`, `text`, `source_path`, `breadcrumb`) + `read_org_file(path) -> list[Chunk]` (one chunk per top-level subtree; text = heading + body + children text; breadcrumb = ancestor headings)
- `src/janbot/ingest/scope.py` -- NEW: `iter_org_files(root) -> Iterator[Path]` (walk, `.org` only) + `within(root, path) -> bool` (minimal fail-closed guard; full policy in 2.4)
- `src/janbot/ingest/__main__.py` -- NEW: `python -m janbot.ingest <corpus> [--index PATH]` → indexes and prints the chunk count
- `src/janbot/ingest/__init__.py` -- export `read_org_file`, `Chunk`, `iter_org_files`, `index_corpus`
- `src/janbot/store/chroma.py` -- NEW: `Embedder` type (`Callable[[list[str]], list[list[float]]]`), `default_embedder()` (ChromaDB default function, returns lists), `VectorStore(index_path, embedder)` with `.upsert(chunks)` and `.query(text, k=3) -> list[dict]` (ids, documents, metadatas with `source_path`/`breadcrumb`)
- `src/janbot/store/__init__.py` -- export `VectorStore`, `default_embedder`
- `tests/fixtures/public_profile_org/example.org` -- NEW: a small nested org file (heading, body, a nested child, a tag)
- `tests/test_ingest_tracer.py` -- NEW: the matrix rows over the fixture + a temp index, with a deterministic stub embedder

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/ingest/org.py` -- implement `Chunk` + `read_org_file` (top-level subtrees, breadcrumb, source path) -- covers CAP-5 (partial; 2.3 completes)
- [ ] `src/janbot/ingest/scope.py` -- `iter_org_files` (`.org` only) + minimal `within` guard -- covers CAP-4 (partial; 2.4 completes)
- [ ] `src/janbot/store/chroma.py` -- `Embedder` seam, `default_embedder`, `VectorStore` upsert/query passing explicit embeddings -- covers CAP-4/CAP-5
- [ ] `src/janbot/ingest/__main__.py` + `__init__.py` exports -- the CLI and the public surface -- integration
- [ ] `tests/fixtures/public_profile_org/example.org` + `tests/test_ingest_tracer.py` -- the four matrix rows -- verification

**Acceptance Criteria:**
- Given a fixture `.org` under the corpus root and a stub embedder, when `index_corpus` runs, then chunks are stored and a subsequent `query` returns a chunk whose `source_path` is the fixture file.
- Given a corpus dir with no `.org` files, when indexed, then zero chunks are stored and no error is raised.
- Given a `.txt` file under the corpus root, when indexed, then it is ignored.

## Implementation Notes

## Plan Change Log

## Review Triage Log

Verdict counts: high 3, medium 1, low 1, info 1.

- high | patch | `src/janbot/store/chroma.py` imports `janbot.ingest.org.Chunk` while `ingest/__init__.py` imports `store` → `import janbot.store` fails (partial-init circular import; confirmed). Fix: remove the store→ingest dependency (structural `ChunkLike` protocol / duck-typing).
- high | patch | `src/janbot/ingest/__main__.py` takes an arbitrary corpus root and never uses the configured public root, so `python -m janbot.ingest ~/org` would index private notes (violates AD-3). Fix: the CLI indexes only `config.corpus_path`.
- high | deferred | `src/janbot/ingest/scope.py` `within()` resolves symlinks, so symlinked public files (the epic's chosen layout) are refused — this is the acknowledged 2.4 scope-policy item, now confirmed; recorded in `deferred-work.md`. Note: it means the 2.2 real-data hitl step cannot use symlinks yet.
- medium | patch | `src/janbot/ingest/org.py` duplicate top-level headings yield identical chunk ids → Chroma `DuplicateIDError` drops the whole file. Fix: make the id unique per subtree (subtree ordinal).
- low | patch | `src/janbot/ingest/org.py` `source_path`/id are CWD-relative (config resolves paths absolute). Fix: resolve the source path before building ids/metadata.
- info | — | no `AGENTS.md`/`CLAUDE.md` in the repo; rules taken from ARCHITECTURE.md/README/plan. Not a defect.

## Design Notes

Embedder seam: `VectorStore` computes embeddings itself and passes explicit `embeddings=` to Chroma `upsert`/`query`, so tests inject a deterministic stub without Chroma's embedding-function validation and without loading the real model; production passes `default_embedder()`. Chunk `id` is a stable string (`<source_path>::<breadcrumb>`) so 2.5 can make upserts idempotent. The tracer chunker is deliberately shallow (top-level subtrees); the full subtree semantics and the symlink-aware scope policy land in 2.3/2.4.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass
- `uv run python -c "import janbot.store"` -- expected: succeeds standalone (no circular import)
- `JANBOT_CORPUS_PATH=tests/fixtures/public_profile_org uv run python -m janbot.ingest --index /tmp/janbot_tracer_index` -- expected: prints a positive chunk count (uses the real default embedder; first run may download the ONNX model)
