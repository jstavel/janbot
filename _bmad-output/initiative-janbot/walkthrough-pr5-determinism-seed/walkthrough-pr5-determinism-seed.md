# Walkthrough — PR #5: "pin eval determinism with a configured seed" (story 3.5)

Target: PR https://github.com/jstavel/janbot/pull/5 · branch `story-3.5-determinism-locked-snapshot` · commit `03c339b`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the seed becomes configuration
- [x] Block 4 — Slice: the seed applied at the LM seam
- [x] Block 5 — Slice: determinism proven at the port and seam
- [x] Block 6 — Periphery

## Status

All blocks accepted: 6 of 6. Review complete: PR #5 merged (`bb09613`), story 3.5 marked done.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-determinism-at-the-locked-snapshot-plan.md](../epic-rag-chat/story-determinism-at-the-locked-snapshot-plan.md).

> **Problem:** The eval/CI model mode is already selected by configuration (AD-5), but nothing pins *sampling reproducibility*: `build_lm` assembles only `model` + `temperature`, so eval determinism rests entirely on the provider's temperature-0 behavior, and no test proves that two runs of the same query at the locked snapshot return identical output. A mis-set `JANBOT_TEMPERATURE` silently breaks eval comparability — the exact failure ADR-004/AD-5 exist to prevent (CAP-6).
>
> **Approach:** Pin determinism at the LM seam and prove it at the port. Add a fixed, configuration-driven `seed` applied to the locked eval snapshot, keep the documented `temperature=0` default, then add tests that (a) the same question returns identical `/chat` output across runs and (b) switching to `openrouter/auto` is an environment-only change. Production (`openrouter/auto`) stays flexible and seed-free.

## Block 2 — Broad strokes

A new `JANBOT_SEED` config value is threaded into the LM only in `eval` mode, and tests prove the pipeline returns identical output across runs. Open these four spots in order:

- [src/janbot/config.py](../../../src/janbot/config.py) — the seed env var, default, `Config` field, and parsing.
- [src/janbot/llm/__init__.py](../../../src/janbot/llm/__init__.py) — where the seed is added to the LM kwargs for non-production modes.
- [tests/test_chat.py](../../../tests/test_chat.py) — the port-level determinism proofs.
- [README.md](../../../README.md) — the documented behaviour.

## Block 3 — Slice: the seed becomes configuration

`JANBOT_SEED` is parsed with the same trim/blank-as-unset and fail-fast rules as the other numeric variables, and stored on the frozen `Config`.

- [config.py:51](../../../src/janbot/config.py) — `SEED_ENV = "JANBOT_SEED"`; [config.py:59](../../../src/janbot/config.py) — `DEFAULT_SEED = 0`.
- [config.py:74](../../../src/janbot/config.py) — `seed: int` on `Config`.
- [config.py:125](../../../src/janbot/config.py) — parsing: blank/unset → default, non-integer → `ValueError` naming the variable.

## Block 4 — Slice: the seed applied at the LM seam

`build_lm` adds `seed` only when the mode is not production, so eval pins the snapshot and production stays open-router flexible.

- [llm/__init__.py:68](../../../src/janbot/llm/__init__.py) — `kwargs["seed"] = config.seed` for non-production; the production branch is untouched and stays seed-free.

## Block 5 — Slice: determinism proven at the port and seam

- [test_chat.py:229](../../../tests/test_chat.py) — same question twice to one app → byte-identical JSON.
- [test_chat.py:252](../../../tests/test_chat.py) — two identical-env apps → identical JSON and identical LM kwargs.
- [test_chat.py:216](../../../tests/test_chat.py) — eval kwargs carry the seed, production kwargs do not.
- [test_llm.py:83](../../../tests/test_llm.py) — the seam: configured seed reaches the LM; [test_llm.py:126](../../../tests/test_llm.py) — production stays seed-free.
- [test_config.py](../../../tests/test_config.py) — seed default, override, negative, blank, and invalid rows.

## Block 6 — Periphery

- [README.md:56](../../../README.md) — `JANBOT_SEED` table row; [README.md:69](../../../README.md) — model-mode paragraph, tightened during review so the pin reads as the documented default, not an unconditional guarantee.
- [story-determinism-at-the-locked-snapshot-plan.md](../epic-rag-chat/story-determinism-at-the-locked-snapshot-plan.md) — the plan, now `built`.
- [deferred-work.md](../deferred-work.md) — a stale-CHANGELOG carry recorded during review.
