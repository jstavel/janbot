---
title: 'End-to-end ingestion suite'
type: 'feature'
ticket: '7'
created: '2026-10-05'
status: done
baseline_revision: '138cb4aa036bba1645d01716dd6add2308f8f7b9'
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

**Problem:** The epic's Done-when is proven piecemeal across unit tests; there is no single hermetic suite that runs the whole pipeline and would fail if the chunker or the scope filter regressed.

**Approach:** Add `tests/test_ingestion_e2e.py`: build a small hermetic org corpus (nested headings, PROPERTIES, tags, LOGBOOK, child content), run `index_corpus` with the stub embedder, and assert end to end — subtree chunks with breadcrumbs/properties/tags/child content land in a populated, queryable index; a private file placed outside the root is refused and changes no result; a re-run is idempotent.

</frozen-after-approval>

## Implementation Notes

Oneshot: one new test module over the existing pipeline, no `src/` change. Reuses the `embedder` fixture from `conftest.py`; the corpus is written into `tmp_path` so the suite is hermetic and offline.

## Review Triage Log

Verdict counts: low 4. The lens mutation-tested the suite and found it too weak to catch the regressions it promises to.

- low | patch | `tests/test_ingestion_e2e.py` — no assertion that an ancestor chunk aggregates descendant text (mutation: disabling the recursion still passed). Fix: assert the child text is in the parent chunk.
- low | patch | `tests/test_ingestion_e2e.py` — the store round-trip asserted only `source_path`, not indexed text (mutation: persisting the breadcrumb instead of text still passed). Fix: assert retrieved `text` carries the expected content.
- low | patch | `tests/test_ingestion_e2e.py` — LOGBOOK was absent from the corpus assertions. Fix: assert the LOGBOOK note is in the chunk text.
- low | patch | `tests/test_ingestion_e2e.py` — the "changes no result" check was vacuous on an empty result set. Fix: assert `rows` and that no private text is present.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass
- `uv run pytest -q tests/test_ingestion_e2e.py` -- expected: the new suite passes
