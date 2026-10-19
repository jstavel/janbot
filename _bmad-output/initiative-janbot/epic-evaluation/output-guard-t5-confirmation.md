# T5 confirmation run — guard + normalizer (2026-10-19)

**Run:** `5ed5d8d73bb7400782503f8941a994f7` (FINISHED).
**Config:** `chunks`, k=4, hybrid, θ=0.26, judge `anthropic/claude-haiku-4.5`,
`program=baseline`, **`output_guard=on`**, `dataset_sha256` `a8bd69dc…`; index 417 chunks /
60 sources. Artifact: `run-5ed5d8d7-output.txt`.

## Pre-run prediction (recorded before this run)

- `spurious_refusal_rate` **1/49 = 0.0204**, item 41 only.
- The **45 common judged items** from T6 unchanged (verdict and answer).
- The three recovered items (4, 23, 63) newly judged, **with unknown verdicts** — the only new
  information this run buys.

## Result

### Self-consistency
- Retrieval recomputed from the pinned index for all 59 val questions; recorded `retrieved:`
  labels matched **59/59, 0 mismatches** (order and duplicates).
- **49** raw-answer items replayed through guard + normalizer; **0 final-answer mismatches**,
  **0 guard-action mismatches**.
- 10 personal items declined before the model by the θ gate and have no raw prediction.

### The 45 common judged items (T6 → T5)

| metric on the 45 common items | T6 | T5 |
|---|---|---|
| `citation_correctness` | 31/45 | **31/45** |
| `faithfulness` | 43/45 | **43/45** |
| verdict changes | — | **0** |
| answer-text changes | — | **0** |
| citation pass/fail changes | — | **0** |

The prediction of no change on the intersection is exact.

### Three newly judged items

| item | citation correctness | faithfulness | answer |
|---|---|---|---|
| **4** — spec-first end to end | **pass** | **faithful** | “Yes, I have implemented spec-first testing end to end. This is demonstrated through a TypeScript monorepo that records evidence from a live browser and verifies it offline against formal models, showcasing that spec-first testing has been executed at scale, not just discussed.” |
| **23** — inspectable projects | **pass** | **hallucinated** | The full project list (JanBot, Krakatoa, Reactive Testing, gtd-org, cdbazar, Clojure testing era, audio transcription, eDeposit, rhsm-cockpit-qe, NEPodpis) with GitHub/live links, and “Everything else has no public reference…” |
| **63** — Linux arc | **miss** | **faithful** | “My Linux experience developed significantly from building a custom Linux From Scratch distribution on a single 1.44MB floppy disk … Over time, I transitioned to compiling kernels and managing multiple desktops during my postgraduate years …” |

The three answers are newly generated text; the guard's alias normalizer resolved 2 / 1 / 2
labels respectively. Item 23's **hallucinated** verdict and item 63's **citation miss** are
new findings; they are not guard failures.

### Totals

| metric | T6 (45 judged) | T5 (48 judged) |
|---|---|---|
| `answer_coverage` | 45/49 | **48/49** |
| `citation_correctness` | 31/45 = 0.6889 | **33/48 = 0.6875** |
| `citation_precision` | 0.6815 | **0.6910** |
| `faithfulness` | 43/45 = 0.9556 | **45/48 = 0.9375** |
| `public_references` | 0.9796 (n=49) | **1.0000 (n=49)** |
| `retrieval_accuracy` / `mrr` | 34/49 / 0.7415 | **34/49 / 0.7415** |
| `refusal_pass_rate` | 1.0 (n=10) | **1.0 (n=10)** |
| `spurious_refusal_rate` | 4/49 = 0.0816 | **1/49 = 0.0204** |

### The five E2 acceptance items

- **4** — answered, citation pass, faithful. **Pass.**
- **19** — `repaired: D2`, answered, grounded clause kept, faithful. **Pass.**
- **74** — `none`, answered with retrieved citations, faithful. **Pass.**
- **83** — `none`, answered with retrieved citations, faithful. **Guard pass.** Its
  expected-source citation remains a **benchmark miss** (unchanged from T6); this is not a guard
  failure and not a stop condition.
- **97** — `none`, answered with retrieved citations, faithful. **Pass.**

### Guard actions

`none` 47 · `repaired: D2` 1 (item 19) · `declined: uncited` 1 (item 41) · pre-model 10.

### Stop conditions
- Any of the 45 common items changed verdict or answer: **none**.
- Any of the five acceptance items failed the guard criteria: **none**.
- `spurious_refusal_rate` not 1/49: **it is 1/49** (item 41 only).
- **No stop condition fired.**

## Status

Run C is the **reference candidate** (corpus + index + dataset + guard on + chunks). **Nothing
is registered on this first pass.** ADR-010 remains **PROPOSED**; promotion and reference
registration are the owner's decisions.
