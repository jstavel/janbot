---
title: 'Citation ordering'
type: 'bugfix'
ticket: ''
created: '2026-10-13'
status: 'built'
baseline_revision: '46d33e9ab076dca8cb52f58532554331b11516a7'
route: 'oneshot'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** citations are built in LM-claim order — `citations = [Citation(source=s) for s in dict.fromkeys(normalized)]` (`src/janbot/pipeline/chat.py:137`), where `normalized` is the order the model emitted its claims. Two runs with identical answer text but permuted claims therefore produce different JSON bodies, a nondeterminism channel that undermines DW4 ("same query at the locked snapshot returns identical output across runs") and that the stub determinism tests cannot see (`tests/test_chat.py:229-249`). Recorded in the epic-rag-chat retrospective.

**Approach:** emit citations in **retrieval-`sources` order** — deduped, and filtered to the validated claim set — so that given identical retrieval the response is identical regardless of the model's claim order. The set of cited sources, the dedup rule, and the validation are unchanged.

## Boundaries & Constraints

**Always:**
- The cited *set* is exactly the validated claims; a claim outside the retrieved set is still rejected (fail-closed).
- One citation per distinct source (dedup preserved); retrieval order is the fixed order.
- The `ChatResponse`/`Citation` shape is unchanged; no new field.
- Preserve 3.2–3.8 pins; if a pin encodes claim order, it is re-expressed as retrieval order (the intent it should have pinned).

**Never:**
- No change to retrieval, `store/`, `ingest/`, `config.py`, `llm/`, or the contract models.
- No change to which sources are cited or to the uncited/unverifiable rejection.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | claims in retrieval order | citations in retrieval order | No error |
| EDGE | claims permuted vs retrieval order | citations still in retrieval order | No error |
| EDGE | duplicate claims | one citation per distinct source, retrieval order | No error |
| ERROR | a claim outside the retrieved set | rejected (unchanged) | 500 envelope |

</frozen-after-approval>

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (132 baseline + new ordering rows)

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: `src/janbot/pipeline/chat.py` — citations are now built by iterating `dict.fromkeys(sources)` (retrieval order, deduped) filtered to the validated claim set (`cited = set(normalized)`); docstring notes retrieval order. The cited set, dedup rule, and rejection logic are unchanged.
- Mutation-verified: reverting to the old claim-order expression fails the ordering test. `uv run pytest -q` → 134 passed.

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 2 medium / 1 low / 0 false / 0 maybe-false.** All routed to patch (test strength).
- **Duplicate-claims matrix row had no port proof** — **verdict: medium**. **route: patch** — added `test_chat_repeated_claim_yields_one_citation`.
- **Ordering test could not distinguish retrieval order from label sort order** (fixture rank coincided with alphabetical) — **verdict: medium**. **route: patch** — the test now uses a corpus where rank (`zulu.org`) ≠ sort (`alpha.org`).
- **Docstring promised two-run byte-identity but the test made one request** — **verdict: low**. **route: patch** — the test now builds two apps with reversed claims and asserts byte-identical bodies.

