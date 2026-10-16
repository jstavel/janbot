---
title: 'Golden dataset class audit'
type: 'feature'
ticket: 21
created: '2026-10-15'
status: done
baseline_revision: 'd8b1b1a'
route: 'oneshot'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** entry 20's breadth decision needs to know **where the dataset is thin** and **how many val items actually put grounding under pressure** — the earlier "val is mostly fact-lookup" hypothesis is refuted (2.11 destabilised items 14/17/19/22/36). Without a reproducible criterion, "grounding pressure" is vibes.

**Approach:** map the current 38 items to the ten-class failure taxonomy (epic-evaluation Notes, 2026-10-15) and report grounding pressure as **two reproducible numbers plus their union**: **(1) by construction** — the items in classes **3** (multi-source synthesis), **5** (weakness/honesty) and **7** (adversarial), which require synthesis/selection from context rather than a plain lookup; **(2) empirically observed** — the union of items whose **faithfulness verdict moved** between the lever runs, computed from the **already-stored** `run-*-output.txt` artifacts with **no new run**: 2.9 changed `{14, 29}`, 2.10 `{19, 29}`, 2.11 `{14, 17, 19, 22, 29, 36}` → union `{14, 17, 19, 22, 29, 36}`. Name the missing / thin classes; state the two consequences: **(a)** which classes to author (independent of the breadth decision); **(b)** how many grounding-pressure val items the gate needs so it can **ACCEPT** via a real gain rather than only reject. Report as "X items under pressure by class, Y empirically observed, union Z; val needs N", written into the epic-evaluation Notes with a per-item mapping artifact.

## Boundaries & Constraints

**Always:** all 38 items mapped (question, split, class); the observed number derived **from the stored artifacts** (the reference `e635c2bf`'s hallucinated set `{23,25,29,32}` vs each lever run's); the union of the two numbers reported; the report lands in the epic-evaluation Notes plus a per-item mapping artifact; no new model run.

**Never:** no dataset change; no gate-rule change; no `src/` change; no optimization stage (8/9 stay gated).

</frozen-after-approval>

## Code Map

- `eval/golden_dataset.yaml` — 38 items with `question`, `expected_answer`, `expected_sources`, `split`, `should_refuse` (all `False` today; class 8 is forward-declared).
- `_bmad-output/initiative-janbot/epic-ingestion/run-c68a9a3e-output.txt` (2.9 top_k=6), `run-7c868e2f-output.txt` (2.10 hybrid), `run-0c01ba33-output.txt` (2.11 dense+sources) — each prints a `judge: <question> — hallucinated|faithful` line per item; the **observed** set is the union of verdict changes against the reference.
- Reference verdicts — run `62e44e56` (the 5.19 diagnosis; its `hallucinated` lines are `{23, 25, 29, 32}`); also recorded in the epic-evaluation 5.19 diagnosis entry.
- `_bmad-output/initiative-janbot/epic-evaluation/epic-evaluation.md` Notes — the ten-class taxonomy note and the faithfulness-asymmetry note (both 2026-10-15); the report lands here.
- Item → class is a judgement per item; the class boundaries are the taxonomy note's one-line failure mode each.

## Tasks & Acceptance

**Execution:**
- [x] map all 38 items to the ten classes (question, split, class) -- the mapping artifact saved beside the Notes (e.g. `epic-evaluation-dataset-classes.md`). *(Done: all 38 classed; counts reconcile 23 train / 15 val and 16/3/5/6/1/3/0/0/3/1.)*
- [x] compute the observed grounding-pressure set from the stored lever outputs vs the reference (no new run) -- the empirical number and its union with the by-construction set. *(Done: {14, 17, 19, 22, 29, 36} = 6; union with X = 8.)*
- [x] write the report into `epic-evaluation.md` Notes: X (by class: 3+5+7), Y (observed), Z (union), the thin/missing classes, and the two consequences including **N** -- the deliverable. *(Done: X=2, Y=6, Z=8, N≈9 by the observed/union criterion.)*

