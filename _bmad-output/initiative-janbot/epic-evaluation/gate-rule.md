# Optimization gate rule (pre-registered)

Committed **before** the optimization stages run, so `5.14` (BootstrapFewShot,
multi-objective) and `5.9` (MIPROv2) are judged against a fixed rule rather than a
threshold chosen after seeing the numbers.

## Population contract (one contract, stated once)

Entry 22, owner decision **B** (2026-10-20). Every metric has **one fixed
population**; no metric may compute a score over a population that silently
shrinks. A non-answered item is a failure, not an exclusion.

- **Claim-quality metrics** — `answer_coverage`, `citation_correctness`,
  `citation_precision`, `faithfulness`, `public_references`: population = every
  in-corpus (non-`should_refuse`) item; the citation metrics additionally require
  the item to name expected sources. A **hard error** or an **in-corpus decline**
  is a failure. A missing judge verdict is a `faithfulness` failure.
- **`refusal_pass_rate`**: population = every `should_refuse` item. A clean
  decline passes; an answer or a hard error fails.
- **`spurious_refusal_rate`**: population = every in-corpus item. A decline
  counts as a spurious refusal; a hard error is not a decline (it fails
  `answer_coverage`, not this metric).
- **`retrieval_accuracy` / `retrieval_mrr`**: unchanged, over items with expected
  sources and an observed retrieval claim (`retrieved_sources is not None`); never
  gating.
- **Diagnostics beside the population** (not a second denominator):
  `hard_error__n`, `in_corpus_decline__n`, `judge_failure__n`, `non_answered__n`.
- **Out-of-corpus declines** are correct behaviour and stay with the refusal
  metrics; they are absent from the claim-quality populations.

Runs measured before this contract (including `4c0d848c`, `e7110d58`, `f9ae28f2`
and `5ed5d8d7`) are **incomparable** on absolute claim-quality values. Their
per-item evidence remains valid historical record.

## Reference

Reference: the val baseline **`156b5d1a76694867bd92e7a03feda76b`** (status `FINISHED`),
registered 2026-10-20 under the population contract above. Nominal gate-eligible
**n = 49** (val 59 minus the 10 `should_refuse`); the claim-quality metrics now aggregate
over that same **n = 49** — the nominal/observed split is gone. Config: `chunks` window,
`top_k=4`, hybrid, θ = 0.26; judge `anthropic/claude-haiku-4.5`; `program=baseline`
(`JANBOT_PROGRAM_PATH` unset); **`output_guard=on`** (ADR-010); `dataset_sha256`
`a8bd69dc…`; corpus `05b11a7` (61 content files), index **417 chunks / 60 sources**;
train 47 / val 59; `should_refuse` 13 (10 val). This reference supersedes `5ed5d8d7`
under a **contract change**, not a corpus/index/dataset re-base: the per-item retrieval,
citation, judge, failure and decline lines are byte-identical to `5ed5d8d7`; only the
aggregates and populations changed. Gate comparisons are still evaluated on the common
items observed in both runs (brief §6.8, Amendment 2), as a second guard beside the fixed
population. It is a **re-baseline, not a gate verdict**; the principle (1.5σ, symmetric
floor) is unchanged.

## Metrics

- **Gate metrics: `citation_correctness` is the GAIN-CARRIER** (baseline **0.6735**,
  33/49 — room to move) and **`faithfulness` is the GUARD** (baseline **0.9184**,
  45/49). Four items are non-faithful (three `hallucinated` verdicts plus item 41's
  decline), so a gain of 3 items = 0.0612 exceeds the 0.0587 floor: **faithfulness can
  accept with ≥3 items up**, and may also guard a regression (≤2 down). A gain may come
  from either gate metric (symmetric target).
- `retrieval_accuracy` (**0.6939**, n = 49) and `retrieval_mrr` (**0.7415**, n = 49) are
  **compiler-invariant** (data-level) — recorded for sanity, **never gating**.
