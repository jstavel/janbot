# Task — fix the full-suite file-descriptor exhaustion (Errno 24)

**Priority:** medium · **Type:** bug/infra · **Scope:** test suite only, no
runtime code changes expected.

## Problem

Running the full suite (`uv run pytest -q`) under the default
`ulimit -n 1024` fails near the end of the run:

- `50 failed, 3294 passed, 10 errors` (= 3354 total) with failures including
  `OSError: [Errno 24] Too many open files` surfaced in pytest's `rm_rf`
  warnings; chroma-based tests (`test_scope.py`, `test_store_hybrid.py`,
  `test_ingest_tracer.py`, `test_ingestion_e2e.py`, `test_ingest_idempotent.py`)
  and `test_usage.py` errors dominate.
- Every failing test **passes in isolation** — this is cross-test interference,
  not a regression in any of them.
- Reproduced on the parent commit `3a04152` as well (36 failed) → **pre-existing
  leak**, not introduced by E3.
- With `ulimit -n 8192` the same tree gives **3354 passed, 0 failed** —
  confirming the failure mode is fd exhaustion, not flakiness or a code bug.

## Why it matters

CI runners typically run with the default 1024 soft limit, so the suite will
flake there regardless of code quality. The flake is deterministic near the
end of the run, which makes bisecting real regressions noisy — a failing suite
can no longer be trusted as a signal.

## Done when (evidence)

1. `uv run pytest -q` completes **0 failed** with the default `ulimit -n` of
   the environment (verify the limit first: `ulimit -n` must read 1024, not a
   raised value inherited from the shell).
2. The leak's source is identified and named in the story notes — suspected
   suspects, in order of likelihood: chroma clients/`VectorStore` instances
   opened per test without close, mlflow tracking handles in eval tests,
   or the ONNX/ORT session descriptors. Evidence should be a measured fd
   count growth (e.g. `/proc/<pytest-pid>/fd` sampling) before and after the
   fix, not an assertion.
3. No test semantics change: the same 3354 tests exist and pass; no skips
   added; no per-test `ulimit` workarounds.

## Constraints

- Do not raise the ulimit as the "fix" — the leak is real and must be closed;
  the limit change only masks it and would break on stricter CI images.
- Fixtures closing resources belong where the resources are opened (conftest
  or the store/eval fixtures), not scattered per-test.
- If the leak turns out to be inside chromadb/pyo3 and unfixable upstream,
  propose the smallest deterministic containment (e.g. a session-scoped
  client) and record why — do not silently skip.
