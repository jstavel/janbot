# Optimization gate rule (pre-registered)

Committed **before** the optimization stages run, so `5.14` (BootstrapFewShot,
multi-objective) and `5.9` (MIPROv2) are judged against a fixed rule rather than a
threshold chosen after seeing the numbers.

## Population contract (one contract, stated once)

Entry 22, owner decision **B** (2026-10-20). Every **claim-quality/gating**
metric has **one fixed population**; no such metric may compute a score over a
population that silently shrinks. A non-answered item is a failure, not an
exclusion.

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
  gating. **This is the explicit exception to the fixed-population rule:** a run
  with no retrieval claim has no retrieval result to score, so the item is out of
  scope. A hard error before retrieval therefore reduces the retrieval `n`; it is
  not scored as a retrieval miss.
- **Diagnostics beside the population** (not a second denominator):
  `hard_error__n`, `in_corpus_decline__n`, `judge_failure__n`, `non_answered__n`.
- **Out-of-corpus declines** are correct behaviour and stay with the refusal
  metrics; they are absent from the claim-quality populations.

Runs measured before this contract (including `4c0d848c`, `e7110d58`, `f9ae28f2`
and `5ed5d8d7`) are **incomparable** on absolute claim-quality values. Their
per-item evidence remains valid historical record.

## Reference

Reference: the val baseline **`e1a0fa4ef96f4f47b37dcea1e0bfba36`** (status
`FINISHED`), measured 2026-10-22 on the re-based instrument under the population
contract above. Nominal gate-eligible **n = 55** (val 69 minus the 14
`should_refuse`); every claim-quality metric aggregates over that same **n = 55**.
Config: `chunks` window, `top_k=4`, hybrid, θ = 0.26; judge
`anthropic/claude-haiku-4.5`; `program=baseline` (`JANBOT_PROGRAM_PATH` unset);
**`output_guard=on`** (ADR-010); `dataset_sha256`
`c4786e1c9e3f6f5c677b3ecbbee8fbc03ff19628b9bcf374aea958fc9cd9af20` (120 items;
train 51 / val 69); corpus `~/org` `339359e` (64 content files), index **440
chunks / 63 sources**; val `should_refuse` 14. Measured: `citation_correctness`
**0.6182** (34/55), `faithfulness` **0.8545** (47/55); context: `answer_coverage`
0.9636 (53/55), `citation_precision` 0.6348, `public_references` 0.9636,
`retrieval_accuracy` 0.6545, `retrieval_mrr` 0.7121, `refusal_pass_rate` 1.0
(n=14), `spurious_refusal_rate` 2/55. Diagnostics: `hard_error__n` = 0,
`in_corpus_decline__n` = 2, `judge_failure__n` = 0, `non_answered__n` = 2.
Artifact: `run-e1a0fa4e-output.txt`. The frozen floors for this reference are the
n = 55 pre-registration **below** (**citation accept ≥6 / regress ≤5; faithfulness
accept ≥4 / regress ≤3**). `156b5d1a` is **historical** (corpus `05b11a7`,
59-object extract, 417 chunks; dataset `a8bd69dc…`, 106 items; n = 49) and
`c6ced445` is older still (dataset `1c3864bd…`, 91 items, 44 gate-eligible,
~291 chunks). Their absolute claim-quality values are not comparable to this run. It is a **re-baseline, not a gate verdict**; the
principle (1.5σ, symmetric floor) is unchanged.

## Re-registration — 2026-10-22 (n = 55, thresholds frozen before the run)

The instrument moved under the reference, so the reference was measured on a new
instrument and its thresholds were frozen **before** that measurement:

