# Optimization gate rule (pre-registered)

Committed **before** the optimization stages run, so `5.14` (BootstrapFewShot,
multi-objective) and `5.9` (MIPROv2) are judged against a fixed rule rather than a
threshold chosen after seeing the numbers.

Reference: the val baseline **`5ed5d8d73bb7400782503f8941a994f7`** (status `FINISHED`),
registered 2026-10-19 for the **shipped** configuration. Nominal gate-eligible **n = 49**
(val 59 minus the 10 `should_refuse`); for `citation_correctness` and `faithfulness` the
**observed n = 48**, because item 41 declined (`declined: uncited`) and the metric contract
excludes declined items. **Both n yield the same integer thresholds** (derived below).
Config: `chunks` window, `top_k=4`, hybrid, θ = 0.26; judge
`anthropic/claude-haiku-4.5`; `program=baseline` (`JANBOT_PROGRAM_PATH` unset);
**`output_guard=on`** (ADR-010); `dataset_sha256` `a8bd69dc…`; corpus `05b11a7`
(61 content files), index **417 chunks / 60 sources**; train 47 / val 59;
`should_refuse` 13 (10 val). This reference supersedes `4c0d848c…` (100 items, 57 val,
47 gate-eligible, `dataset_sha256` `78761c13…`), which remains a valid historical record
but is not comparable across a corpus + index + dataset re-base. **Judged population grew
45 → 48 because items 4, 23 and 63 now answer after alias normalization; raw counts are
therefore not comparable across runs. The comparison was made on the 45 common items,
where nothing changed (brief §6.8, Amendment 2).** This is a **re-baseline, not a gate
verdict**; the principle (1.5σ, symmetric floor) is unchanged.

## Metrics

- **Gate metrics: `citation_correctness` is the GAIN-CARRIER** (baseline **0.6875**,
  33/48 — room to move) and **`faithfulness` is the GUARD** (baseline **0.9375**,
  45/48). With three unfaithful items possible in the observed population, the maximal
  gain is +1 item = 0.0208, below the floor, so **faithfulness can never accept** — a gain
  must come from `citation_correctness`; faithfulness may only guard a regression.
- `retrieval_accuracy` (**0.6939**, n = 49) and `retrieval_mrr` (**0.7415**, n = 49) are
  **compiler-invariant** (data-level) — recorded for sanity, **never gating**.
- Other non-gating context: `answer_coverage` 48/49, `citation_precision` 0.6910 (n=48),
  `public_references` 1.0 (n=49), `refusal_pass_rate` 1.0 (n=10),
  `spurious_refusal_rate` 1/49.

## Target and threshold

- **Symmetric target:** either gate metric may carry the gain; **neither may regress
  beyond the floor**. A cross-floor trade — one up beyond the floor, the other down
  beyond it — is a **REJECT** (the Goodhart guard: faithfulness must not be bought
  with citations, nor the reverse).
- **Noise floor (re-derived at the new baseline p; arithmetic shown):** per-metric
  1.5σ = 1.5·√(p(1−p)/n) at the reference's own p.
  - **Gain-carrier `citation_correctness`** (p = 33/48 = 0.6875):
    - nominal **n = 49**: σ = √(0.6875·0.3125/49) ≈ √0.004385 ≈ **0.0662**;
      1.5σ ≈ **0.0993** → **accept needs ≥ 5 items up** (5/49 = 0.1020 > 0.0993);
      **a regression is allowed up to 4 items down** (4/49 = 0.0816 ≤ 0.0993;
      ≥ 5 down = 0.1020 fails).
    - observed **n = 48**: σ = √(0.6875·0.3125/48) ≈ √0.004476 ≈ **0.0669**;
      1.5σ ≈ **0.1004** → **accept needs ≥ 5 items up** (5/48 = 0.1042 > 0.1004);
      **a regression is allowed up to 4 items down** (4/48 = 0.0833 ≤ 0.1004;
      ≥ 5 down = 0.1042 fails).
    - **Identical integers at both n: accept ≥ 5 items, regression ≤ 4 items.**
  - **Guard `faithfulness`** (p = 45/48 = 0.9375):
    - nominal **n = 49**: σ = √(0.9375·0.0625/49) ≈ √0.001196 ≈ **0.0346**;
      1.5σ ≈ **0.0519** → +1 item = 0.0204 is below it, so it **cannot accept**;
      **a regression is allowed up to 2 items down** (2/49 = 0.0408 ≤ 0.0519;
      3 down = 0.0612 fails).
    - observed **n = 48**: σ = √(0.9375·0.0625/48) ≈ √0.001221 ≈ **0.0349**;
      1.5σ ≈ **0.0524** → +1 item = 0.0208 is below it, so it **cannot accept**;
      **a regression is allowed up to 2 items down** (2/48 = 0.0417 ≤ 0.0524;
      3 down = 0.0625 fails).
    - **Identical integers at both n: cannot accept, regression ≤ 2 items.** The guard
      floor moved from ≤1 to ≤2 because the baseline p is lower (0.9375 vs 0.9778); the
      principle—1.5σ, symmetric floor—is unchanged.

## Verdicts and policy

| Verdict | Condition | Action |
|---|---|---|
| **ACCEPT** | a gate metric rises beyond the floor and neither falls beyond it | adopt the compiled program; it becomes the reference for the next stage; `5.9` may proceed |
| **REJECT** | either gate metric falls beyond the floor | keep the baseline; do not adopt |
| **NO DECISION** | every change is within the floor | do **not** adopt; keep the current reference; do **not** escalate to the more expensive stage (an undecidable cheap stage cannot justify MIPROv2); record an **underpowered experiment** — dataset growth (breadth) is the precondition for the next attempt |

## Breadth gates optimization

Detecting a ~5% effect needs val ≈ 100 items; until then **"no decision" is the
honest expected outcome** of a stage, not a failure. **Breadth has arrived** (2026-10-15):
the val is now **59 items (49 gate-eligible)** across the ten-class failure taxonomy, and
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
- **2026-10-19** — **`4c0d848c8f924a3aa32ee220114c126f` → `5ed5d8d73bb7400782503f8941a994f7`**
  (ADR-010 guard adopted: `output_guard=on`, org-id alias normalization; corpus `05b11a7`,
  index 417/60, dataset `a8bd69dc…`, train 47 / val 59). The judged population grew 45 → 48
  because items 4/23/63 now answer; raw counts are not comparable — the 45 common items are
  unchanged (brief §6.8). This is a re-registration, not a verdict.

## Verdict record

Append-only; the rule above is frozen and never edited by a verdict.

- **2026-10-16 — entry 14 (multi-objective `BootstrapFewShot` compile), vs reference `c6ced445`: REJECT.** Compile `1bd62a51` (`fewshot:ef4f7404a591`, `w_c=w_f=0.5`, 4 demos); val run `707fbef3` (`dataset_sha256` `1c3864bd…`). `citation_correctness` 0.7209 (31/43) → 0.7273 (32/44); `faithfulness` 0.9767 (42/43) → 0.9091 (40/44). Item-level: citation +1/−0; faithfulness +1/−4 (**net −3**) — the guard fell beyond its ≤1-item floor. Keep the baseline; do not adopt; do not escalate to MIPROv2. Evidence: `epic-evaluation/run-707fbef3-output.txt`.
