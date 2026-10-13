# Walkthrough — PR #19: "run the port-only suite and prove a broken contract goes red (story 4.5)"

Target: PR https://github.com/jstavel/janbot/pull/19 · branch `e2e-4.5-ci` · commit `618b087`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the response fixture + self-test
- [x] Block 4 — Slice: the CI wiring
- [x] Block 5 — Periphery

## Status

All blocks accepted: 5 of 5. Review complete: PR #19 squash-merged (`e4b0f2e`), story 4.5 marked done; entry 4.6 unblocked.

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [story-ci-wiring-broken-contract-negative-plan.md](../epic-verification/story-ci-wiring-broken-contract-negative-plan.md).

> **Problem:** Done-when 4 has two halves: CI runs the endpoint suite green on every push, **and a deliberately broken contract turns it red**. The workflow already runs `uv run pytest -q` (which collects `tests/e2e`), but nothing demonstrates that a broken `/chat` contract is actually detected — the suite could pass vacuously.
>
> **Approach:** (a) make the port-only suite an explicit, named CI step; (b) add a committed **response fixture** (`tests/fixtures/chat_response.json`) and a keyless **self-test** that validates it through the Pydantic contract and rejects a malformed response; (c) add a CI job that **mutates the fixture**, runs the self-test, and is green only when the self-test goes **red** — proving the contract check is not vacuous.

## Block 2 — Broad strokes

A committed fixture, a keyless self-test, and a CI extension — no production code. Three spots:

- [tests/fixtures/chat_response.json](../../../tests/fixtures/chat_response.json) — the valid response fixture (the mutation target).
- [tests/test_response_contract.py:29](../../../tests/test_response_contract.py#L29) — the keyless self-test.
- [.github/workflows/ci.yml:41](../../../.github/workflows/ci.yml#L41) — the `contract-negative` job.

## Block 3 — Slice: the response fixture + self-test

The fixture is the exact JSON a caller receives. The self-test validates it through `ChatResponse` (so the wire shape is pinned) and asserts a parametrized malformed payload is rejected.

- [tests/fixtures/chat_response.json](../../../tests/fixtures/chat_response.json) — `{"answer", "citations":[{"source"}]}`.
- [test_response_contract.py:29](../../../tests/test_response_contract.py#L29) — `test_response_fixture_validates_unchanged`.
- [test_response_contract.py:46](../../../tests/test_response_contract.py#L46) — `test_malformed_response_is_rejected` (empty/missing/mistyped → `ValidationError`).

## Block 4 — Slice: the CI wiring

The `test` job now runs the unit/in-process suite and the port-only suite as named steps. The `contract-negative` job mutates the fixture to zero citations and inverts the exit code: it fails the job unless the self-test exits exactly `1`.

- [ci.yml:35](../../../.github/workflows/ci.yml#L35) — `Run unit and in-process tests` (`--ignore=tests/e2e`); [ci.yml:38](../../../.github/workflows/ci.yml#L38) — `Run port-only end-to-end tests`.
- [ci.yml:61](../../../.github/workflows/ci.yml#L61) — mutate the fixture (`uv run python`, `citations = []`); [ci.yml:73](../../../.github/workflows/ci.yml#L73) — require exit `1` on `test_response_fixture_validates_unchanged` (a collection error like `2`/`4`/`5` fails the job).

## Block 5 — Periphery

- [README.md:120](../../../README.md#L120) — notes the split CI steps and the `contract-negative` job.
- [story-ci-wiring-broken-contract-negative-plan.md](../epic-verification/story-ci-wiring-broken-contract-negative-plan.md) — the plan (`built`); its Review Triage Log records the exit-code and `uv run python` fixes.