- **Corpus re-extract at `339359e`** (`~/org`, view commit): 62 objects (the
  view's full selection) + `public-proof-map.org` + `thesis-map.md`; the three
  Czech objects (`growth-in-any-role`, `intent-based-delegation`,
  `style-references-as-intent`) enter as English translations with injected
  `:SOURCE-ID:`/`:SOURCE-SHA256:` pins. Extract committed at janbot `1aae1d8`;
  index rebuilt: **440 chunks / 63 sources**, identity `930e0a3d…`
  (`all-MiniLM-L6-v2@913d7300…`); `out_of_scope_sources` empty at startup.
- **Dataset `c4786e1c…`** (120 items; train 51 / val 69; val `should_refuse` 14
  → **gate-eligible n = 55**, verified against the dataset file).
- **Thresholds, derived at the outgoing reference's own p and projected to
  n = 55** (`156b5d1a` is the only honest pre-measurement p):
  - **Gain-carrier `citation_correctness`** (p = 33/49 = 0.6735):
    σ = √(0.6735·0.3265/55) ≈ 0.0632; 1.5σ ≈ 0.0948. 5/55 = 0.0909 is inside it;
    6/55 = 0.1091 exceeds it → **accept ≥ 6 items up; a regression is allowed up
    to 5 items down**.
  - **Guard `faithfulness`** (p = 45/49 = 0.9184): σ = √(0.9184·0.0816/55) ≈
    0.0369; 1.5σ ≈ 0.0554. 3/55 = 0.0545 is inside it — exactly the noise-carry
    the re-baseline warns about, which is why the frozen n=49 floor (≤2) must
    **not** be carried forward; 4/55 = 0.0727 exceeds it → **accept ≥ 4 items
    up; a regression is allowed up to 3 items down**.
- **Integer thresholds, frozen: citation accept ≥ 6 / regress ≤ 5; faithfulness
  accept ≥ 4 / regress ≤ 3.** The principle is untouched: 1.5σ per metric at the
  reference's own p, symmetric floor, one fixed population per claim-quality
  metric, judge failure = faithfulness failure. If the new reference's own p
  shifts materially from `156b5d1a`'s, that is recorded — these frozen floors
  still govern this round.
- **`156b5d1a` and `c6ced445` are historical from here on** — `156b5d1a` on
  dataset `a8bd69dc…` (106 items, n = 49) and 417 chunks; `c6ced445` on dataset
  `1c3864bd…` (91 items, n = 44) and ~291 chunks; neither is comparable to runs
  on this instrument.
- **Owner sign-off: given with the plan approval (2026-10-22), before the
  reference run.** The frozen threshold commit `7161460` predates the run; this
  sign-off line was committed with the registration, so the repository's commit
  time does not by itself prove the ordering — the threshold commit does.

## Metrics

*Historical derivation at `156b5d1a` (n = 49); the governing floors for the
current reference are the n = 55 pre-registration above.*

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
  `judge_failure__n` = 0, `non_answered__n` = 1. The one non-answer is item 41, and
  its vocabulary has three layers: the dataset says `should_refuse=false` (in-corpus);
  the API `reason` is `out_of_corpus`, produced by the deterministic
  `classify_decline_reason` text heuristic; the actual mechanism is an **uncited
  answer** (`raw-citations: <none>`), which the guard reports as `declined: uncited`.
  It is a failure in the claim-quality metrics.

## Target and threshold

*Historical derivation at `156b5d1a` (n = 49); the governing floors for the
current reference are the n = 55 pre-registration above.*

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
honest expected outcome** of a stage, not a failure. **Breadth has arrived**: as of
the 2026-10-22 re-baseline the val is **69 items (55 gate-eligible)** across the
ten-class failure taxonomy (it was 59/49 at the 2026-10-20 reference), and the N
confirmation on the earlier 54-item val passed (citation-moved 9 under hybrid vs
the floor 5); that confirmation is carried forward as the breadth evidence — it was
**not** re-measured on each new val. The gate is **decidable** for a lever that
moves `citation_correctness`.

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
- **2026-10-22** — **`156b5d1a…` → `e1a0fa4ef96f4f47b37dcea1e0bfba36`** (corpus
  re-extract at `~/org` `339359e`: 62 objects + 2 generated = 64 content files; three
  Czech objects enter as pinned English translations; index 440/63; dataset
  `c4786e1c…`, 120 items, train 51 / val 69, **n = 55**). Floors were frozen before
  the run from `156b5d1a`'s own p projected to n = 55: citation accept ≥6 / regress
  ≤5; faithfulness accept ≥4 / regress ≤3. Measured: citation 34/55 (0.6182),
  faithfulness 47/55 (0.8545), zero hard errors and zero judge failures. `156b5d1a`
  and `c6ced445` are historical from here on. This is a re-registration, not a verdict.

## Verdict record

Append-only; the rule above is frozen and never edited by a verdict. Verdicts recorded
before 2026-10-20 were measured under the old conditional population; their absolute
values are historical and incomparable under the contract above.

- **2026-10-16 — entry 14 (multi-objective `BootstrapFewShot` compile), vs reference `c6ced445`: REJECT.** Compile `1bd62a51` (`fewshot:ef4f7404a591`, `w_c=w_f=0.5`, 4 demos); val run `707fbef3` (`dataset_sha256` `1c3864bd…`). `citation_correctness` 0.7209 (31/43) → 0.7273 (32/44); `faithfulness` 0.9767 (42/43) → 0.9091 (40/44). Item-level: citation +1/−0; faithfulness +1/−4 (**net −3**) — the guard fell beyond its ≤1-item floor. Keep the baseline; do not adopt; do not escalate to MIPROv2. Evidence: `epic-evaluation/run-707fbef3-output.txt`.
