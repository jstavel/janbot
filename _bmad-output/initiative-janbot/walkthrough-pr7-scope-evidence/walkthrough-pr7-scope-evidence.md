# Walkthrough — PR #7: "isolate both scope filters and rank-compare private notes" (story 3.7)

Target: PR https://github.com/jstavel/janbot/pull/7 · branch `story-3.7-scope-evidence` · commit `274a5e1`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: isolating each scope filter
- [x] Block 4 — Slice: the ranked comparison
- [x] Block 5 — Periphery

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-scope-refusal-evidence-hardening-dw3-plan.md](../epic-rag-chat/story-scope-refusal-evidence-hardening-dw3-plan.md).

> **Problem:** epic-ingestion Done-when 3 ("a private note outside the public folder changes no retrieval result; a non-whitelisted path is offered and refused fail-closed") is only weakly evidenced. `iter_org_files` and `index_corpus` each carry a `within` filter, so a test that removes either filter alone still passes, and no test hands an out-of-scope path directly to `index_corpus`. "Changes no retrieval result" is narrowed to an id-set diff plus one post-hoc query, not a ranked-result comparison.
>
> **Approach:** Add tests that isolate the `index_corpus` scope guard (hand it an out-of-scope path directly so removing that guard fails) and that compare *ranked* retrieval before and after a private note is placed, so a private note altering top-k ordering fails the suite. Tests only — no production code change.

## Block 2 — Broad strokes

Test-only change in one file: three new tests in [tests/test_scope.py](../../../tests/test_scope.py) that make each scope filter individually observable and rank-compare the private-note case. Open these three spots:

- [test_scope.py:155](../../../tests/test_scope.py) — the `index_corpus` guard, isolated.
- [test_scope.py:180](../../../tests/test_scope.py) — the `iter_org_files` filter, isolated.
- [test_scope.py:203](../../../tests/test_scope.py) — the ranked comparison.

## Block 3 — Slice: isolating each scope filter

Two filters guard the corpus: `iter_org_files` drops out-of-scope paths, and `index_corpus` re-checks with `within`. Each test neutralizes the *other* mechanism so that only one filter can do the work.

- [test_scope.py:155](../../../tests/test_scope.py) — patches `janbot.ingest.iter_org_files` to hand `index_corpus` an out-of-scope path; asserts `index_corpus` indexes nothing (0 chunks, empty store).
- [test_scope.py:180](../../../tests/test_scope.py) — patches `Path.rglob` to yield an in-root and an out-of-root file; asserts `iter_org_files` yields only the in-root one.

## Block 4 — Slice: the ranked comparison

- [test_scope.py:203](../../../tests/test_scope.py) — indexes a public corpus, captures the *ranked* `query` list, then offers a private file to the indexer (via patched `iter_org_files`) and re-indexes; asserts the ranked list is identical before and after. A regression that let the private note in would reorder the list.

## Block 5 — Periphery

- [story-scope-refusal-evidence-hardening-dw3-plan.md](../epic-rag-chat/story-scope-refusal-evidence-hardening-dw3-plan.md) — the plan (`built`); Implementation Notes and Review Triage Log record the mutation-verification and the review fixes.
