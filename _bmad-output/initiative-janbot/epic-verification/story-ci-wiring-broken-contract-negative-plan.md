---
title: 'CI wiring + broken-contract negative'
type: 'feature'
ticket: 5
created: '2026-10-13'
status: 'built'
baseline_revision: 'fc33f630abbe42b7fb32c7e0baac7a973150661a'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Done-when 4 has two halves: CI runs the endpoint suite green on every push, **and a deliberately broken contract turns it red**. The workflow already runs `uv run pytest -q` (which collects `tests/e2e`), but nothing demonstrates that a broken `/chat` contract is actually detected — the suite could pass vacuously.

**Approach:** (a) make the port-only suite an explicit, named CI step; (b) add a committed **response fixture** (`tests/fixtures/chat_response.json`) and a keyless **self-test** that validates it through the Pydantic contract and rejects a malformed response; (c) add a CI job that **mutates the fixture**, runs the self-test, and is green only when the self-test goes **red** — proving the contract check is not vacuous.

## Boundaries & Constraints

**Always:**
- Changes are confined to `tests/` and `.github/workflows/ci.yml`; **no `api/` change** (the epic boundary holds).
- The self-test is **keyless** and in-process: it imports the contract models (`janbot.api.contract`) and standard validation only — no service, no model.
- The negative CI job inverts the exit code: it succeeds only when the mutated fixture makes the self-test **fail**; a mutation that goes undetected fails the job.
- The existing unit/in-process suite keeps running; the port-only suite gets its own named step.

**Never:**
- No production-code change (`api/`, `pipeline/`, `store/`, `ingest/`, `config.py`).
- Do not modify the existing `tests/*.py` files.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | the committed response fixture | validates through `ChatResponse` unchanged | No error |
| ERROR | malformed response (empty `citations`, missing `answer`, mistyped field) | `ValidationError` from the contract | rejected at the contract |
| NEGATIVE (CI) | CI mutates the fixture (e.g. `citations = []`) | the self-test **fails**, so the job reports the break and exits green | job green only when the run goes red |

</frozen-after-approval>

## Code Map

- `tests/fixtures/chat_response.json` (new) — the valid response fixture: `{"answer": ..., "citations": [{"source": ...}]}`.
- `tests/test_response_contract.py` (new) — keyless self-test: the fixture validates through `ChatResponse`; a malformed response (parametrized: empty/missing/wrong-typed) raises `ValidationError`. Mirrors `tests/test_contract.py` (`ChatResponse.model_validate`, `min_length=1` on `citations`, `contract.py:43-50`).
- `.github/workflows/ci.yml` — split the `test` job's run into an explicit `tests` step (excluding e2e) and a named port-only `tests/e2e` step; add a `contract-negative` job that mutates the fixture and asserts the self-test fails.
- `README.md` — one line under "End-to-end tests": CI runs the port-only suite and a broken-contract job that must be red.
- Do not touch: `src/janbot/**`, existing `tests/*.py`.

## Tasks & Acceptance

**Execution:**
- [x] `tests/fixtures/chat_response.json` -- add the valid response fixture -- the mutation target and the contract pin.
- [x] `tests/test_response_contract.py` -- the keyless self-test (fixture validates; malformed rejected) -- the detection the CI job relies on.
- [x] `.github/workflows/ci.yml` -- explicit port-only e2e step + the `contract-negative` job (mutate → expect red) -- Done-when 4.
- [x] `README.md` -- note the CI wiring -- docs match behaviour.

**Acceptance Criteria:**
- Given a good push, when CI runs, then the unit/contract suite and the port-only `tests/e2e` suite both run and pass.
- Given the response fixture, when the self-test runs, then it validates unchanged and a malformed response is rejected with `ValidationError`.
- Given the fixture mutated to hold zero citations, when the self-test runs, then it fails (the CI job asserts this red).
- Given the whole suite keyless, when run locally, then every existing test passes.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- Added `tests/fixtures/chat_response.json`, `tests/test_response_contract.py`, split the CI `test` job into `--ignore=tests/e2e` + named `tests/e2e` steps, added the `contract-negative` job, and noted the wiring in `README.md`.
- Verified: self-test 5 passed on the pinned fixture; full suite 160 passed; local mutation (`citations = []`) made `test_response_contract.py` go red (1 failed, 4 passed); `yaml.safe_load` reports `yaml ok`.

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 1 medium / 3 low / 0 false / 0 maybe-false.** Two patched, two rejected.
- **`contract-negative` accepted any nonzero pytest exit as proof** — **verdict: medium**. Verified: the `if uv run pytest tests/test_response_contract.py` branch also accepts collection/usage/no-tests errors (exit 2/4/5), so deleting or renaming the self-test would leave the job green and Done-when 4 vacuous. **route: patch** — the step now targets `::test_response_fixture_validates_unchanged` and requires exit code exactly `1`; simulated locally: mutated fixture → `1` (job green), nonexistent node → `4` (job fails).
- **Mutation step ran bare `python`** — **verdict: low**. Verified: every other step runs through `uv`; `astral-sh/setup-uv@v10.2.0` + `uv python install` does not guarantee a `python` on `PATH`. **route: patch** — now `uv run python`.
- **`README.md` is outside the plan's "confined to `tests/` and the CI workflow" wording** — **verdict: low**, **rejected** (the only fix is plan/epic wording). The README line documents the change, matching sibling stories 4.1–4.4; "confined" was meant to exclude production code, not docs.
- **Execution checkboxes left unticked while the Implementation Notes claimed completion** — **verdict: low**, **rejected** (fix edits the plan). Boxes ticked as plan hygiene.

## Design Notes

- Why a committed fixture plus a mutation job: a self-test alone can pass vacuously; mutating the fixture and *requiring* red is an executable proof that the contract check detects a break (Done-when 4's second half). In-place mutation on the ephemeral CI runner is safe.
- Why the fixture is a plain `/chat` response body: it is the exact JSON a caller receives, so the self-test pins the wire shape (`ChatResponse`) rather than a Python object literal.
- Why split the CI run: a named port-only step makes Done-when 1/4 visible, and `--ignore=tests/e2e` avoids running the suite twice.

## Verification

**Commands:**
- `uv run pytest tests/test_response_contract.py -q` -- expected: the self-test passes on the committed fixture.
- `uv run pytest -q` -- expected: every existing test passes.
- Mutation proof: apply the CI mutation locally (`python -c` setting `citations = []`), run `uv run pytest tests/test_response_contract.py -q`, expect **failure**; then restore the fixture.
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"` -- expected: `yaml ok`.
