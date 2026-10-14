---
title: 'Rewriter coverage & guard alignment'
type: 'bugfix'
ticket: ''
created: '2026-10-13'
status: 'built'
baseline_revision: '690ae721375e7c958d1e8d06677ba74808572a6f'
route: 'oneshot'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem (two parts):** (1) `corpus_relative` / `UnattributableContext` (`src/janbot/pipeline/chat.py:58-75`) have **zero test coverage** after story 3.6 repointed the out-of-root port row to the store-boundary 503; a regression in the rewriter, or building it from the wrong root, passes the whole suite — the "second, fail-closed guard" is untested. (2) The two fail-closed guards **disagree on a relative `source_path`**: the store's `_within_scope` (`src/janbot/store/chroma.py:57`) does `os.path.abspath(source_path)` (CWD-dependent — may accept), while the rewriter does `Path(source_path).relative_to(resolved_root)` (fails for a relative path → `UnattributableContext` → 500). A relative-source chunk can therefore enter the prompt at the store and then 500 at the rewriter with a message falsely claiming the source "lies outside the corpus root"; the store's verdict also depends on the process CWD, contradicting the documented CWD-independence. Recorded in the epic-rag-chat retrospective.

**Approach:** make the two guards **agree** on non-absolute paths (decision below) and add **direct coverage** for both, so each branch fails loudly under a mutation.

## Boundaries & Constraints

**Always:**
- A non-absolute or otherwise unjudgeable `source_path` is handled *consistently* by the store and the rewriter — no chunk can pass one guard and fail the other.
- Fail-closed: an out-of-root or malformed `source_path` is never cited.
- The 3.2–3.8 pins stay green; the `/chat` contract is unchanged.

**Never:**
- No change to retrieval ranking, ingestion, config, or the contract models; no new route or field.
- Do not change which *absolute* in-root sources are cited.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | absolute in-root `source_path` | rewritten to a corpus-relative label | No error |
| ERROR | absolute out-of-root `source_path` | never cited (store excludes; rewriter refuses) | 503 or `UnattributableContext` |
| EDGE | relative `source_path` | store and rewriter agree (both reject) | consistent fail-closed |
| EDGE | missing / non-string `source_path` | excluded by the store | No error |

Decision (2026-10-13): option 1A — the store requires an **absolute** `source_path` (relative/non-string excluded, fail-closed); the rewriter already refuses relative, so both reject and the invariant is enforced at the store boundary. Option 2A — a focused unit test of the pure `corpus_relative` helper, a recorded narrow deviation from AD-7's port-only rule because 3.6 made the rewriter's out-of-root branch unreachable through the port.

Decision (2026-10-13, review): the rewriter judges containment by the **located** path (resolve the containing directory, keep the final component) — matching the store — which closes the symlink-form mismatch between the two guards (option A extended); the store's `_within_scope` docstring drops the inexact "mirrors `ingest.scope.within`" claim.

</frozen-after-approval>

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (139 baseline + new coverage rows)

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: `src/janbot/store/chroma.py` — `_within_scope` now requires an absolute `source_path` (non-absolute excluded, fail-closed); docstring corrected. `src/janbot/pipeline/chat.py` — `corpus_relative` now refuses non-absolute sources explicitly and judges containment by the *located* path, matching the store. `tests/test_store_scope.py` gains relative- and `..`-path exclusion rows (the relative row `chdir`s into the root so it mutation-catches the guard). `tests/test_citation_rewrite.py` (new) covers the rewriter directly: in-root, nested, symlinked-in-root, out-of-root, and relative.
- Mutation-verified: removing the store's `is_absolute` guard fails the store row; removing the rewriter's guard fails the relative row; the symlink row catches the old literal-string `relative_to`.
- Verification: `uv run pytest -q` → 146 passed.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 3 medium / 2 low / 0 false / 0 maybe-false.** All routed to patch.
- **Relative-refusal test not mutation-sensitive** (passed under an absolutize regression) — **verdict: medium**. **route: patch** — `chdir` into the root.
- **Symlink-form absolute path still diverged** (store located vs rewriter literal) — **verdict: medium**. Verified live. **route: patch** — rewriter now judges the located path, matching the store; symlink row added.
- **Store `..` branch unpinned** (deletion passed the suite) — **verdict: medium**. **route: patch** — added a `..`-path exclusion row.
- **`_within_scope` docstring's "mirrors `ingest.scope.within`" now false** — **verdict: low**. **route: patch** — docstring corrected.
- **Rewriter tests fed unresolved paths against a resolved root** (platform-fragile) — **verdict: low**. **route: patch** — resolved by the located-path change; tests remain on `tmp_path`.
