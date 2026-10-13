# Walkthrough — PR #12: "align store and citation guards on located absolute paths; cover rewriter"

Target: PR https://github.com/jstavel/janbot/pull/12 · branch `hardening-rewriter-alignment` · commit `6d84d65`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the store guard requires an absolute path
- [x] Block 4 — Slice: the rewriter aligns on the located path + direct coverage
- [x] Block 5 — Periphery

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [plan-rewriter-coverage-alignment.md](../plan-rewriter-coverage-alignment.md).

> **Problem (two parts):** (1) `corpus_relative` / `UnattributableContext` have **zero test coverage** after story 3.6 repointed the out-of-root port row to the store-boundary 503; a regression in the rewriter, or building it from the wrong root, passes the whole suite. (2) The two fail-closed guards **disagree on a relative `source_path`**: the store's `_within_scope` does `os.path.abspath` (CWD-dependent — may accept), while the rewriter's `relative_to` fails for a relative path → 500. A relative-source chunk can enter the prompt at the store then 500 at the rewriter with a message falsely claiming the source "lies outside the corpus root"; the store's verdict also depends on the CWD, contradicting the documented CWD-independence.
>
> **Approach:** make the two guards **agree** on non-absolute paths and add **direct coverage** for both, so each branch fails loudly under a mutation.

## Block 2 — Broad strokes

Two guards made to agree, plus coverage. Open these spots:

- [store/chroma.py:60](../../../src/janbot/store/chroma.py) — the store guard's absolute-path requirement.
- [pipeline/chat.py:59](../../../src/janbot/pipeline/chat.py) — the rewriter, now located-path aligned.
- [tests/test_citation_rewrite.py](../../../tests/test_citation_rewrite.py) — direct rewriter coverage.
- [tests/test_store_scope.py:159](../../../tests/test_store_scope.py) — store exclusion rows.

## Block 3 — Slice: the store guard requires an absolute path

- [chroma.py:60](../../../src/janbot/store/chroma.py) — `if not Path(source_path).is_absolute(): return False` — a relative source is unjudgeable and excluded, so the store no longer depends on the process CWD; [chroma.py:66](../../../src/janbot/store/chroma.py) judges containment by the located path; the docstring drops the now-false "mirrors `ingest.scope.within`" claim.

## Block 4 — Slice: the rewriter aligns on the located path + direct coverage

- [chat.py:72](../../../src/janbot/pipeline/chat.py) — a non-absolute source is refused explicitly; [chat.py:78](../../../src/janbot/pipeline/chat.py) — containment is judged by the located path (resolve the containing directory, keep the final component), matching the store, so a symlink-form absolute path no longer passes the store and fails the rewriter.
- [tests/test_citation_rewrite.py](../../../tests/test_citation_rewrite.py) — in-root, nested, symlinked-in-root, out-of-root, and relative; a recorded narrow deviation from port-only AD-7 (the branch is unreachable through the port after 3.6).
- [tests/test_store_scope.py:159](../../../tests/test_store_scope.py) — a relative row that `chdir`s into the root (so it mutation-catches the guard) and a `..`-path row.

## Block 5 — Periphery

- [plan-rewriter-coverage-alignment.md](../plan-rewriter-coverage-alignment.md) — the plan (`built`); Triage Log records the five review fixes.
