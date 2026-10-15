# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Configuration module `janbot.config`: stdlib-only `JANBOT_*` environment loading (model mode, locked snapshot, corpus and index paths) with documented defaults and fail-fast mode validation. Adds `JANBOT_PROJECT_ROOT`, resolves corpus/index paths to absolute, CWD-independent paths under the project root (`~`-expanded), normalizes the model mode, and treats blank/whitespace values as unset.
- CI workflow (GitHub Actions): installs uv, syncs locked dependencies, and runs `pytest` on every push and pull request.
- Milestone 1, epics 2–4: org-mode ingestion with fail-closed scope, the DSPy answer + citation pipeline via `/chat`, and the end-to-end test suite (planned, not yet built).
- Eval `public_references` metric: a corpus-derived, generated allow-list of valid public URLs (`eval/public_urls.yaml`) verified against every answer — an off-list URL fails as unverifiable and an expected-but-missing URL fails as incomplete, with each failing item/URL flagged in the run output.
- Eval `retrieval_accuracy` metric: the pipeline exposes the corpus-relative sources it retrieved (`ChatProgram.last_retrieved_sources`), and each golden item passes when its expected sources are a subset of the retrieved set — a retrieved-but-missed source is flagged per item as a `retrieval:` CLI line.
- Eval `citation_correctness` metric: each golden item passes when its expected sources are a subset of the sources its answer cites (containment, never exact-set equality), with each miss flagged per item as a `citation:` CLI line; a separate informational `citation_precision` metric records the expected share of the cited sources, so a retrieved-but-unexpected citation lowers precision without ever failing correctness.
- Eval `faithfulness` metric via an LLM-as-a-judge: a config-driven judge model (`JANBOT_JUDGE_MODEL`, default the locked snapshot, routed through OpenRouter at `temperature=0`) scores each answer against the golden expected answer and returns a `faithful`/`hallucinated` verdict; the runner runs the injectable judge per item and records the verdict, a failed judge call leaves that item unjudged and flagged as a `judge:` CLI line without aborting the run, and the `faithfulness` metric aggregates the verdicts.
- BootstrapFewShot stage (`janbot.eval.optimize`): compiles the `/chat` program over the golden dataset's **train** split against a multi-objective objective — the answer cites its sources **and** the LLM-as-a-judge finds it faithful (`w_c = w_f = 0.5`) — and persists the compiled program as a DSPy JSON state file; `python -m janbot.eval.optimize` compiles, saves and logs it as an MLflow artifact with the compile config, hyperparameters, and the per-item `(cited_ok, faithful)` pairs. Adds `JANBOT_PROGRAM_PATH`, which pins a compiled program so production and the eval load it without recompiling (a set-but-missing path fails fast), and the eval marks such runs with a `program` parameter (`baseline` or `fewshot:<sha>`) so compiled and baseline runs compare side by side.
- Golden-dataset train/val split and val gate: each item carries a `split` (`train`/`val`); the compile CLI is train-only and the eval CLI takes `--split {all,train,val}`; a re-measured val baseline is the gate reference, and the optimization gate is pre-registered in `gate-rule.md` before any stage is judged.
- Eval run records: every run pins the config that produced it (model mode, snapshot, temperature, seed, top-k, judge model, `program`), the dataset `sha256`, and the split, and records each metric's population as its denominator (`<metric>__n`); the metric registry declares each metric's polarity (`higher_is_better`), so runs are comparable and a refusal is never scored as an uncited or unfaithful answer.
- Eval `retrieval_mrr` metric: over the same claim-making items as `retrieval_accuracy`, each golden item scores `1 / rank` of the first expected source in the retrieved list (0.0 when none is retrieved), so a source at rank 1 and one at rank 4 are distinguished where the binary `retrieval_accuracy` cannot.
- Hybrid retrieval mode: `JANBOT_RETRIEVAL_MODE` (`dense` default / `hybrid`, unknown values fail fast) adds an opt-in deterministic in-module BM25 lexical ranking over the scope-filtered candidate chunks, fused with the dense ranking by reciprocal-rank fusion inside `VectorStore.query`; the return shape, fail-closed scope filtering and `k` truncation are unchanged, and the shipped default stays `dense`.

### Documentation

- `README.md`: a **Configuration** section documenting the `JANBOT_*` variables, and updated status and package-layout sections.
- `ARCHITECTURE.md`: a cross-cutting **Configuration** subsection; added GitHub issue and PR templates.

## [0.1.0] - 2026-10-05

### Added

- Project scaffold: `uv`-managed Python project with the `src/janbot` layout (`api`, `pipeline`, `ingest`, `store`, `llm`) and pinned Milestone 1 dependencies.
- FastAPI application with a `GET /health` endpoint returning `{"status": "ok"}`.
- pytest + httpx smoke tests covering package import, pinned dependency versions, and the health endpoint.
- Specification and planning artifacts under `_bmad-output/`: the capability spec, the architecture spine (ports-and-adapters) with decision records, and the Milestone 1 ticket tree.
- `README.md` and the MIT `LICENSE`.
