# Walkthrough — PR #11: "reject non-finite JANBOT_TEMPERATURE at config load"

Target: PR https://github.com/jstavel/janbot/pull/11 · branch `hardening-temperature-finite` · commit `4d773b9`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the finite check
- [x] Block 4 — Slice: the tests
- [x] Block 5 — Periphery

## Status

All blocks accepted: 5 of 5. Review complete: PR #11 squash-merged (`eab9b80`). Loose follow-up work (retro fix-now goal 4) — no ticket to flip.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [plan-temperature-finite-validation.md](../plan-temperature-finite-validation.md).

> **Problem:** `JANBOT_TEMPERATURE` is parsed with `float()` only, so `"nan"`, `"inf"`, and `"-inf"` are accepted as valid (verified). The value flows into the LM kwargs in *both* model modes, silently voiding the story-3.5 eval-determinism pin — the exact failure 3.5 exists to prevent — and can only fail at request time inside dspy/litellm, outside the `/chat` envelope mapping. Recorded in the epic-rag-chat retrospective.
>
> **Approach:** reject a non-finite temperature at config load with a `ValueError` naming `JANBOT_TEMPERATURE` (a `math.isfinite` check beside the existing parse), and document the finite requirement. Tests cover `nan`/`inf`/`-inf`.

## Block 2 — Broad strokes

One function in [src/janbot/config.py](../../../src/janbot/config.py) plus tests and a README row. Open these spots:

- [config.py:126](../../../src/janbot/config.py) — the finite check.
- [tests/test_config.py:194](../../../tests/test_config.py) — the non-finite test.
- [README.md](../../../README.md) — the documented "finite number" rule.

## Block 3 — Slice: the finite check

- [config.py:37](../../../src/janbot/config.py) — `import math`.
- [config.py:126](../../../src/janbot/config.py) — after `float()`, `if not math.isfinite(temperature): raise ValueError(...)` naming `JANBOT_TEMPERATURE`. Blank/unset still defaults to `0.0`; a finite value still parses; the "not a number" path is unchanged.

## Block 4 — Slice: the tests

- [test_config.py:194](../../../tests/test_config.py) — `test_non_finite_temperature_raises` covers `nan`/`inf`/`-inf`/`Infinity` and asserts the message names the variable and says "finite".
- [test_config.py:183](../../../tests/test_config.py) — the non-numeric rows now include `1.2x`.

## Block 5 — Periphery

- [config.py:20](../../../src/janbot/config.py) — the module docstring now says temperature must be a *finite* number.
- [README.md](../../../README.md) — the `JANBOT_TEMPERATURE` row says "not a finite number fails fast".
- [plan-temperature-finite-validation.md](../plan-temperature-finite-validation.md) — the plan (`built`); Triage Log records the two low fixes.
