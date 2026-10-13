# Walkthrough — PR #22: "add keyed e2e CI job and dedup the e2e harness"

Target: PR https://github.com/jstavel/janbot/pull/22 · branch `hardening-verification-followups` · commit `558f4ea`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the keyed CI job
- [x] Block 4 — Slice: the e2e dedup
- [x] Block 5 — Periphery

## Status

All blocks accepted: 5 of 5. Review complete: PR #22 squash-merged (`77ca93d`), plan set to done.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-verification-followups-plan.md](../story-verification-followups-plan.md).

> **Problem:** the `epic-verification` retrospective left two tracked items open. (1) The keyed e2e rows (4.1 happy path, 4.4 determinism) `skipif` without a key and CI runs keyless, so Done-when 1/3 are never machine-exercised — the F1 verification gap. (2) The e2e harness duplicates small things: the same `QUESTION`, the same 503 `{detail}` assertion, and the subprocess-RUN boilerplate in `conftest.py`.
>
> **Approach:** (1) add a scheduled/manual **keyed** CI workflow that runs `tests/e2e` with `OPENROUTER_API_KEY` (skipping cleanly when the secret is unset); (2) extract a `tests/e2e/_support.py` with the shared `QUESTION`, key-env name and envelope assertion, and factor the duplicated subprocess-run boilerplate in `conftest.py`. No production code.

## Block 2 — Broad strokes

A new CI workflow plus an e2e harness refactor — two spots:

- [.github/workflows/e2e-keyed.yml](../../../.github/workflows/e2e-keyed.yml) — the keyed job.
- [tests/e2e/_support.py](../../../tests/e2e/_support.py) — the shared helpers; [tests/e2e/conftest.py:73](../../../tests/e2e/conftest.py#L73) — `_run_cli`.

## Block 3 — Slice: the keyed CI job

Runs `tests/e2e` with `OPENROUTER_API_KEY` on a schedule and on demand. It gates on the **trimmed** key (matching the tests' own gate) and fails if pytest reports any `skipped`, so a green job proves the keyed rows ran; it exits 0 with a message when the secret is unset.

- [e2e-keyed.yml:16](../../../.github/workflows/e2e-keyed.yml#L16) — the `e2e-keyed` job; [e2e-keyed.yml:36](../../../.github/workflows/e2e-keyed.yml#L36) — the run step; [e2e-keyed.yml:50](../../../.github/workflows/e2e-keyed.yml#L50) — the skip guard.

## Block 4 — Slice: the e2e dedup

`_support.py` holds the one `QUESTION`, the key-env name, and the `{detail}` envelope assertion the modules share (imported as `from e2e._support import …`); `conftest._run_cli` collapses the two identical subprocess-run blocks.

- [tests/e2e/_support.py:13](../../../tests/e2e/_support.py#L13) — `QUESTION`/`MODEL_KEY_ENV`; [tests/e2e/_support.py:19](../../../tests/e2e/_support.py#L19) — `assert_detail_string`.
- [tests/e2e/conftest.py:73](../../../tests/e2e/conftest.py#L73) — `_run_cli`, used by `_build_fixture_index` and `_make_index`.

## Block 5 — Periphery

- [README.md:118](../../../README.md#L118) — notes the keyed workflow.
- [story-verification-followups-plan.md](../story-verification-followups-plan.md) — the plan (`built`); Review Triage Log records the two workflow patches.
