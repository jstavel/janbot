# Walkthrough — PR #8: "reconcile stale api/pipeline/llm/config docstrings" (story 3.8)

Target: PR https://github.com/jstavel/janbot/pull/8 · branch `story-3.8-refactor-sweep` · commit `cbaee61`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: docstring reconciliation
- [x] Block 4 — Slice: recording the deferred items
- [x] Block 5 — Periphery

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-refactor-sweep-plan.md](../epic-rag-chat/story-refactor-sweep-plan.md).

> **Problem:** The epic's cleanup items are still open. Earlier stories left stale docstrings in `api/`, `pipeline/`, `llm/` that no longer match the code: `llm/__init__.py` still says the OpenRouter key's sourcing is "decided later, by the `/chat` pipeline story" (story 3.2 wired it), and `pipeline/chat.py` describes citations as taken from raw `source_path` metadata "then" rewritten (3.4 rewrites first) and the LM as set "at construction time" (it is set after construction, at startup). Separately, the epic named a cross-cutting review item for this sweep — chunk-id stability — which lives in `ingest/org.py`, outside this epic's edit boundary, so it can only be recorded here.
>
> **Approach:** A cleanup-only pass over `api/`, `pipeline/`, `llm/`: reword the stale docstrings/comments to match the code, keep the import-order guards exactly as-is (they are load-bearing), and record the out-of-boundary items in `deferred-work.md` so none is lost. No behaviour change.

## Block 2 — Broad strokes

Docs-and-comments only across four source files plus the deferred list. Open these spots:

- [src/janbot/llm/__init__.py](../../../src/janbot/llm/__init__.py) — the key-sourcing note now points at `OPENROUTER_API_KEY`.
- [src/janbot/pipeline/chat.py](../../../src/janbot/pipeline/chat.py) — citation-order and `set_lm` wording.
- [src/janbot/api/main.py](../../../src/janbot/api/main.py) and [src/janbot/config.py](../../../src/janbot/config.py) — import-order / module docstrings.
- [deferred-work.md](../deferred-work.md) — the two recorded sweep decisions.

## Block 3 — Slice: docstring reconciliation

Each reworded line now matches what the code actually does.

- [llm/__init__.py:22](../../../src/janbot/llm/__init__.py) — key is sourced from `OPENROUTER_API_KEY` by the app (was: "decided later").
- [chat.py:8](../../../src/janbot/pipeline/chat.py) — rewrite labels → validate claims → cite (matches 3.4); [chat.py:15](../../../src/janbot/pipeline/chat.py) — LM set at startup.
- [main.py:18](../../../src/janbot/api/main.py) — the import-order note now records the real minimal repro (`import dspy` before `chromadb`).
- [config.py](../../../src/janbot/config.py) — module docstring no longer calls the OpenRouter key a "later, separately-managed concern".

## Block 4 — Slice: recording the deferred items

- [deferred-work.md](../deferred-work.md) — chunk-id stability (needs `ingest/`, its own ticket) and the scoped-query over-fetch optimization (perf, `store/`), each with rationale so neither is lost.

## Block 5 — Periphery

- [story-refactor-sweep-plan.md](../epic-rag-chat/story-refactor-sweep-plan.md) — the plan (`built`); Implementation Notes + Review Triage Log record the two review fixes (reverted `corpus_relative` narrowing; corrected import-order repro).
