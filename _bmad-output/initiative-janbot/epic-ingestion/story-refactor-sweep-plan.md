---
title: 'Refactor sweep'
type: 'refactor'
ticket: '6'
created: '2026-10-05'
status: done
baseline_revision: '3ca7ea8'
route: 'oneshot'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-janbot/epic-ingestion/epic-ingestion.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless you explicitly renegotiate">

## Intent

**Problem:** The epic's test suite accumulated duplicated helpers — `_stub_embedder` in two files, `_write_org` in two files, a hand-built id helper — and the tracer's `within` test now duplicates the more thorough `test_scope.py`.

**Approach:** Add `tests/conftest.py` with shared fixtures/helpers (`stub_embedder`, `write_org`, `chunk_id`), switch the test files to them, and drop the redundant `within` test from the tracer. Cleanup only — no production behavior changes.

</frozen-after-approval>

## Implementation Notes

Oneshot: primarily test deduplication, mechanical. Scope set when the sweep started, from the epic's test files. No behavioral `src/` cleanup was owed (no TODOs, sizes healthy); one behavior-neutral type-annotation cleanup was included — `ChunkLike` was rewritten to read-only properties so a frozen `Chunk` statically satisfies it.

## Review Triage Log

Verdict counts: low 2.

- low | accepted | `src/janbot/store/chroma.py` — the `ChunkLike` protocol rewrite is a type-annotation-only cleanup with no runtime behavior change, within "cleanup only"; the intent's "no production behavior changes" holds. Accepted.
- low | patch | `tests/conftest.py` — the shared stub used a `0.1` base, altering every test's vectors vs the originals (and turning the constant scope embedder token-sensitive); restore a `0.0` base so the dedup is behavior-preserving.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass, count unchanged (test renamed/removed only where redundant)
