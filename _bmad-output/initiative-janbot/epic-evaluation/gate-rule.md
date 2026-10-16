# Optimization gate rule (pre-registered)

Committed **before** the optimization stages run, so `5.14` (BootstrapFewShot,
multi-objective) and `5.9` (MIPROv2) are judged against a fixed rule rather than a
threshold chosen after seeing the numbers.

Reference: the val baseline **`28c98a8d`** (gate-eligible **n = 44**; the breadth val,
54 items minus the 10 `should_refuse`), judge `anthropic/claude-haiku-4.5`,
`dataset_sha256` `1c3864bd…` as recorded in that run. **This is the RE-REGISTRATION
transcription** — the reference moved with the breadth work (corpus + index rebuilt,
dataset 91), and the n-specific thresholds were re-instantiated for the new n (the
principle — 1.5σ, symmetric floor — is unchanged; see the epic Notes "PRE-REGISTERED
metric re-registration", 2026-10-15). A compiled stage is evaluated on the same
44 gate-eligible held-out val items and compared proportion-for-proportion.

## Metrics

- **Gate metrics: `citation_correctness` is the GAIN-CARRIER** (baseline 0.5116 —
  room to move) and **`faithfulness` is the GUARD** (baseline 0.9767, 42/43 — at its
  ceiling: with one unfaithful item, the maximal gain is +1 = 0.023, below its floor,
  so **faithfulness can never accept** — a gain must come from `citation_correctness`;
  faithfulness may only guard a regression).
- `retrieval_accuracy` and `retrieval_mrr` are **compiler-invariant** (data-level) —
  recorded for sanity, **never gating**.
- No other gate metric: at n=15 each extra guard compounds the false-reject risk.

## Target and threshold

- **Symmetric target:** either gate metric may carry the gain; **neither may regress
  beyond the floor**. A cross-floor trade — one up beyond the floor, the other down
  beyond it — is a **REJECT** (the Goodhart guard: faithfulness must not be bought
  with citations, nor the reverse).
- **Noise floor (re-instantiated at the new gate-eligible n=44):** per-metric
  1.5σ = 1.5·√(p(1−p)/n) at the metric's baseline p:
  - **Gain-carrier `citation_correctness`** (p≈0.5116): σ ≈ 0.075, **1.5σ ≈ 0.113** →
    **accept needs ≥ 5 items up** (5/44 = 0.114 > 0.113); **a regression is allowed
    up to 4 items down** (4/44 = 0.091 ≤ 0.113; ≥ 5 down = 0.114 fails).
  - **Guard `faithfulness`** (p≈0.9767): σ ≈ 0.023, **1.5σ ≈ 0.034** → the maximal
    gain (+1 item = 0.023) is below it, so it **cannot accept**; **a regression is
    allowed up to 1 item down** (0.023 ≤ 0.034; ≥ 2 down = 0.045 fails).

## Verdicts and policy

| Verdict | Condition | Action |
|---|---|---|
| **ACCEPT** | a gate metric rises beyond the floor and neither falls beyond it | adopt the compiled program; it becomes the reference for the next stage; `5.9` may proceed |
| **REJECT** | either gate metric falls beyond the floor | keep the baseline; do not adopt |
| **NO DECISION** | every change is within the floor | do **not** adopt; keep the current reference; do **not** escalate to the more expensive stage (an undecidable cheap stage cannot justify MIPROv2); record an **underpowered experiment** — dataset growth (breadth) is the precondition for the next attempt |

## Breadth gates optimization

Detecting a ~5% effect needs val ≈ 100 items; until then **"no decision" is the
honest expected outcome** of a stage, not a failure. **Breadth has arrived** (2026-10-15):
the val is 54 items (44 gate-eligible) across the ten-class failure taxonomy, and the
N confirmation passed (citation-moved 9 under hybrid vs the floor 5) — the gate is now
**decidable** for a lever that moves `citation_correctness`.

Threshold note on record: 2σ would be off-spec — chosen after the fact — and would
weaken the pre-registration; 1.5σ is the value entry 18 pre-registered, re-instantiated
per-metric at the new n.
