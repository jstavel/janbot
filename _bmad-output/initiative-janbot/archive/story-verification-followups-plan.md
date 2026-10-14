---
title: 'Verification follow-ups: keyed CI + e2e dedup'
type: 'chore'
ticket: ''
created: '2026-10-13'
status: 'done'
baseline_revision: '248d7f69cdf3d961783b92fa4f14b086a5c68f7f'
route: 'oneshot'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the `epic-verification` retrospective left two tracked items open. (1) The keyed e2e rows (4.1 happy path, 4.4 determinism) `skipif` without a key and CI runs keyless, so Done-when 1/3 are never machine-exercised — the F1 verification gap. (2) The e2e harness duplicates small things: the same `QUESTION`, the same 503 `{detail}` assertion, and the subprocess-RUN boilerplate in `conftest.py`.

**Approach:** (1) add a scheduled/manual **keyed** CI workflow that runs `tests/e2e` with `OPENROUTER_API_KEY` (skipping cleanly when the secret is unset); (2) extract a `tests/e2e/_support.py` with the shared `QUESTION`, key-env name and envelope assertion, and factor the duplicated subprocess-run boilerplate in `conftest.py`. No production code.

## Boundaries & Constraints

**Always:**
- Changes are confined to `tests/e2e/`, `.github/workflows/`, and README.
- The e2e test modules keep importing no `janbot` internals; the new `_support` module is `janbot`-free too.
- The keyless suite behaviour is unchanged: keyed rows still skip without a key, and no fixture index is built keylessly.
- The keyed CI workflow skips with a clear message (exit 0) when `OPENROUTER_API_KEY` is unset, so a repo without the secret stays green.

**Never:**
- No production-code change (`api/`, `pipeline/`, `store/`, `ingest/`, `config.py`).
- Do not modify the existing top-level `tests/*.py` files.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | keyless suite | identical to today (keyed rows skip, no fixture index built) | No error |
| HAPPY | keyed CI run, secret set | `tests/e2e` runs and passes through OpenRouter | No error |
| EDGE | keyed CI run, secret unset | the job prints a skip message and exits 0 | no red |

</frozen-after-approval>

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: added `.github/workflows/e2e-keyed.yml` (weekly + `workflow_dispatch`; runs `tests/e2e` with `OPENROUTER_API_KEY`, skips cleanly when the secret is unset). Extracted `tests/e2e/_support.py` (`QUESTION`, `MODEL_KEY_ENV`, `assert_detail_string`) and imported it from the e2e modules (verified `from e2e._support import …` resolves); factored the duplicated subprocess-run boilerplate into `conftest._run_cli`. README notes the keyed workflow.
- Verified: keyless (both keys unset) `uv run pytest -q` → 158 passed, 2 skipped; keyed via OpenRouter only `uv run pytest tests/e2e -q` → 8 passed; `.github/workflows/e2e-keyed.yml` parses.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 0 medium / 3 low / 0 false / 0 maybe-false.** Two patched, one rejected.
- **The keyed job could go green without exercising the keyed rows** — **verdict: low**. Verified: it gated on a raw `-z` test while the row gate and app treat a whitespace key as absent (`test_chat_e2e.py:25`, `test_determinism_e2e.py:51`, `api/main.py:76`), so a whitespace secret would proceed, skip both rows, and pass. **route: patch** — the job now gates on the trimmed key.
- **Nothing asserted the keyed rows actually ran** — **verdict: low** (same surface; separate root cause). A green job was indistinguishable from one that skipped. **route: patch** — the job now fails when pytest reports any `skipped`. Simulated: unset/whitespace → skip (exit 0); real key → 8 passed, no skip.
- **The plan artifact is outside the declared confinement** — **verdict: low**, **rejected**. `_bmad-output/…-plan.md` is the BMAD plan artifact (fix edits the plan); the confinement clause describes the code/doc surface.

## Verification

**Commands:**
- `env -u OPENAI_API_KEY -u OPENROUTER_API_KEY uv run pytest -q` -- expected: every test passes (keyed rows skip).
- `env -u OPENAI_API_KEY uv run pytest tests/e2e -q` -- expected: the keyed rows pass through OpenRouter.
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/e2e-keyed.yml')); print('yaml ok')"` -- expected: `yaml ok`.
