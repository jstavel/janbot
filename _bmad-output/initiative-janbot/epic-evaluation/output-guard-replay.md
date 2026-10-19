# Offline output-guard replay — runs A and B (2026-10-19)

**Status: PARTIAL — blocked by missing per-item artifact data.** No model call was made.

## What the recorded artifacts contain

- `run-e7110d58-output.txt` (A, `chunks`) and `run-f9ae28f2-output.txt` (B, `sources`) carry
  the CLI output: metrics, retrieval/citation misses, judge verdicts, declines, and an
  `answer:` line for every item that produced a response.
- They do **not** carry the per-item citation list the guard's D1 needs. The CLI prints the
  answer text only; the response `citations` are never written, and the MLflow run artifacts
  are only `golden_dataset.yaml` and `split_manifest.json`.
- Four acceptance items have **no answer text at all** in run B: 4, 74, 83, 97 all appear
  only as `failed: … FabricatedCitation`. Item 4 has no answer in either run. Item 19 has an
  answer in both.

Evidence (commands):

```sh
grep -E '^(answer|failed): (Have you implemented spec-first testing|You didn.t build that monitoring|What are the custom metrics|How do you handle credentials|Tell me about yourself)' \
  _bmad-output/initiative-janbot/epic-evaluation/run-e7110d58-output.txt
grep -E '^(answer|failed): (Have you implemented spec-first testing|You didn.t build that monitoring|What are the custom metrics|How do you handle credentials|Tell me about yourself)' \
  _bmad-output/initiative-janbot/epic-evaluation/run-f9ae28f2-output.txt
```

## What can be replayed, and how

The available answers can be replayed through **D2** by reconstructing the retrieved chunks
deterministically from the current index (same corpus, same window, k=4). For citations I
used **all retrieved sources** as a proxy, not the recorded citations:

- For every item that answered, the old program had already rejected any citation outside
  the retrieved set, so all recorded citations were valid; D1 would therefore be a no-op on
  those items by construction.
- For D2, using all retrieved chunks is a **superset** of the actual cited chunks. It can
  under-drop (ground a claim the actual cited subset would not), so the untouched count is
  an **upper bound**, not an exact replay.

| run | recorded answers | untouched | repaired | declined |
|---|---|---|---|---|
| A (`chunks`) | 56 | **55** | **1** (item 19) | 0 |
| B (`sources`) | 53 | **52** | **1** (item 19) | 0 |

### Item 19 — the one repair in both runs

**Before (A):**

> I am someone who values clarity through building and storytelling, using projects to clarify my narrative and facilitate thinking. **I have a strong foundation in programming languages like Python, Perl, Clojure, and TypeScript, and I focus on creating systems with verifiable outputs.** My professional philosophy is guided by foundational books that emphasize organization, growth mindset, deep work, purpose-driven action, team trust, ownership, knowledge management, and habit formation. I see my role in AI workflows as an architect, where I maintain direction and facilitate growth, both for myself and others.

**After:** the same answer with the bolded sentence removed; it stays **answered**. The
removed sentence is the over-claim the guard exists to catch. The answer retained its
grounded statements.

## The five acceptance items

| item | replay status |
|---|---|
| 4 | **Cannot replay** — no answer text in A or B (both `FabricatedCitation`). D1 is covered by unit tests; the fresh-run check is required. |
| 19 | **Replayed** — one sentence dropped, answer kept, stays answered. |
| 74 | A answered with valid citations (D1 no-op); B has no answer text. The B failure cannot be replayed offline. |
| 83 | A answered with valid citations (D1 no-op); B has no answer text. Cannot replay the B failure. |
| 97 | A answered with valid citations (D1 no-op); B has no answer text. Cannot replay the B failure. |

## What is missing for the full acceptance test

To replay D1 exactly, the eval run must persist, per item:

- the answer text,
- the cited labels,
- the retrieved sources,
- the retrieved context,
- and, on a guard refusal, the raw prediction that was refused.

The current runner discards per-item outcomes after aggregation. **Recommendation:** add that
per-item artifact to the eval runner (eval-protocol change, owner approval) and then run the
paid confirmation (T4). The unit tests already prove D1/D2/no-op/decline/fail-closed
mechanics; the five-item replay is the outstanding acceptance evidence.
