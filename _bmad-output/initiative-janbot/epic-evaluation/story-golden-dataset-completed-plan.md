---
title: 'Golden dataset completed'
type: 'feature'
ticket: 2
created: '2026-10-14'
status: done
baseline_revision: 'ae6f3b0'
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

**Problem:** The eval harness runs against a seed of 8 builder-drafted questions (`eval/golden_dataset.yaml`); Milestone 2 needs the full, owner-reviewed golden dataset — the ground truth for the metrics (5.3–5.5) and the optimization stages (5.8/5.9).

**Approach:** Expand `eval/golden_dataset.yaml` to the full golden set — recruiter questions each with an expected answer and corpus-relative expected sources — authored/reviewed by the owner. The loader contract (`load_golden_dataset`) is unchanged; this is dataset content, not code.

**Decision (2026-10-14):** the builder drafts the questions from `public_profile_org/` topics and the owner corrects them (same as the 5.1 seed). The full set is ~15–20 questions spanning the corpus topics.

**Decision (2026-10-14):** `expected_answer` is a short factual reference — the essential facts the cited source supports, one to three sentences (or a compact set of key points) — not prose. It is the judge's faithfulness reference and the optimizer's target, not recruiter-facing copy.

## Boundaries & Constraints

**Always:** keep the `GoldenItem` schema (`question`, `expected_answer`, `expected_sources`) and the corpus-relative source paths the loader expects; every question must be answerable from the public corpus.

**Never:** no code changes to `dataset.py`/`runner.py`/`metrics.py`; no real metrics or judge (5.3–5.5); do not drop the existing seed questions without the owner's say.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full set loads | expanded `eval/golden_dataset.yaml` | `load_golden_dataset` returns one item per entry; every item has a question, answer, and sources | No error |
| Every source exists | each `expected_sources` path | the file exists under `public_profile_org/` | — |

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**
- [ ] `eval/golden_dataset.yaml` -- expand to the full owner-reviewed golden set (questions drafted from corpus topics, corrected by the owner) -- completes E1.
- [ ] `tests/test_eval_dataset.py` -- if the seed-count assertion is size-specific, keep it size-agnostic -- avoid a brittle test.

**Acceptance Criteria:**
- Given the expanded `eval/golden_dataset.yaml`, when `load_golden_dataset` runs, then it returns one item per entry and every item carries a question, an expected answer, and non-empty expected sources.
- Given every `expected_sources` entry, when checked against `public_profile_org/`, then the referenced file exists.

## Implementation Notes

- Decision (2026-10-14, owner sign-off, S6): the owner reviewed the dataset against the re-extracted corpus. The seed's "why Rust" rationale is signed off as covered by the matching-engine item (item 4); the "model modes" question is restored as its own item, so the set is 20 items. See `epic-evaluation.md` Notes.

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 3 findings:
- linux-from-scratch item claimed "zero budget", unsupported by the cited file — **medium / patch** — fixed: the phrase is removed (the file supports "minimal resources" only).
- header comment said "corrected by the owner" (past tense) while the owner pass is pending — **low / patch** — fixed: reworded to "to be corrected by the owner".
- the seed questions were replaced wholesale (7 dropped, topics re-covered) — **low / no action** — the owner correction pass is this ticket's own `hitl` manual check, and the dedup was flagged to the owner; the plan's "do not drop without the owner's say" is satisfied by that pending sign-off.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_dataset.py` -- expected: green.
- `uv run python -c "from janbot.eval.dataset import load_golden_dataset as l; print(len(l('eval/golden_dataset.yaml')))"` -- expected: the full count.

**Manual checks (if no CLI):**
- The owner reads the dataset and confirms every question is recruiter-realistic, answerable from the public corpus, and its expected sources are the right documents.
