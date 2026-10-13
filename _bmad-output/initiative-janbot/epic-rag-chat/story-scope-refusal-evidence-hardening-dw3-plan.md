---
title: 'Scope/refusal evidence hardening (DW3)'
type: 'chore'
ticket: 7
created: '2026-10-13'
status: 'built'
baseline_revision: 'a4b4e31297a3df253d9d0d9b516c4fbbb7b0c64e'
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

**Problem:** epic-ingestion Done-when 3 ("a private note outside the public folder changes no retrieval result; a non-whitelisted path is offered and refused fail-closed") is only weakly evidenced. `iter_org_files` and `index_corpus` each carry a `within` filter, so a test that removes either filter alone still passes, and no test hands an out-of-scope path directly to `index_corpus` (`epic-ingestion-retrospective.md:61`). "Changes no retrieval result" is narrowed to an id-set diff plus one post-hoc query, not a ranked-result comparison (`:62`).

**Approach:** Add tests that isolate the `index_corpus` scope guard (hand it an out-of-scope path directly so removing that guard fails) and that compare *ranked* retrieval before and after a private note is placed, so a private note altering top-k ordering fails the suite. Tests only — no production code change.

</frozen-after-approval>

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: All changes are in `tests/test_scope.py`; no production code changed.
  - `test_index_corpus_refuses_out_of_scope_path_handed_directly` — monkeypatches `janbot.ingest.iter_org_files` to hand `index_corpus` an out-of-scope path, isolating its `within` guard.
  - `test_iter_org_files_refuses_out_of_scope_path_from_its_own_filter` — monkeypatches `Path.rglob` to yield an in-root and an out-of-root file, isolating `iter_org_files`' own `within` filter.
  - `test_private_note_changes_no_ranked_retrieval` — offers a private file to the indexer via patched `iter_org_files` and asserts the *ranked* query list is unchanged before/after.
- Mutation-verified (the DW3 point): removing `index_corpus`' `within` guard fails (1) and (3); removing `iter_org_files`' `within` fails (2). Full suite: 130 passed.
- Review fix: the first draft's ranked test relied on a symlinked directory, but Python 3.12 `rglob` does not descend symlinked dirs, so it could never fail on a scope regression (reviewer mutation-tested). Rewritten to inject the private path.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 2 medium / 1 low / 0 false / 0 maybe-false.** All routed to patch.
- **Direct-refusal test isolates only one of the two filters** (`tests/test_scope.py:155`) — **verdict: medium**. Verified by mutation: dropping `iter_org_files`' `within` left the suite green, so "removing either filter alone fails" was met for only `index_corpus`. **route: patch** — added `test_iter_org_files_refuses_out_of_scope_path_from_its_own_filter`.
- **Ranked test's symlink premise is false on Python 3.12** (`tests/test_scope.py:180`) — **verdict: medium**. Verified: `rglob` does not recurse symlinked dirs, so the private file was never reachable and the test could not fail on a scope regression. **route: patch** — rewritten to offer the private path directly to the indexer and compare ranked output.
- **Implementation Notes left empty** (`story-scope-refusal-evidence-hardening-dw3-plan.md`) — **verdict: low**. **route: patch** — recorded files, decisions, and the mutation-verification above.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (127 baseline + new scope-evidence rows)
