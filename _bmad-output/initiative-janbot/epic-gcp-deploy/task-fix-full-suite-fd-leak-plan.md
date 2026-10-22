---
title: 'Fix the full-suite file-descriptor exhaustion (Errno 24)'
type: 'bugfix'
ticket: ''
created: '2026-10-22'
status: 'built'
baseline_revision: '367fcd7'
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

**Problem:** the full suite (`uv run pytest -q`) fails near the end under the default `ulimit -n 1024` (50 failed, 10 errors on 3354 tests; reproduced on the parent commit `3a04152`, so pre-existing), and CI runs at 1024 — the suite cannot be trusted as a signal. **Measured profile (fd probe, this session):** the run ends at **1021/1024 fds**; every test that builds a chroma store leaks **~11–12 fds** (6 file fds per per-test `index/` dir — sqlite + journals — plus sockets and anon_inode eventfds; the final classification holds ~4–6 fds for each of the run's per-test index directories, 98 sockets, 288 anon_inode). **Named source:** chromadb 1.5.9's process-global, refcounted `System` cache (`chromadb.api.client.SharedSystemClient._identifier_to_system`/`_identifier_to_refcount`) — a `VectorStore` creates a `chromadb.PersistentClient` per instance and nothing ever closes it; each per-test tmp index path pins its own `System` (sqlite connections, HNSW artifacts, telemetry client) for the whole run. Secondary source: mlflow's per-URI engine map (`SqlAlchemyStore._engine_map`) keeps each eval test's tmp `mlflow.db` pooled connections open (~2 fds per engine).

**Approach:** close the resources where the suite opens them — one **autouse fixture in `tests/conftest.py`** whose teardown (1) releases exactly the chroma `System` references the test added, driving each to chroma's own last-reference stop (`_release_system`, which stops + pops the System) — systems opened *before* the test (the shared repo-index System created by `janbot.api.main`'s module-level `create_app()`, e2e subprocess-built indexes) keep their references and stay open; and (2) disposes (`engine.dispose()`) the mlflow engines the test added to `_engine_map`. No per-test scattering, no skips, no runtime code change, and the `ulimit` is not touched as the "fix". `RUNBOOK.md` §2 drops its `ulimit -n 16384` wrapper — it existed to mask exactly this leak and would hide regressions.

**Task constraints (from the task file, binding):** raise no ulimit as the fix; no test-semantics change (same tests, no skips, no per-test `ulimit` workarounds); evidence is a measured fd-count delta before/after, not an assertion; scope is the test suite only.

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [ ] `tests/conftest.py` — the autouse release fixture (chroma refcount delta → `_release_system`; mlflow `_engine_map` delta → `engine.dispose()`), with the why in its docstring — the fix.
- [ ] `RUNBOOK.md` §2 — run `uv run pytest -q` bare; note the leak is closed, not masked — living documentation stops masking.
- [ ] Measured evidence — re-run the fd probe under `ulimit -n 1024` after the fix and record the before/after numbers in `## Implementation Notes` — the done-when's measured delta.

**Acceptance Criteria:**
- Given the default environment limit verified as 1024 inside the run, when the full suite runs, then it completes **0 failed, 0 errors** with all 3354 tests.
- Given the probe before/after, then the per-file fd growth attributed to store-building tests collapses to ~0 and the end-of-run fd count is far below the limit (numbers recorded, not asserted).
- Given the diff, then no test is skipped or semantically changed, no runtime (`src/`) file is touched, and no ulimit manipulation exists in the fix.

## Implementation Notes

- **Files changed:** `tests/conftest.py` (autouse `release_per_test_stores` fixture),
  `RUNBOOK.md` §2 (drop the `ulimit -n 16384` wrapper). No `src/` change, no test
  semantics change (3354 tests before and after, no skips).
- **Measured before (probe run, `ulimit -n 1024`, baseline `367fcd7`):** final fd count
  **1021/1024**; `50 failed, 3294 passed, 10 errors`; ~11–12 fds leaked per
  store-building test (6 file fds per per-test `index/` dir + sockets + anon_inode);
  final classification held a 4–6-fd block per per-test index directory, 98 sockets,
  288 anon_inode. The probe itself then failed to `open()` its report at session finish
  with `OSError: [Errno 24]` — the ceiling reached, direct evidence.
