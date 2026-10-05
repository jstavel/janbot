---
title: 'Fail-closed scope filter'
type: 'feature'
ticket: '4'
created: '2026-10-05'
status: done
baseline_revision: '3eec6ca550f1a2d3c9f009e90775627d68a2c458'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-janbot/epic-ingestion/epic-ingestion.md'
  - '_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md'
  - '_bmad-output/initiative-janbot/deferred-work.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The tracer's `within()` resolves symlinks, so the epic's chosen public layout — a scope folder holding files **symlinked** from their real locations in `~/org` — yields nothing (confirmed in the 2.2 review). The scope rule must be settled: what is "public" is defined by *where a file is placed*, not where its target lives, while anything physically located outside the root stays excluded.

**Approach:** Make the scope filter **symlink-aware and fail-closed**: a path is in scope only when its *located* path (symlinks in the final component not followed, `..` collapsed) is under the configured root. Resolve the root itself (so a symlinked root works). `iter_org_files` yields `.org` files located under the root, including symlinked files, and does not descend symlinked directories. Any unresolvable or escaping path is refused.

## Boundaries & Constraints

**Always:** decisions are made on the located path, not the symlink target; the root may itself be a symlink (resolve it once); `..` escapes and paths outside the root are refused; refusals never raise (fail-closed); `.org` files only; deterministic order.

**Never:** no embedding/store changes; no idempotency (entry 2.5); no DSPy/`/chat`; no new dependency; do not follow symlinked directories out of the root; do not index a path merely because its target is inside the root (location governs).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Symlinked public file | `root/pub.org -> ~/org/real.org` (target outside root) | in scope; indexed (its content read through the link) | No error |
| Outside file | `elsewhere/priv.org` | refused; never yielded by `iter_org_files` | No error |
| Directory escape | `root/../priv.org` | refused | No error |
| Symlinked directory | `root/link -> ~/org` (dir symlink) | not descended; files behind it are not indexed | No error |
| Symlinked root | the root itself is a symlink | its files are in scope (root resolved once) | No error |
| Unresolvable / missing | a path that cannot be normalized | refused | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/ingest/scope.py` -- MODIFY. Current: `within(root, path)` calls `Path(path).resolve()` on both sides (follows symlinks) and `iter_org_files(root)` uses `rglob("*.org")`. Change `within` to compare the *located* path: `Path(os.path.abspath(path))` (CWD-anchored, `..` collapsed by normpath) against a once-resolved root, using `is_relative_to`; do not resolve the candidate's final component. Keep `iter_org_files` yielding symlinked files; confirm `rglob` does not descend symlinked dirs (it does not by default).
- `src/janbot/ingest/__init__.py` -- `index_corpus` already filters each yielded path through `within`; no signature change expected.
- `tests/test_scope.py` -- NEW: the matrix rows (symlinked file indexed, outside refused, `..` refused, dir-symlink not descended, symlinked root).
- `tests/test_ingest_tracer.py` -- its `test_within_is_fail_closed` may need updating to the new semantics (a symlinked path inside the root is now in scope).
- Reference: `deferred-work.md` (the symlink-policy item), `architecture-janbot.md` AD-3, `epic-ingestion.md` Done-when 3.

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/ingest/scope.py` -- located-path containment, resolved root, symlink-aware, fail-closed -- covers CAP-4
- [ ] `tests/test_scope.py` + update `tests/test_ingest_tracer.py` -- the matrix rows -- verification

**Acceptance Criteria:**
- Given a public file symlinked into the root from outside, when the corpus is indexed, then its chunks are stored and retrievable.
- Given a private `.org` file outside the root, when the corpus is indexed, then it is refused and changes no query result.
- Given a `root/../priv.org` path, when checked, then `within` is `False`; given an unresolvable path, then `within` is `False`.
- Given a directory symlink inside the root, when walked, then its target's files are not indexed.

## Implementation Notes

Settles the deferred symlink-policy item: containment is judged on the located path, so symlinked public files are indexed while anything physically outside stays out. Review patches also unified `read_org_file`'s `source_path`/id onto the located path (no target leak).

## Plan Change Log

## Review Triage Log

Verdict counts: medium 2, low 2.

- medium | patch | `src/janbot/ingest/scope.py` — `within` accepts `root/mid/../secret.org` when `mid` is a symlinked dir (lexical `..` collapse erases the symlink), so an escaping path is in scope (probe: realpath outside but `within` True). Not reachable via `rglob`, but `within` is public API. Fix: fail-closed on any `..` component.
- medium | patch | `src/janbot/ingest/org.py` — a symlinked public file is stored with `source_path`/id = the symlink target outside the root (which `within` then refuses), leaking the real location and breaking "location governs". Fix: build `source_path`/id from the located absolute path (no final-component symlink resolution).
- low | patch | `src/janbot/ingest/scope.py` — `within(root, root)` is False when the root is a symlink whose parent path also contains a symlink. Fix: make the root-equals case hold for a symlinked root.
- low | patch | `tests/test_scope.py` — the outside-file test only checks an empty index (AC2 wants a populated index unaffected); add a populated-index assertion and a symlinked-file `source_path`-inside-root assertion.

## Design Notes

The epic chose a *folder* as the public boundary whose contents may be symlinks. Therefore containment must be judged by where the link sits, not where it points: an operator's act of placing a link in the public folder is the whitelist decision. This keeps fail-closed behavior (a file physically outside stays out; a symlinked dir is not descended) while making the symlinked layout work. The root is resolved once so a symlinked root folder is still handled.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass
