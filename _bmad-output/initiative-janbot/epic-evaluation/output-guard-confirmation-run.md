# Output-guard confirmation run — T6 (2026-10-19)

**Run:** `c967e50ddaa64da38741907b83648a74` (FINISHED).
**Config:** `val`, 59 items; `chunks`, k=4, hybrid, θ=0.26, judge
`anthropic/claude-haiku-4.5`, `program=baseline`, **`output_guard=on`**,
`dataset_sha256` `a8bd69dc…`; index 417 chunks / 60 sources.
**Artifact:** `run-c967e50d-output.txt`.
**Outcome:** self-consistency **passes**; the five acceptance items behave as intended.
**Nothing is registered** on this first pass; ADR-010 remains **PROPOSED**.

## 1. Self-consistency (the central AC)

Method, as required:

1. For every val question, retrieval was **recomputed from the pinned index** with the
   run's config (`hybrid`, `chunks`, k=4) — no model call.
2. The recomputed source labels were compared **exactly** (order and duplicates) with the
   recorded `retrieved:` line.
3. The recorded `raw-answer` / `raw-citations` were replayed through the guard using the
   **recomputed chunk texts**, then compared with the recorded final answer and guard action.

Results:

| check | result |
|---|---|
| items with a recorded block | 59 / 59 |
| retrieval-label mismatches | **0** |
| raw answers replayed | 49 |
| pre-model declines (θ gate, no raw answer) | 10 |
| final-answer mismatches | **0** |
| guard-action mismatches | **0** |

The guard is deterministic in production: replaying raw → guard reproduces every recorded
final answer byte-identically.

## 2. Guard actions

| action | count |
|---|---|
| `none` | 44 |
| `repaired: D2` | 1 |
| `declined: D1` | 4 |
| pre-model decline (`<none>`) | 10 |

- The **one repair** is item 19.
- The **four D1 declines** are items 4, 23, 41, 63. In run A, items 4, 23 and 63 were
  `FabricatedCitation` **errors**, not answers; item 41 was already declined. **No
  previously-answering item became a decline.**
- The D1 declines share a cause: the model cited org-roam IDs (`20261007-…`) instead of the
  retrieved source labels. D1 drops them; with no valid label left, the reply declines. A
  citation-label normalizer (ID → source) would be a separate lever.

## 3. The five acceptance items

| item | guard | final result | acceptance |
|---|---|---|---|
| **4** — spec-first end to end | `declined: D1` | clean `insufficient` reply | **pass** (clean decline; no fabricated label emitted) |
| **19** — Tell me about yourself | `repaired: D2` | **answered**; technology clause removed; grounded clause kept | **pass** |
| **74** — monitoring stack copied? | `none` | answered; raw citations `insights-health-monitoring.org`, `departure-narrative.org` (both retrieved) | **pass** |
| **83** — custom metrics | `none` | answered; raw citation `insights-health-monitoring.org` (retrieved) | **pass** |
| **97** — credentials and secrets | `none` | answered; raw citations `secret-management-evolution.org` ×3 (retrieved) | **pass** |

**Item 19 final answer:**

> I am someone who values clarity through building and storytelling, using projects to
> clarify my narrative and facilitate thinking. **I focus on creating systems with
> verifiable outputs.** My professional philosophy is guided by foundational books that
> emphasize organization, growth mindset, deep work, purpose-driven action, team trust,
> ownership, knowledge management, and habit formation. I see my role in AI workflows as an
> architect, where I maintain direction and facilitate growth, both for myself and others.

The over-claim (“a strong foundation in … TypeScript”) is gone; the grounded clause survives;
the answer stays answered.

## 4. Guard metrics against A (`e7110d58`)

| metric | A (no guard) | T6 (guard on) |
|---|---|---|
| `answer_coverage` | 45/49 = 0.9184 | **45/49 = 0.9184** |
| `citation_correctness` | 31/45 = 0.6889 | **31/45 = 0.6889** |
| `citation_precision` | 0.6815 | **0.6815** |
| `faithfulness` | 43/45 = 0.9556 | **43/45 = 0.9556** |
| `retrieval_accuracy` | 34/49 = 0.6939 | **34/49 = 0.6939** |
| `retrieval_mrr` | 0.7415 | **0.7415** |
| `refusal_pass_rate` | 1.0 (n=10) | **1.0 (n=10)** |
| `spurious_refusal_rate` | 1/46 = 0.0217 | **4/49 = 0.0816** |

Reading: the guard leaves the four aggregate quality metrics and retrieval unchanged, because
the affected items were already excluded from the citation/faithfulness populations as
errors. Its visible cost is the **spurious-refusal** population: three items that were
unscoreable `FabricatedCitation` errors are now clean in-corpus declines (items 4, 23, 63),
and item 41 was already declined. The metric counts those clean declines, so `4/49` is a
**behavioural gain in contract compliance, not a new refusal of a previously answering item**.

## 5. Status

- Self-consistency: **passes**.
- Five acceptance items: **pass**.
- Guard metrics: citation/faithfulness flat; spurious-refusal population moves from
  errors to clean declines.
- **No reference is registered.** ADR-010 stays **PROPOSED** until the owner decides whether
  to promote it and how to treat the D1 decline cost (org-ID citation labels) in the next
  round.
