# Walkthrough — PR #18: "assert grounding determinism, not byte-identical bodies (story 4.4 follow-up)"

Target: PR https://github.com/jstavel/janbot/pull/18 · branch `e2e-4.4-determinism-fix` · commit `630dd78`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the grounding row
- [x] Block 4 — Slice: the upstream reconciliation
- [x] Block 5 — Periphery

## Status

All blocks accepted: 5 of 5. Review complete; wrap-up pending (merge PR #18).

## Block 1 — Intent

Source: from the plan's amended Intent + the post-merge fix note — [story-determinism-at-the-locked-snapshot-plan.md](../epic-verification/story-determinism-at-the-locked-snapshot-plan.md).

> **Problem:** story 4.4 asserted the two cache-cold `/chat` bodies were **byte-identical**, but the provider is not byte-stable at temperature 0 — `gpt-4o-mini` varied the answer wording on ~4 of 5 keyed runs (`…and evaluation before starting JanBot.` vs `…and evaluation.`), while the cited sources stayed identical. A row that fails on ordinary provider variance tests nothing stable.
>
> **Approach:** assert the property the service actually guarantees — **same-source grounding** (both `200`, well-formed `{answer, citations}`, identical corpus-relative citation sources), and reconcile the upstream spec/epic wording so nothing still claims byte-identity.

## Block 2 — Broad strokes

A test re-scope plus documentation reconciliation — no production code. Two spots:

- [tests/e2e/test_determinism_e2e.py](../../../tests/e2e/test_determinism_e2e.py) — the determinism row, now comparing citation sources.
- [spec-janbot.md:43](../spec-janbot/spec-janbot.md#L43) and [epic-verification.md:31](../epic-verification/epic-verification.md#L31) — the capability + Done-when being reconciled.

## Block 3 — Slice: the grounding row

`generate()` runs one cache-cold eval service and posts the question once. The row validates each body (`_assert_grounded_response`: non-empty answer, ≥1 citation, corpus-relative sources) and asserts the two runs cite the **same** sources. It deliberately does not compare answer text.

- [test_determinism_e2e.py:56](../../../tests/e2e/test_determinism_e2e.py#L56) — `test_two_cold_runs_ground_the_answer_in_the_same_sources`; [test_determinism_e2e.py:35](../../../tests/e2e/test_determinism_e2e.py#L35) — `_assert_grounded_response`.

## Block 4 — Slice: the upstream reconciliation

The re-scope is propagated so no artifact still claims byte-identity:

- [spec-janbot.md:43](../spec-janbot/spec-janbot.md#L43) — CAP-6 success now says "retrieves and cites the same corpus sources … the provider does not guarantee byte-identical answer text".
- [epic-verification.md:31](../epic-verification/epic-verification.md#L31) — Done-when 3 reworded; a decision note records the grounding-determinism scope.
- [tickets.toml](../epic-verification/tickets.toml) — entry 4's `description`/`verify` reworded; [deferred-work.md](../deferred-work.md) — the resolved note reworded off "byte-identical".

## Block 5 — Periphery

- [README.md:118](../../../README.md#L118) — "Grounding determinism … the two runs must ground the answer in the same corpus sources", with the provider caveat.
- [story-determinism-at-the-locked-snapshot-plan.md](../epic-verification/story-determinism-at-the-locked-snapshot-plan.md) — plan re-scoped (`built`); Plan Change Log + Review Triage Log record the fix, including a correction that citations are emitted in retrieval order (`pipeline/chat.py:147-152`).
