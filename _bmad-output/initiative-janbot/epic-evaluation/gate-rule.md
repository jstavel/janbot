# Optimization gate rule (pre-registered)

Committed **before** the optimization stages run, so `5.14` (BootstrapFewShot,
multi-objective) and `5.9` (MIPROv2) are judged against a fixed rule rather than a
threshold chosen after seeing the numbers.

Reference: the val baseline **`4c0d848c8f924a3aa32ee220114c126f`** (status `FINISHED`),
re-registered 2026-10-18 after the corpus round 2026-10-17. Nominal gate-eligible
**n = 47** (val 57 minus the 10 `should_refuse`); for `citation_correctness` and
`faithfulness` the **observed n = 45**, because two items errored (`FabricatedCitation`)
and the metric contract excludes errored items. **Both n yield the same integer
thresholds** (derived below). Judge `anthropic/claude-haiku-4.5`; retrieval
`JANBOT_RETRIEVAL_MODE=hybrid` (the adopted default) with the `chunks` window,
`top_k=4` and the two-best relevance guard (θ = 0.26); `program=baseline`
(`JANBOT_PROGRAM_PATH` unset); `dataset_sha256` `78761c13…109d`. Split: train 43 /
val 57; `should_refuse` 13 (10 val). This reference supersedes `c6ced445` (91 items,
54 val, 44 gate-eligible, `dataset_sha256` `1c3864bd…`), which remains a valid
historical record but is not comparable across a corpus + index + dataset re-base.
**This is the RE-REGISTRATION transcription** — the reference moved with the breadth
work and now with the corpus round; the n-specific thresholds were re-instantiated at
the new baseline p (the principle — 1.5σ, symmetric floor — is unchanged; see the
epic Notes "PRE-REGISTERED metric re-registration", 2026-10-15). A compiled stage is
evaluated on the same gate-eligible held-out val items and compared
proportion-for-proportion.

## Metrics

- **Gate metrics: `citation_correctness` is the GAIN-CARRIER** (baseline **0.7111**,
  32/45 — room to move) and **`faithfulness` is the GUARD** (baseline **0.9778**,
  44/45 — at its ceiling: with one unfaithful item, the maximal gain is +1 item =
  0.0222, below its floor, so **faithfulness can never accept** — a gain must come
  from `citation_correctness`; faithfulness may only guard a regression).
- `retrieval_accuracy` (**0.7660**, n = 47) and `retrieval_mrr` (**0.7677**, n = 47)
  are **compiler-invariant** (data-level) — recorded for sanity, **never gating**.
- No other gate metric: at this n each extra guard compounds the false-reject risk.

## Target and threshold

- **Symmetric target:** either gate metric may carry the gain; **neither may regress
  beyond the floor**. A cross-floor trade — one up beyond the floor, the other down
  beyond it — is a **REJECT** (the Goodhart guard: faithfulness must not be bought
  with citations, nor the reverse).
- **Noise floor (re-derived at the new baseline p; arithmetic shown):** per-metric
  1.5σ = 1.5·√(p(1−p)/n) at the reference's own p.
  - **Gain-carrier `citation_correctness`** (p = 32/45 ≈ 0.7111):
    - nominal **n = 47**: σ = √(0.7111·0.2889/47) ≈ √0.004371 ≈ **0.0661**;
      1.5σ ≈ **0.0992** → **accept needs ≥ 5 items up** (5/47 = 0.1064 > 0.0992);
      **a regression is allowed up to 4 items down** (4/47 = 0.0851 ≤ 0.0992;
      ≥ 5 down = 0.1064 fails).
    - observed **n = 45**: σ = √(0.7111·0.2889/45) ≈ √0.004565 ≈ **0.0676**;
      1.5σ ≈ **0.1013** → **accept needs ≥ 5 items up** (5/45 = 0.1111 > 0.1013);
      **a regression is allowed up to 4 items down** (4/45 = 0.0889 ≤ 0.1013;
      ≥ 5 down = 0.1111 fails).
    - **Identical integers at both n: accept ≥ 5 items, regression ≤ 4 items.**
  - **Guard `faithfulness`** (p = 44/45 ≈ 0.9778):
    - nominal **n = 47**: σ = √(0.9778·0.0222/47) ≈ √0.000462 ≈ **0.0215**;
      1.5σ ≈ **0.0323** → the maximal gain (+1 item = 0.0213) is below it, so it
      **cannot accept**; **a regression is allowed up to 1 item down**
      (2 down = 0.0426 > 0.0323 fails).
    - observed **n = 45**: σ = √(0.9778·0.0222/45) ≈ √0.000483 ≈ **0.0220**;
      1.5σ ≈ **0.0330** → +1 item = 0.0222 is below it, so it **cannot accept**;
      **a regression is allowed up to 1 item down** (2 down = 0.0444 > 0.0330 fails).
    - **Identical integers at both n: cannot accept, regression ≤ 1 item.**

## Verdicts and policy

| Verdict | Condition | Action |
|---|---|---|
| **ACCEPT** | a gate metric rises beyond the floor and neither falls beyond it | adopt the compiled program; it becomes the reference for the next stage; `5.9` may proceed |
| **REJECT** | either gate metric falls beyond the floor | keep the baseline; do not adopt |
| **NO DECISION** | every change is within the floor | do **not** adopt; keep the current reference; do **not** escalate to the more expensive stage (an undecidable cheap stage cannot justify MIPROv2); record an **underpowered experiment** — dataset growth (breadth) is the precondition for the next attempt |

## Breadth gates optimization

Detecting a ~5% effect needs val ≈ 100 items; until then **"no decision" is the
honest expected outcome** of a stage, not a failure. **Breadth has arrived** (2026-10-15):
the val is now **57 items (47 gate-eligible)** across the ten-class failure taxonomy, and
the N confirmation on the previous 54-item val passed (citation-moved 9 under hybrid vs
the floor 5); that confirmation is carried forward as the breadth evidence — it was **not**
re-measured on the new val. The gate is now **decidable** for a lever that moves
`citation_correctness`.

Threshold note on record: 2σ would be off-spec — chosen after the fact — and would
weaken the pre-registration; 1.5σ is the value entry 18 pre-registered, re-instantiated
per-metric at the new n.

## Re-registration history

A re-registration moves the reference and re-derives its n-specific thresholds; it is
**not a verdict** and never changes the principle above.

- **2026-10-15** — `28c98a8d` → **`c6ced445`** (hybrid + the two-best guard adopted;
  91 items, 54 val, 44 gate-eligible).
- **2026-10-18** — **`c6ced445` → `4c0d848c8f924a3aa32ee220114c126f`** (corpus round
  2026-10-17: nine new objects, `thesis-map` moved out of the index, dataset 91 → 100
  with repaired/extended/new items; train 43 / val 57). No gate decision was made.

## Verdict record

Append-only; the rule above is frozen and never edited by a verdict.

- **2026-10-16 — entry 14 (multi-objective `BootstrapFewShot` compile), vs reference `c6ced445`: REJECT.** Compile `1bd62a51` (`fewshot:ef4f7404a591`, `w_c=w_f=0.5`, 4 demos); val run `707fbef3` (`dataset_sha256` `1c3864bd…`). `citation_correctness` 0.7209 (31/43) → 0.7273 (32/44); `faithfulness` 0.9767 (42/43) → 0.9091 (40/44). Item-level: citation +1/−0; faithfulness +1/−4 (**net −3**) — the guard fell beyond its ≤1-item floor. Keep the baseline; do not adopt; do not escalate to MIPROv2. Evidence: `epic-evaluation/run-707fbef3-output.txt`.
