---
title: 'Pre-registered optimization gate rule'
type: 'chore'
ticket: 18
created: '2026-10-15'
status: done
baseline_revision: '51a741f'
route: 'oneshot'
route_source: 'auto'
risk: 'medium'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the optimization stages (`5.14`, `5.9`) must be judged against a rule committed **before** the run, not a threshold invented after seeing the numbers — otherwise every result can be rationalized.

**Approach:** record a fixed **gate rule** against the val baseline `e635c2bf` (n=15), naming the metric(s), the acceptance threshold beyond the noise floor, and the "no decision" band; the stages are then evaluated against it. The rule lives as a versioned doc the entries cite.

## Boundaries & Constraints

**Always:** the rule is committed before `5.14` runs; the comparison is compiled-vs-`e635c2bf` on the same 15 held-out val items; a within-noise result is **"no decision"**, not a win or a loss.

**Never:** no code change here beyond recording the rule; no dataset change after the rule is committed (it would invalidate the reference); no retuning the rule after a result.

**Decision (2026-10-15, the rule):** as recorded below.

## The rule (pre-registered)

Metrics on the val split, compiled vs `e635c2bf` (n=15):

- **Gate metrics: `citation_correctness` and `faithfulness`** — the multi-objective objective's terms, both program-controlled. `retrieval_accuracy`/`retrieval_mrr` are **compiler-invariant** — recorded for sanity, never gating. **No other gate metrics** (each extra guard compounds false-reject risk at n=15).
- **Symmetric target:** either gate metric may carry the gain; **neither may regress beyond the floor**. A cross-floor trade (one up > floor, the other down > floor) is a **REJECT** — the Goodhart guard.
- **Noise floor & threshold:** at n=15, p≈0.73, σ = √(p(1−p)/n) ≈ 0.11, so the threshold is **1.5σ ≈ 0.17**. In **item terms** (n=15): **accept needs ≥ 3 items up** (3/15 = 0.20 > 0.17; +2 = 0.13 < 0.17); **a regression is allowed up to 2 items down** (2/15 = 0.13 ≤ 0.17; **≥ 3 down = 0.20 fails**).
- **Verdicts:** **accept** iff a gate metric rises beyond the floor and neither falls beyond it; **reject** iff either falls beyond it; **no decision** otherwise.
- **Policy:**
  - **ACCEPT** → adopt the compiled program; it becomes the reference for the next stage; `5.9` may proceed.
  - **REJECT** → keep the baseline; do not adopt.
  - **NO DECISION** → do **not** adopt the artifact; keep the current reference; do **not** escalate to the more expensive stage (an undecidable cheap stage cannot justify paying for MIPROv2); record it as an **underpowered experiment**, with dataset growth (breadth) as the precondition for the next attempt.
- **Breadth gates optimization:** detecting a ~5% effect needs val ≈ 100 items; until then "no decision" is the honest expected outcome.

(Threshold tradeoff on record: 2σ ≈ 0.23 ≈ 4 items would be off-spec — chosen after the fact — and would weaken the pre-registration; 1.5σ is the value entry 18 pre-registered.)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Improvement beyond the floor | compiled val run | gate metric(s) up > 0.17, none down > 0.17 → **accept** | No error |
| Regression beyond the floor | compiled val run | a gate metric down > 0.17 → **reject** | No error |
| Within the noise | compiled val run | all changes ≤ 0.17 → **no decision** | Recorded |

</frozen-after-approval>

## Code Map

- `_bmad-output/initiative-janbot/epic-evaluation/gate-rule.md` (new) — the rule, cited by entries 14/9 and the epic.
- `_bmad-output/initiative-janbot/epic-evaluation/epic-evaluation.md` — a dated decision recorded.

## Tasks & Acceptance

**Execution:**
- [ ] `_bmad-output/initiative-janbot/epic-evaluation/gate-rule.md` -- record the rule: metrics, noise floor, accept/reject/no-decision bands, and the reference run `e635c2bf` -- the pre-registered rule.
- [ ] `_bmad-output/initiative-janbot/epic-evaluation/epic-evaluation.md` -- a dated `Decision:` line citing the rule and the reference -- the record.

**Acceptance Criteria:**
- Given the gate rule file, when read, then it names the gate metrics, the threshold (> 1.5σ ≈ 0.17), the "no decision" band, and the reference run `e635c2bf`.
- Given the rule is committed before `5.14`, when `5.14`/`5.9` run, then each is judged against it with no post-hoc change.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Verification

**Commands:**
- `git log --oneline -- _bmad-output/initiative-janbot/epic-evaluation/gate-rule.md` -- the rule is committed before the `5.14` compile.