- **Measured after (same probe, same limit):** final fd count **26** (initial 12);
  `3354 passed, 0 failed, 0 errors`; per-file net growth ≤ +2 (transient) and **0** for
  every store-building module; final classification holds only the shared repo-index
  chroma System (6 fds — `janbot.api.main`'s module-level `create_app()` at import,
  deliberately kept) plus 3 sockets / 3 anon_inode / 5 pipes. Ceiling delta: **995 fds**.
- **The one +14 jump** is the first e2e chat test: the session-scoped subprocess service
  fixture's pipes/sockets, bounded once for the session — not a per-test leak.
- **Why the delta approach, not `clear_system_cache()` alone:** dropping the cache only
  removes references; stopping the Systems is what closes sqlite/HNSW/telemetry fds, and
  a refcount delta releases exactly what the test opened while leaving systems created
  before the test (the shared repo-index app) untouched. Verified no session- or
  module-scoped in-process chroma store exists: the e2e indexes are built in
  subprocesses (`tests/e2e/conftest.py`).
- **Raised-limit check:** `ulimit -n 16384` → `3354 passed` as well (no regression for
  local shells that retain the old habit).
- **Review round (quick lens) — four record/robustness findings, all patched:**
  (1) the mlflow half disposed engines by new-URI key but left the key in
  `_engine_map`, so a later test reusing a URI would reconnect the disposed engine and
  the store lru-cache would hand back the stale store — fixed by **disposing and
  popping** the engines the test created and clearing the tracking-store cache when
  anything was disposed; proven with a throwaway two-test module sharing one sqlite URI
  (2 passed, 14 fds at session end, no `mlflow.db` open). (2) `RUNBOOK.md` §8's trap row
  still prescribed `ulimit -n 16384` — replaced with the fixture reference and the
  measured numbers. (3) `README.md` §Development still declared the suite "not fixed"
  at 1024 and told readers to raise the limit — replaced with the fixed state. (4) the
  two fd entries in `deferred-work.md` still read "not fixed" — dated closure notes
  appended (history kept, no rewrite).

## Review Triage Log

Quick lens, 2026-10-22. Four findings, all verified and patched; nothing deferred.

- **mlflow disposal missed the URI-reuse case — medium — patch (fixed).** Verified: `_get_or_create_engine` caches by URI and `dispose()` leaves the key, while `TrackingStoreRegistry._get_store_with_resolved_uri` is `@lru_cache`d — a later test sharing a URI reconnects the disposed engine and teardown skips it. Fixed by popping disposed engines and clearing the store cache; proven with a throwaway two-test shared-URI module (14 fds at end, no `mlflow.db` open).
- **RUNBOOK §8 trap row still prescribed `ulimit -n 16384` — medium — patch (fixed).** Verified the row contradicted §2 (same file); replaced with the fixture reference and the measured 1021→26 numbers, with "a reappearance is a regression — do not raise the limit".
- **README §Development still declared the suite known-red at 1024 — medium — patch (fixed).** Verified the blockquote's three claims ("21 failed / 496 passed", "517 passed", "not fixed") are all false on this tree; replaced with the fixed state.
- **`deferred-work.md` fd entries still recorded the leak as open — low — patch (fixed).** Verified both entries said "not fixed" and pointed at the README note; appended dated closure notes with the measured result, leaving the original evidence intact.

## Verification

**Commands:**
- `bash -c 'ulimit -n 1024 && echo "in-run ulimit: $(ulimit -n)" && uv run pytest -q'` — expected: `3354 passed`, 0 failed, 0 errors.
- `bash -c 'ulimit -n 1024 && PYTHONPATH=/tmp/opencode uv run pytest -q -p fdprobe'` (throwaway probe, not committed) — expected: final fd count far below 1024; the per-file growth table shows no per-test store growth; numbers recorded in `## Implementation Notes`.
- `ulimit -n 16384 && uv run pytest -q` — still green at a raised limit too (no regression for local shells that keep the old habit).
