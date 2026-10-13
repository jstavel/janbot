---
title: 'Refactor sweep'
type: 'refactor'
ticket: 8
created: '2026-10-13'
status: 'done'
baseline_revision: 'a3d6b8e9f8c2bb43f152db06000cd22e3ea06a36'
route: 'oneshot'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The epic's cleanup items are still open. Earlier stories left stale docstrings in `api/`, `pipeline/`, `llm/` that no longer match the code: `llm/__init__.py` still says the OpenRouter key's sourcing is "decided later, by the `/chat` pipeline story" (story 3.2 wired it), and `pipeline/chat.py` describes citations as taken from raw `source_path` metadata "then" rewritten (3.4 rewrites first) and the LM as set "at construction time" (it is set after construction, at startup). Separately, the epic named a cross-cutting review item for this sweep — chunk-id stability — which lives in `ingest/org.py`, outside this epic's edit boundary, so it can only be recorded here.

**Approach:** A cleanup-only pass over `api/`, `pipeline/`, `llm/`: reword the stale docstrings/comments to match the code, keep the import-order guards exactly as-is (they are load-bearing — verified: importing `dspy` before `chromadb` fails with `data type 'bool' not understood`), and record the out-of-boundary items in `deferred-work.md` so none is lost. No behaviour change.

## Boundaries & Constraints

**Always:**
- Cleanup only: docstrings/comments in `api/`, `pipeline/`, `llm/`; no behaviour change and no new public surface.
- Keep the `janbot.store`-before-`dspy` import-order guards and their comments (verified necessary on the pinned stack).
- The suite stays green; every 3.1–3.7 pin passes unchanged.

**Never:**
- No edits to `store/`, `ingest/`, `api/contract.py`, or the test layer's behaviour; `config.py` only for its module docstring (see the decision below).
- Do not remove the `build_lm` production-key fail-fast or the `create_app` boot gate — both are tested contracts (defence-in-depth, intentional).
- No chunk-id change (it would edit `ingest/org.py`, outside this epic).

## I/O & Edge-Case Matrix

Bar: below this line is (deliberately) empty — a cleanup pass has no I/O.

Decision (2026-10-13, human): sweep depth **B + C** — docstring/comment cleanups in `api/`/`pipeline/`/`llm/`, the matching stale phrase in `config.py`'s module docstring, and a verification note on the import-order guards. Chunk-id stability and the scoped-query over-fetch optimization are deferred (recorded in `deferred-work.md`).

</frozen-after-approval>

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: Docstring/comment cleanups only — no runtime behaviour changed.
  - `src/janbot/llm/__init__.py` — the key-sourcing note now points at `OPENROUTER_API_KEY` / `janbot.api.main` instead of "decided later".
  - `src/janbot/pipeline/chat.py` — docstring reordered to match 3.4 (rewrite labels → validate claims → cite) and `set_lm` described as set at startup.
  - `src/janbot/api/main.py`, `src/janbot/pipeline/chat.py`, `src/janbot/config.py` — import-order comments and the config module docstring reconciled; the verification note records the real minimal repro.
- 2026-10-13: Option B's `Path(root).resolve()` micro-tidy was **reverted** — dropping the wrapper narrowed `corpus_relative` (a `str` root would raise instead of working), which conflicts with the "no behaviour change" rule; the verification-note half of B was kept.
- Verification: `uv run pytest -q` → 130 passed. Corrected claim reproduces: `python -c "import dspy, chromadb"` → `TypeError: data type 'bool' not understood`.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 2 medium / 1 low / 0 false / 0 maybe-false.** All addressed.
- **`config.py` edit conflicted with the frozen Never list** — **verdict: medium**. Real: the plan's Never barred `config.py`, yet the docstring was reworded per the human's B+C choice. **route: fixed** — the B+C decision is now recorded in the frozen intent, and Never scoped to `config.py` *code*.
- **`corpus_relative` `Path()` micro-tidy narrowed a public function** — **verdict: medium**. Verified: the sole caller passes `Path`, but a `str` root would now raise. **route: fixed** — reverted to `Path(root).resolve()` (the verification-note half of B kept).
- **The added "verified" note stated the wrong repro** — **verdict: low**. Verified: `import dspy, numpy` succeeds; the failure needs `import dspy, chromadb`. **route: fixed** — comments corrected to the real minimal repro.
- Note: the frozen Intent's Approach still carries the same wrong parenthetical ("dspy before numpy"); flagged for the human since the frozen block is theirs.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: 130 passed

