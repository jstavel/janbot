# Walkthrough — PR #17: "determinism at the locked snapshot (story 4.4)"

Target: PR https://github.com/jstavel/janbot/pull/17 · branch `e2e-4.4-determinism` · commit `049ba0c`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the cache-cold seam
- [x] Block 4 — Slice: the determinism row
- [x] Block 5 — Periphery

## Status

All blocks accepted: 5 of 5. Review complete: PR #17 squash-merged (`7a76bc2`), story 4.4 marked done; entry 4.5 unblocked.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-determinism-at-the-locked-snapshot-plan.md](../epic-verification/story-determinism-at-the-locked-snapshot-plan.md).

> **Problem:** the in-process tests prove the eval LM is *built* with the pinned snapshot, temperature `0.0` and a seed (`tests/test_llm.py`, `tests/test_config.py`), but nothing proves the **running service generates** the same answer for the same question — the determinism CAP-7/Done-when 3 asks for is a property of the shipped HTTP path, not just the adapter. A naive "post twice and compare" cannot prove it: DSPy caches responses by default and the LM is built once per app, so the second identical POST is a **cache hit** and the bodies match even when generation is nondeterministic.
>
> **Approach:** start **two cache-cold service processes** (each with its own `DSPY_CACHEDIR`, exactly **one** POST each) under the locked eval snapshot at temperature `0`, seed `0`. Compare the two first-generation response bodies and assert they are **byte-identical**. Skipped cleanly without a model key.

## Block 2 — Broad strokes

A new keyed e2e module plus a fixture seam — no production code. Open these three spots:

- [tests/e2e/test_determinism_e2e.py](../../../tests/e2e/test_determinism_e2e.py) — the determinism row.
- [tests/e2e/conftest.py:289](../../../tests/e2e/conftest.py#L289) — the pinned `DETERMINISM_ENV` and the `cold_service` factory.
- [tests/e2e/conftest.py:144](../../../tests/e2e/conftest.py#L144) — the `extra_env` seam threaded through `_service_env`/`_serve`.

## Block 3 — Slice: the cache-cold seam

The row's validity rests on each run generating fresh, not reading a cache. `_service_env` now merges an `extra_env` mapping **last**, so it overrides ambient values; `cold_service` uses that to start a fresh eval service with the pinned config and a **unique `DSPY_CACHEDIR`** per call. Distinct cache roots plus a fresh subprocess (hence a fresh in-memory cache) make each run's single POST a cache miss.

- [conftest.py:144](../../../tests/e2e/conftest.py#L144) — `_service_env(index_path, extra_env)` merges the override last.
- [conftest.py:289](../../../tests/e2e/conftest.py#L289) — `DETERMINISM_ENV`: `eval`, temperature `0`, seed `0`, pinned snapshot.
- [conftest.py:298](../../../tests/e2e/conftest.py#L298) — `cold_service()` mints a per-run `DSPY_CACHEDIR` and starts the service.

## Block 4 — Slice: the determinism row

The row posts the same question once to each of two cold runs and compares the raw response bytes. Skipped cleanly when no model key is present.

- [test_determinism_e2e.py:34](../../../tests/e2e/test_determinism_e2e.py#L34) — `test_two_cold_runs_generate_byte_identical_bodies`: `first == second` on `response.content`, both `200`.

## Block 5 — Periphery

- [README.md:118](../../../README.md#L118) — one line noting the cache-cold determinism row.
- [story-determinism-at-the-locked-snapshot-plan.md](../epic-verification/story-determinism-at-the-locked-snapshot-plan.md) — the plan (`built`); its Review Triage Log and Plan Change Log record the oneshot→full replan (cache vacuity) and the final pass.
- [deferred-work.md](../deferred-work.md) — the stale "keyed double-run not performed" entry is marked **resolved** by this story.
