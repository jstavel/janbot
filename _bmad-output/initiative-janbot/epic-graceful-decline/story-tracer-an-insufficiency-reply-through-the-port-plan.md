---
title: 'Tracer: an insufficiency reply through the port'
type: 'feature'
ticket: 1
created: '2026-10-14'
status: done
baseline_revision: '423d64ada99853c947a13512c6e12fcdf011a04a'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** When the pipeline cannot ground a question — no in-scope corpus chunk — `POST /chat` answers `503`, an error rather than a graceful reply. The owner wants JanBot to say, in the contract, that it cannot answer from the public corpus.

**Approach:** add `status: "answered" | "insufficient"` to `ChatResponse` (citations required when `answered`, allowed empty when `insufficient`), and return the insufficiency reply at HTTP 200 for the no-grounding case; every normal answer carries `status="answered"`. The real detection refinement is entry 2.

## Boundaries & Constraints

**Always:** Pydantic stays the single contract source (AD-4) and the OpenAPI derives from it; genuine failures keep their 5xx envelope.

**Never:** no ingestion or store change; do not decline a fabricated *cited* answer.

**Decision (2026-10-14):** the decline shape is a `status` field; the decline returns HTTP 200. The decline covers `EmptyRetrieval` (no in-scope chunk) and the **no-sources-claimed** `UncitedAnswer`. A **fabricated cited answer** — the model naming a source outside the retrieved set — is **still refused with a 500** (the epic's Done-when 2), so the pipeline gains a distinct exception for it and the handler declines only the no-claim case. Entry 2 owns the fuller gate split and detection. The `answer` text is a fixed line: *"I don't have that in the public profile I answer from."*

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Grounded question | corpus has in-scope chunks | 200, `status="answered"`, ≥1 citation | No error |
| No in-scope context | empty/sourceless index (`EmptyRetrieval`) | 200, `status="insufficient"`, empty citations, the fixed line | No 503 |
| No sources claimed | model claims no sources (`UncitedAnswer`) | 200, `status="insufficient"`, empty citations, the fixed line | No 500 |
| Fabricated cited answer | model names a source outside the retrieved set | unchanged 500 `{detail}` refusal | Unchanged |
| Insufficient with citations | `status="insufficient"`, `citations=[…]` | rejected by the contract | Validation error |
| Genuine processing failure | model/store exception | unchanged 5xx `{detail}` | Unchanged |

</frozen-after-approval>

## Code Map

- `src/janbot/api/contract.py:43` — `ChatResponse`; add `status` and a model validator; relax `citations.min_length`.
- `src/janbot/pipeline/chat.py:133` — the no-sources-claimed `UncitedAnswer` (declines); `:141` — the unknown/out-of-set claim, which gains a **distinct exception** so it keeps a 500 refusal.
- `src/janbot/api/main.py:101` — declines `(EmptyRetrieval, UncitedAnswer)` at 200; the new out-of-set exception falls through to the 500 `{detail}` path.
- `src/janbot/api/contract.py:81` — the model validator rejects `answered` with empty citations; it must also reject `insufficient` **carrying** citations.
- `README.md` — the Chat and End-to-end prose still document the old `{answer, citations}` / 503 / 500 contract; it must follow the new shape.
- `tests/test_contract.py`, `tests/test_chat.py` — contract + port behavior.
- `tests/e2e/test_grounding_e2e.py:41` — the sourceless-index test asserts 503; it becomes a 200 insufficiency (a contract change made in Pydantic first, AD-7).

## Tasks & Acceptance

**Execution:**
- [ ] `src/janbot/api/contract.py` -- add `status`; allow empty citations; reject `answered` with empty citations **and** `insufficient` carrying citations -- the owner's decline shape in the single source.
- [ ] `src/janbot/pipeline/chat.py` -- raise a **distinct exception** for the unknown/out-of-set claim (kept a 500 refusal) while `UncitedAnswer` stays the no-sources-claimed decline signal.
- [ ] `src/janbot/api/main.py` -- on `EmptyRetrieval` and the no-claims `UncitedAnswer`, return a `ChatResponse(status="insufficient", citations=[], answer=<fixed line>)` at 200; the out-of-set exception stays a 500.
- [ ] `README.md` -- update the Chat and End-to-end contract prose to the new shape -- the documented contract must not contradict Pydantic.
- [ ] `tests/test_contract.py` -- insufficient-with-empty valid; answered-with-empty rejected (assert on the new message); insufficient-with-citations rejected -- pin the shape.
- [ ] `tests/test_chat.py`, `tests/e2e/test_grounding_e2e.py` -- a normal answer carries `status="answered"`; the sourceless and no-claims cases decline 200; the unknown-source-claim case stays a 500 refusal -- prove the port.

**Acceptance Criteria:**
- Given a question the corpus grounds, when posted, then the reply is 200 with `status="answered"` and at least one citation.
- Given no in-scope context, when posted, then the reply is 200 with `status="insufficient"` and empty citations.
- Given a model answer with no claimed sources, when posted, then the reply is 200 with `status="insufficient"` and empty citations.
- Given a model answer naming a source outside the retrieved set, when posted, then the reply is still refused with a 500 `{detail}`.
- Given `status="answered"` with no citations, or `status="insufficient"` carrying citations, when constructed, then the contract rejects it.
- Given the FastAPI app, when the OpenAPI is generated, then it derives the `status` field from Pydantic with no hand-written schema.

## Implementation Notes

## Plan Change Log

- 2026-10-14 (bad_plan loopback, review pass 1): the first plan declined a **fabricated cited answer** — it lumped every `UncitedAnswer`, contradicting the epic's Done-when 2 ("a fabricated cited answer is still refused"). Amended: the decline covers `EmptyRetrieval` and the no-sources-claimed `UncitedAnswer` only; the unknown/out-of-set claim gains a **distinct exception** kept as a 500 refusal. Also folded in: the contract must reject `insufficient` carrying citations; README's Chat/End-to-end prose must follow the new shape; the vacuous contract assertion tightened; the unused e2e helper removed. Reverted the first implementation and re-derived.
  - KEEP: the `status: answered|insufficient` shape and the `INSUFFICIENT_ANSWER` constant; the `answered`→non-empty-citations model validator; the 200 decline for `EmptyRetrieval` and no-claims; the OpenAPI derivation with no hand-written schema.

## Review Triage Log

Review pass 1 (quick, pinned) — 5 findings:
- a fabricated *cited* answer (out-of-set source) is declined instead of refused — **high / bad_plan** — contradicts the epic's Done-when 2; fixed by the loopback (distinct exception keeps the 500).
- README still documents the old `{answer, citations}` / 503 / 500 contract — **medium / bad_plan** — folded into the re-derivation (README updated).
- the contract does not reject `insufficient` carrying citations — **medium / bad_plan** — folded in (validator extended).
- a contract test's assertion is now vacuous — **low / patch** — tightened in the re-derivation.
- an e2e helper is left unused with a stale docstring — **low / patch** — removed in the re-derivation.

Review pass 2 (quick, after the re-derivation) — 3 findings, all patched:
- the reviewed diff omitted `pipeline/chat.py`, so as staged it declined a fabricated cited answer — **medium / patch** — a staging omission, not a code defect; `chat.py` restaged and the diff re-read.
- a contract test's name described a rule the contract no longer expresses — **low / patch** — renamed to `test_answered_response_without_citations_is_rejected`.
- `tests/e2e/test_determinism_e2e.py` docstring still showed the old `{answer, citations}` body — **low / patch** — updated to `{status, answer, citations}`.

## Verification

**Commands:**
- `uv run pytest -q tests/test_contract.py tests/test_chat.py tests/e2e/test_grounding_e2e.py` -- expected: green.
- `uv run python -c "import json,urllib.request; ..."` -- a sourceless service returns 200 `insufficient`.

**Manual checks (if no CLI):**
- Inspect the generated OpenAPI to confirm `status` appears without a hand-written schema.