- Other non-gating context: `answer_coverage` 48/49, `citation_precision` 0.6769 (n=49),
  `public_references` 0.9796 (48/49), `refusal_pass_rate` 1.0 (n=10),
  `spurious_refusal_rate` 1/49.
- **Diagnostics at the reference:** `hard_error__n` = 0, `in_corpus_decline__n` = 1,
  `judge_failure__n` = 0, `non_answered__n` = 1. The one non-answer is item 41
  (`declined: uncited`); it is a failure in the claim-quality metrics.

## Target and threshold

- **Symmetric target:** either gate metric may carry the gain; **neither may regress
  beyond the floor**. A cross-floor trade — one up beyond the floor, the other down
  beyond it — is a **REJECT** (the Goodhart guard: faithfulness must not be bought
  with citations, nor the reverse).
- **Noise floor (re-derived at the reference's own p; arithmetic shown):** per-metric
  1.5σ = 1.5·√(p(1−p)/n) at the reference's own p, n = 49.
  - **Gain-carrier `citation_correctness`** (p = 33/49 = 0.6735):
    σ = √(0.6735·0.3265/49) ≈ √0.004487 ≈ **0.0670**;
    1.5σ ≈ **0.1005** → **accept needs ≥ 5 items up** (5/49 = 0.1020 > 0.1005);
    **a regression is allowed up to 4 items down** (4/49 = 0.0816 ≤ 0.1005;
    ≥ 5 down = 0.1020 fails).
  - **Guard `faithfulness`** (p = 45/49 = 0.9184):
    σ = √(0.9184·0.0816/49) ≈ √0.001529 ≈ **0.0391**;
    1.5σ ≈ **0.0587** → 2 items up = 0.0408 is below it; **3 items up = 0.0612 exceeds
    it** → **accept needs ≥ 3 items up**;
    **a regression is allowed up to 2 items down** (2/49 = 0.0408 ≤ 0.0587;
    3 down = 0.0612 fails).
  - **Integer thresholds: citation accept ≥ 5 items, regression ≤ 4 items; faithfulness
    accept ≥ 3 items, regression ≤ 2 items.** The citation floor is unchanged from the
    previous reference; the faithfulness floor is ≤2 here (it moved from ≤1 to ≤2 at
    `5ed5d8d7` because the baseline p fell). The 1.5σ principle is unchanged.

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
- **2026-10-20** — **`5ed5d8d7…` → `156b5d1a76694867bd92e7a03feda76b`** (population
  contract change, entry 22 decision B: one failure-inclusive population; hard errors and
  in-corpus declines are failures; diagnostics beside the population). Same corpus, index
  and dataset; the per-item evidence is byte-identical to `5ed5d8d7`. Every earlier run is
  incomparable on absolute claim-quality values. Floors: citation accept ≥5 / regress ≤4;
  faithfulness accept ≥3 / regress ≤2. This is a re-registration, not a verdict.

## Verdict record

Append-only; the rule above is frozen and never edited by a verdict. Verdicts recorded
before 2026-10-20 were measured under the old conditional population; their absolute
values are historical and incomparable under the contract above.

- **2026-10-16 — entry 14 (multi-objective `BootstrapFewShot` compile), vs reference `c6ced445`: REJECT.** Compile `1bd62a51` (`fewshot:ef4f7404a591`, `w_c=w_f=0.5`, 4 demos); val run `707fbef3` (`dataset_sha256` `1c3864bd…`). `citation_correctness` 0.7209 (31/43) → 0.7273 (32/44); `faithfulness` 0.9767 (42/43) → 0.9091 (40/44). Item-level: citation +1/−0; faithfulness +1/−4 (**net −3**) — the guard fell beyond its ≤1-item floor. Keep the baseline; do not adopt; do not escalate to MIPROv2. Evidence: `epic-evaluation/run-707fbef3-output.txt`.
