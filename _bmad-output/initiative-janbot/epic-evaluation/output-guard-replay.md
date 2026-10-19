# Offline output-guard replay — runs A and B (2026-10-19, updated after clause-level D2)

**Status: PARTIAL — the old artifacts still lack the seam's per-item data.** No model call
was made. The observation seam (`raw-answer:`, `raw-citations:`, `retrieved:`, `guard:`)
applies to runs made **after** it landed; it does not retroactively fix these artifacts.

## What the recorded artifacts contain

- `run-e7110d58-output.txt` (A, `chunks`) and `run-f9ae28f2-output.txt` (B, `sources`) carry
  the CLI output: metrics, retrieval/citation misses, judge verdicts, declines, and an
  `answer:` line for every item that produced a response.
- They do **not** carry the per-item citation list the guard's D1 needs. The CLI prints only
  the answer text; the response `citations` were never written, and the MLflow artifacts are
  only `golden_dataset.yaml` and `split_manifest.json`.
- Four acceptance items have **no answer text** in run B: 4, 74, 83, 97 all appear only as
  `failed: … FabricatedCitation`. Item 4 has no answer in either run. Item 19 has an answer
  in both.

## Replay method and evidence class

For each recorded answer, the retrieved chunks were recomputed deterministically from the
current index (same corpus, same window, k=4). Citations are **not** recorded, so the replay
uses **all retrieved sources** as a proxy:

- For every item that answered, the pre-guard program had already rejected any citation
  outside the retrieved set. Therefore **D1 is an exact no-op** for those items.
- For D2, using all retrieved chunks is a **superset** of the actual cited chunks. It can
  under-drop, so the untouched count is a **proxy upper bound**, not exact acceptance
  evidence.
- Item 19's dropped clause is ungrounded in every retrieved chunk (the marker “strong
  foundation” never co-occurs with TypeScript), so its repair is robust to the citation
  subset; the grounded clause has no marker and survives exactly.

| run | recorded answers | untouched (**proxy**) | repaired | declined | evidence class |
|---|---|---|---|---|---|
| A (`chunks`) | 56 | **55** | **1** (item 19) | 0 | answer text exact; D1 exact no-op; D2 input proxy |
| B (`sources`) | 53 | **52** | **1** (item 19) | 0 | answer text exact; D1 exact no-op; D2 input proxy |

## Item 19 — exact effect on the recorded text

**Before (A):**

> I am someone who values clarity through building and storytelling, using projects to clarify my narrative and facilitate thinking. **I have a strong foundation in programming languages like Python, Perl, Clojure, and TypeScript.** I focus on creating systems with verifiable outputs. My professional philosophy is guided by foundational books…

**After:** the technology clause is removed; the grounded clause **“I focus on creating
systems with verifiable outputs.”** survives; the answer stays **answered**. This is the
clause-level fix: the earlier sentence-level guard removed both.

## The five acceptance items

| item | replay status | evidence class |
|---|---|---|
| 4 | **Cannot replay** — no answer text in A or B (both `FabricatedCitation`). D1 is covered by unit tests. | unavailable |
| 19 | **Replayed** — over-claim clause dropped, grounded clause kept, stays answered. | answer exact; guard input proxy |
| 74 | A answered (D1 exact no-op); B has no answer text. The B failure cannot be replayed. | A exact for D1; B unavailable |
| 83 | A answered (D1 exact no-op); B has no answer text. The B failure cannot be replayed. | A exact for D1; B unavailable |
| 97 | A answered (D1 exact no-op); B has no answer text. The B failure cannot be replayed. | A exact for D1; B unavailable |

## What is still missing

The seam now records `raw-answer:`, `raw-citations:`, `retrieved:`, `guard:` per item, so a
**new** run can replay D1 exactly. The old artifacts cannot. The paid confirmation run (T6),
with the guard **on** and the seam recording, is the first run that can satisfy:

- self-consistency (raw → guard → final, byte-identical);
- the five acceptance items individually;
- guard metrics against A.

No proxy count above is presented as acceptance evidence.