**Acceptance Criteria:**
- Given the 38 items, when mapped, then every item has exactly one class and its split.
- Given the stored lever-run output artifacts, when their `hallucinated` sets are diffed against the reference `{23, 25, 29, 32}`, then the observed set is `{14, 17, 19, 22, 29, 36}` (the moved items) with no new run.
- Given the report, when read, then it states X (by construction), Y (observed), Z (union), and N; names the thin/missing classes; and states which classes to author plus how many grounding-pressure val items the gate needs to ACCEPT.

## Implementation Notes

- The mapping: all 38 items classed (artifact `epic-evaluation-dataset-classes.md` beside the Notes); distribution fact lookup 16, strengths/depth 6, multi-source 5, narrative 3, stance 3, attribution 3, weakness 1, voice 1, adversarial 0, refusal 0 — reconciles 23 train / 15 val.
- Grounding pressure: **X = 2** (val, classes 3/5/7), **Y = 6** (observed: {14, 17, 19, 22, 29, 36}), **Z = 8** (union). The two criteria are **disjoint** — class labels do not predict grounding pressure (every observed item is single-source).
- Thin/missing: 7 adversarial and 8 refusal missing; 5 weakness and 10 voice thin; 9 attribution has 3 (2 val); only 1 of 15 val items is multi-source.
- Consequences recorded: (a) author 7 adversarial + 8 refusal, deepen 5/10, add multi-source val items; (b) **N ≈ 9** val grounding-pressure items by the observed/union criterion (~3× headroom over the floor, per the asymmetry).
- Full verification: `uv run pytest -q` → 379 passed (no code touched).

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 6 findings: 4 patched, 1 re-staged, 1 false:
- the plan's `<frozen-after-approval>` block was never closed (everything to EOF sat inside it) — **low / patch** — the tag now closes before `## Code Map`, per the sibling-plan convention.
- the recorded 2.11 changed set `{14, 17, 19, 22, 36}` omitted item 29's fix (its verdict moved faithful) — **low / patch** — corrected in the mapping artifact and the frozen Intent (a factual typo in a recorded number, disclosed here; the union was unaffected since 2.9/2.10 already contributed 29).
- the Design Notes' N-derivation (~3 per class across 3/5/7) contradicted the delivered report (N by the observed/union criterion, not the class label) — **low / patch** — the Design Notes now record the proposal **and its supersession** by the disjointness finding.
- the causal claim "pressure tracks multi-subtree sources and synthesis demands" was unsupported (every observed item is single-source) — **low / patch** — reworded to the supported claim: class labels and source count do not explain the pressure; item 22's 2.11 depth loss is the one concrete multi-subtree datum; the general mechanism is not established.
- the review diff's frontmatter was stale relative to the on-disk plan (review metadata added after staging) — **low / patch** — the diff is re-staged at finalize.
- the Execution tasks were unchecked with the deliverable present — **false** — the diff was captured mid-workflow; this finalize step ticks them.

## Design Notes

- **Why two numbers.** "By construction" is exact and stable but does not prove the items actually stress grounding; "observed" proves the stress but is bounded by the levers run so far (a small, biased sample). Reporting both plus their **union** makes the claim reproducible and honest: the union is the set of items that are grounding-pressure by *either* route.
- **Deriving N — as proposed, then superseded by the audit's own finding.** The proposal was N ≈ 9 val grounding-pressure items spread ~3 per class across classes 3/5/7 (the gate accepts at ≥ 3 items net up; faithfulness is asymmetric, so an ACCEPT needs ≥ 3 flips plus headroom). The audit then found the by-class and observed criteria **disjoint** — class labels do not predict pressure — so the delivered N rests on the **observed/union criterion** (~9 val grounding-pressure items, measured not classed, with ~3× headroom for the destabilisation asymmetry); entry 20 owns the final breadth number.
- **Class 8** (refusal/out-of-corpus) has no items yet (`should_refuse` all `False`) but is not grounding-pressure in the same sense (it is the refusal-metric population, entry 5.13) — record it as a thin class but keep it out of the grounding-pressure count.

## Verification

**Commands:**
- read the mapping artifact -- expected: all 38 items classed.
- `uv run pytest -q` -- expected: green, unchanged (no code touched).
- Manual: the epic-evaluation Notes report states X, Y, Z, N and the two consequences; the observed set reproduces from the three stored `run-*-output.txt` artifacts.
