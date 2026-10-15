# Optimization gate rule (pre-registered)

Committed **before** the optimization stages run, so `5.14` (BootstrapFewShot,
multi-objective) and `5.9` (MIPROv2) are judged against a fixed rule rather than a
threshold chosen after seeing the numbers.

Reference: the val baseline **`9c7260da`** (n=15), judge `anthropic/claude-haiku-4.5`,
`dataset_sha256` as recorded in that run (a **reference-pointer update** from
`e635c2bf` — the `5.13` re-baseline; see the epic Notes; the rule body itself is
unchanged). A compiled stage is evaluated on the same
15 held-out val items and compared proportion-for-proportion.

## Metrics

- **Gate metrics: `citation_correctness` and `faithfulness`** — the multi-objective
  objective's two terms, both program-controlled (the compiler can move them).
- `retrieval_accuracy` and `retrieval_mrr` are **compiler-invariant** (data-level) —
  recorded for sanity, **never gating**.
- No other gate metric: at n=15 each extra guard compounds the false-reject risk.

## Target and threshold

- **Symmetric target:** either gate metric may carry the gain; **neither may regress
  beyond the floor**. A cross-floor trade — one up beyond the floor, the other down
  beyond it — is a **REJECT** (the Goodhart guard: faithfulness must not be bought
  with citations, nor the reverse).
- **Noise floor:** at n=15, p≈0.73, σ = √(p(1−p)/n) ≈ 0.11, so the threshold is
  **1.5σ ≈ 0.17**, expressed in **item terms** on n=15:
  - **Accept needs ≥ 3 items up** (3/15 = 0.20 > 0.17; +2 = 0.13 < 0.17).
  - **A regression is allowed up to 2 items down** (2/15 = 0.13 ≤ 0.17;
    **≥ 3 down = 0.20 fails**).

## Verdicts and policy

| Verdict | Condition | Action |
|---|---|---|
| **ACCEPT** | a gate metric rises beyond the floor and neither falls beyond it | adopt the compiled program; it becomes the reference for the next stage; `5.9` may proceed |
| **REJECT** | either gate metric falls beyond the floor | keep the baseline; do not adopt |
| **NO DECISION** | every change is within the floor | do **not** adopt; keep the current reference; do **not** escalate to the more expensive stage (an undecidable cheap stage cannot justify MIPROv2); record an **underpowered experiment** — dataset growth (breadth) is the precondition for the next attempt |

## Breadth gates optimization

Detecting a ~5% effect needs val ≈ 100 items; until then **"no decision" is the
honest expected outcome** of a stage, not a failure.

Threshold note on record: 2σ ≈ 0.23 ≈ 4 items would be off-spec — chosen after the
fact — and would weaken the pre-registration; 1.5σ is the value entry 18
pre-registered.
