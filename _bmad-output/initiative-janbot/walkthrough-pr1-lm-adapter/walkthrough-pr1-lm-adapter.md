# Review: PR #1 — epic-rag-chat kickoff (LM adapter, story 3.1)

Target: [PR #1](https://github.com/jstavel/janbot/pull/1) — head `story-3.1-lm-adapter` → base `main`, 6 commits; this walkthrough weights story 3.1 (commit `21458c3`) with the earlier 5 commits as periphery.

## Block 1 — Intent

- [ ] in progress — currently here

> **Problem:** JanBot's LLM layer does not exist: `src/janbot/llm/` is an empty package, and `Config` carries model mode + snapshot but no LM adapter and no temperature/top-k routing knobs — so the `/chat` DSPy pipeline (story 3.2) has nothing to build its LM on.
>
> **Approach:** Add `janbot.llm` with pure-config model-mode routing (`resolve_model`) and a `build_lm` factory behind an injectable LM-construction seam; extend `Config` with `temperature` (default `0.0`) and `top_k` (default `3`) read from new `JANBOT_TEMPERATURE` / `JANBOT_TOP_K` vars.

This Intent is pasted verbatim from the frozen block of the [story-3.1 plan](../epic-rag-chat/story-lm-adapter-model-mode-routing-plan.md#L20).

The other 5 commits form the kickoff queue that PR #1 publishes ahead of story 3.1: the [public corpus extract](../../../public_profile_org/), two provenance-doc clarifications, an ingestion idempotence test, and ticket bookkeeping that closes [epic-ingestion](../epic-ingestion/epic-ingestion.md) and incepts [epic-rag-chat](../epic-rag-chat/epic-rag-chat.md). They are reviewed only as periphery in this walkthrough; story 3.1 carries the weight.

## Block 2 — Broad strokes

- [ ] unvisited

The four entry points a reviewer opens first:

- [src/janbot/llm/__init__.py](../../../src/janbot/llm/__init__.py) — the new adapter: `resolve_model` + `build_lm`.
- [src/janbot/config.py](../../../src/janbot/config.py) — the two new config knobs (`JANBOT_TEMPERATURE`, `JANBOT_TOP_K`).
- [tests/test_llm.py](../../../tests/test_llm.py) — routing/kwargs contract tests.
- [README.md](../../../README.md) — the documented contract rows for both knobs.

By design, story 3.1 touches none of `store/`, `ingest/`, or `api/` — wiring `top_k` into retrieval and the `/chat` route is story 3.2.

## Block 3 — Slice: model-mode routing

- [ ] unvisited

`resolve_model` routes purely by the resolved `Config` — `production` returns the `openrouter/auto` constant, `eval` returns `config.model_snapshot`, and an impossible mode raises a defensive `ValueError` (unreachable through `load_config`, which validates, but reachable if a `Config` is constructed directly). Switching modes is an environment change only, never code. The mode constants live in `config.py` and `llm` imports them, so there is one vocabulary.

- [src/janbot/llm/__init__.py:36](../../../src/janbot/llm/__init__.py#L36) — `resolve_model`; the defensive raise at [src/janbot/llm/__init__.py:42](../../../src/janbot/llm/__init__.py#L42).
- [src/janbot/llm/__init__.py:30](../../../src/janbot/llm/__init__.py#L30) — `OPENROUTER_MODEL` / `OPENROUTER_API_BASE` constants.
- [src/janbot/config.py:39](../../../src/janbot/config.py#L39) — `MODEL_MODE_EVAL` / `MODEL_MODE_PRODUCTION` / `MODEL_MODES` (the constants `llm` imports).

## Block 4 — Slice: build_lm and the injectable seam

- [ ] unvisited

`build_lm` assembles constructor kwargs from pure configuration — always `model` (via `resolve_model`) and `temperature` — and, only in `production`, the OpenRouter `api_base` plus a caller-supplied `api_key`; a `production` call without a key fails fast with a `ValueError` naming the mode and the parameter. In `eval` mode any supplied `api_key` is deliberately ignored, so eval kwargs stay secret-free. The seam is `lm_factory: Callable[..., Any] = dspy.LM`, and because tests inject a stub factory that just captures kwargs, no test ever constructs a real `dspy.LM` or touches the network.

- [src/janbot/llm/__init__.py:45](../../../src/janbot/llm/__init__.py#L45) — `build_lm` signature with the keyword-only seam; the `LMFactory` alias at [src/janbot/llm/__init__.py:33](../../../src/janbot/llm/__init__.py#L33).
- [src/janbot/llm/__init__.py:57](../../../src/janbot/llm/__init__.py#L57) — kwargs assembly; the fail-fast `ValueError` at [src/janbot/llm/__init__.py:63](../../../src/janbot/llm/__init__.py#L63).
- [tests/test_llm.py:119](../../../tests/test_llm.py#L119) — the `__kwdefaults__` identity check proving the default factory is `dspy.LM` without instantiating it (the seam is keyword-only, so the default lives in `__kwdefaults__`).

## Block 5 — Slice: config knobs

- [ ] unvisited

`load_config` parses the two new knobs after the shared `_clean` trim: a blank or whitespace-only value counts as unset and takes the default (`0.0` / `3`); an unparseable value raises a `ValueError` that names the offending variable. `JANBOT_TOP_K` must additionally be an integer ≥ 1. `JANBOT_TEMPERATURE` deliberately has no range check — it validates parse-only (`nan`/negative would pass), a strictness decision recorded in the plan's implementation notes.

- [src/janbot/config.py:48](../../../src/janbot/config.py#L48) — the `JANBOT_TEMPERATURE` / `JANBOT_TOP_K` env consts; defaults at [src/janbot/config.py:55](../../../src/janbot/config.py#L55).
- [src/janbot/config.py:109](../../../src/janbot/config.py#L109) — temperature parse + `ValueError`; the top-k parse and the `≥ 1` range check at [src/janbot/config.py:120](../../../src/janbot/config.py#L120).
- [story-3.1 plan, implementation notes](../epic-rag-chat/story-lm-adapter-model-mode-routing-plan.md#L87) — the recorded no-range-check decision for temperature and the widened top-k guard.

## Block 6 — Slice: tests

- [ ] unvisited

The two test modules assert literal contracts: `test_llm.py` covers routing by configuration alone (eval → snapshot, production → `openrouter/auto`), a `StubLMFactory` that captures constructor kwargs for both modes, a production-without-key failure test asserting the factory was never called, and a pin that `eval` ignores a supplied `api_key`. `test_config.py` extends its autouse env-clearing fixture with the two new variable names and adds the same literal style of default, override, blank→default, and invalid→`ValueError` tests for both knobs.

- [tests/test_llm.py:20](../../../tests/test_llm.py#L20) — `StubLMFactory` kwarg capture; routing tests at [tests/test_llm.py:47](../../../tests/test_llm.py#L47).
- [tests/test_llm.py:67](../../../tests/test_llm.py#L67) — eval kwargs (`temperature` honored, no `api_base`/`api_key`), including the eval-ignores-`api_key` pin at [tests/test_llm.py:78](../../../tests/test_llm.py#L78).
- [tests/test_llm.py:87](../../../tests/test_llm.py#L87) — production kwargs (`api_base` + `api_key`); the fail-fast test at [tests/test_llm.py:105](../../../tests/test_llm.py#L105).
- [tests/test_config.py:17](../../../tests/test_config.py#L17) — extended fixture; new knob tests from [tests/test_config.py:157](../../../tests/test_config.py#L157) (defaults), [tests/test_config.py:165](../../../tests/test_config.py#L165) (overrides), [tests/test_config.py:172](../../../tests/test_config.py#L172) (blanks), [tests/test_config.py:182](../../../tests/test_config.py#L182) (invalid values).

## Block 7 — Slice: README contract rows

- [ ] unvisited

The Configuration table gains two rows, and the documented defaults are treated as part of the contract: `JANBOT_TEMPERATURE` is documented as passed to the model in every mode, with the exact clause "A value that is not a number fails fast." — wording kept deliberately narrower than the sibling knob after triage, since the code checks parse-only. `JANBOT_TOP_K` documents the retrieval top-k with the exact clause "Takes effect with the upcoming `/chat` pipeline" — an honest note that no code consumes it yet (retrieval wiring is story 3.2; the default `3` matches the store's `k=3`). Both rows were patched in response to the plan's quick-lens triage before commit.

- [README.md:55](../../../README.md#L55) — the `JANBOT_TEMPERATURE` row with the fail-fast clause.
- [README.md:56](../../../README.md#L56) — the `JANBOT_TOP_K` row with the upcoming-`/chat` clause.
- [story-3.1 plan, review triage log](../epic-rag-chat/story-lm-adapter-model-mode-routing-plan.md#L101) — the two low doc-wording findings and their patch route.

## Block 8 — Periphery

- [ ] unvisited

The 5 pre-3.1 commits, references only:

- `27f59bf` — [public_profile_org/](../../../public_profile_org/) — the JanBot SSOT corpus extract, 37 reviewed org files added as a chore.
- `64c01d2` / `9d58b31` — [README.md:31](../../../README.md#L31) and [ARCHITECTURE.md:49](../../../ARCHITECTURE.md#L49) — the two-level corpus provenance lines (JanBot SSOT is a copy of the personal SSOT, updated only by re-extraction).
- `d01dae6` — [tests/test_ingest_idempotent.py:87](../../../tests/test_ingest_idempotent.py#L87) and [tests/test_ingest_idempotent.py:103](../../../tests/test_ingest_idempotent.py#L103) — tests proving reconcile preserves and repairs payload, backed by [src/janbot/store/chroma.py](../../../src/janbot/store/chroma.py) additions.
- `731036f` — [epic-rag-chat/tickets.toml](../epic-rag-chat/tickets.toml) and [epic-ingestion/tickets.toml](../epic-ingestion/tickets.toml) with the [epic-ingestion](../epic-ingestion/epic-ingestion.md) epic closed, the [epic-rag-chat](../epic-rag-chat/epic-rag-chat.md) epic incepted with 8 stories, and the [epic-ingestion retrospective](../epic-ingestion/epic-ingestion-retrospective.md) on record.

## Status

Current block: Block 1 — Intent, in progress. No blocks are accepted yet.
