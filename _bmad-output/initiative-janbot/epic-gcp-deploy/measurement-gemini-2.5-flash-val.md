# Measurement — `google/gemini-2.5-flash` on the val golden split (vs the registered reference)

**Date:** 2026-10-22 · **Task:** demo-ux-under-guardrails (part 4) · **Type:** a
measurement producing a decision input — production routing is untouched, and
this note is not a diff.

## Comparison target — supersession recorded on purpose

**The comparison target is `156b5d1a`** — the registered current reference —
**per the owner's decision (2026-10-22), superseding the task file's
`c6ced445` pointer.** The task file named `c6ced445` from memory; that run is
the 2026-10-15 historical reference measured on the **old** corpus (291
chunks), the **old** dataset (`1c3864bd…`, 44 gate-eligible items). The run
below was produced on today's tree (corpus 417 chunks, dataset
`a8bd69dc…`, n=49), so it is comparable only to a reference measured on the
**identical corpus, index, dataset and judge** — which is `156b5d1a`
(`eval-a8bd69dc`, judge `anthropic/claude-haiku-4.5`).

**The supersession is a finding, not a slip to hide:** a stale pointer in a
task file is exactly the kind of drift this record exists to catch. And to be
explicit: **the gemini comparison below says nothing about the historical
`c6ced445` gate line** — the two runs differ in corpus, dataset and split, so
they are not a sequence and must not be read as one.

## Run

```sh
JANBOT_MODEL_SNAPSHOT=google/gemini-2.5-flash \
JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 \
uv run python -m janbot.eval --split val
```

- **Run id:** `effd4854d9b04bb9b3029184789443ef` (MLflow, `sqlite:///mlflow.db`,
  experiment `janbot-eval`).
- **Config:** model mode `eval`, snapshot `google/gemini-2.5-flash`, judge
  **pinned to the reference judge** `anthropic/claude-haiku-4.5` (changing the
  judge would invalidate faithfulness comparability), temperature 0.0, seed 0,
  top_k 4, retrieval hybrid/chunks, relevance threshold 0.26, output guard on,
  program baseline, dataset sha `a8bd69dc…` — identical to `156b5d1a`'s params
  in every field except `model_snapshot`.
- 59 val items: 49 non-refusal answered (1 declined in-corpus), 10 should-refuse
  declined pre-LM; 48/49 judged, 0 judge failures, 0 hard errors.

## The four metrics vs the reference (`156b5d1a`)

| metric | `156b5d1a` (gpt-4o-mini-2024-07-18) | `effd4854` (gemini-2.5-flash) | delta |
|---|---|---|---|
| faithfulness (n=49) | 0.9184 | **0.9184** | 0 |
| answer_coverage (n=49) | 0.9796 | **0.9796** | 0 |
| refusal_pass_rate (n=10) | 1.0000 | **1.0000** | 0 |
| spurious_refusal_rate (n=49) | 0.0204 | **0.0204** | 0 |

Side observation, recorded for completeness (not among the four compared
metrics, which the task's decision rule fixes): citation_correctness moved
0.6735 → 0.6327 and citation_precision 0.6769 → 0.6071 on the same 49 items —
the citation-noise concern the task file raised ("What is JanBot?" citing an
unrelated org file) shows up here, mildly. Retrieval metrics are identical
(same corpus/index/program).

## Conclusion

**No regression on any of the four compared metrics** — all four are identical
to the registered reference. Per the task's decision rule: **propose the
production change** (route `production` to `google/gemini-2.5-flash`). The
proposal is a decision input only: production's `openrouter/auto` routing is a
deliberate choice (AD-5), so flipping it needs its own ADR-level decision —
the citation-precision dip above belongs in that decision's inputs.
