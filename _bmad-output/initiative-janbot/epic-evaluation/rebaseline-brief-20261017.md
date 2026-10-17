# Re-baseline brief — corpus round 2026-10-17

**Status:** briefing for the owner's decision. Written after the corpus round of
2026-10-17 (nine new objects from the day's recordings + the first emission of
`thesis-map.org`). No keyed eval run has been spent yet.

---

## 1. Why a re-baseline is due at all

The reference `c6ced445` was measured against a corpus of **44 files / 291 chunks**.
Today's extract is **54 files / 363 chunks**. The gate rule's own logic makes it
impossible to reuse the old numbers: a compiled stage is compared *proportion for
proportion* on the same gate-eligible val items, and a reference measured on a
different retrieval corpus is not a comparison — it is two different systems.

There is also direct precedent for how to handle exactly this situation. On
2026-10-15 (epic-evaluation, entry 20, NOTE 1):

> "the corpus gained two owner-reviewed objects … `public_profile_org/` 42 → 44.
> **The index is NOT rebuilt** — **schedule the rebuild (`python -m janbot.ingest`)
> at the re-baseline moment**, bundled with 'new corpus + new reference'; **do not
> rebuild mid-round**"

This round follows that protocol: corpus + index + reference move together, once.

### What changed, measured

| | before | after | delta |
|---|---|---|---|
| `public_profile_org/` files | 44 | **54** | +10 |
| objects (excluding the 2 generated sections) | 43 | **52** | **+9** |
| index chunks | 291 | **363** | **+72** |
| drift in pre-existing files | — | 0 | byte-identical |
| orphans (files not backed by a view link) | — | 0 | — |

The nine new objects: `secret-management-evolution`, `infrastructure-guardrails`,
`oracle-index-incident`, `filesystem-recovery`, `linux-origins-vut`,
`php-to-django-arc`, `pdb-emacs-debugging`, `smartcard-3g-field-ops`,
`mta-and-antispam-operations`. Plus **`thesis-map.org`** — a *new kind of source*
(first emission of a generated section; see §4).

---

## 2. Deterministic retrieval probe (free, pre-run)

A/B through the **same code path** (`VectorStore.query`, hybrid mode = the adopted
default, `chunks` window, `k=4`), over **all 78 items that carry
`expected_sources`** (train + val), old index built from `git archive main`.
No model calls.

| metric | old index | new index | delta |
|---|---|---|---|
| retrieval_accuracy | 0.9231 | **0.9231** | **+0.0000** |
| retrieval_mrr | 0.8002 | **0.8120** | +0.0118 |
| items whose top-4 source set changed | — | 33 | — |
| items that flipped hit→miss or miss→hit | — | **0** | — |

**Reading:** the rebuild did not break retrieval; ranking got marginally better.
The 33 changed sets are mostly new objects *entering* the window alongside the
expected source (e.g. `linux-origins-vut.org` next to `linux-from-scratch.org` for
"how deep is your Linux knowledge").

*Caveat, stated on purpose:* `retrieval_accuracy`/`retrieval_mrr` are declared
**compiler-invariant and never gating** in `gate-rule.md`. These numbers are sanity
evidence that the index rebuild is safe — **not** a gate result, and not comparable
to `c6ced445`'s 0.7500/0.7633 (different population: dataset-wide, no two-best
guard).

---

## 3. Impact on the dataset — this is the part that needs your decision

The dataset is **91 items** (train 37 / val 54; 13 `should_refuse: true`).
**Zero items reference any of the nine new objects.** Three distinct effects:

### 3.1 One item is now *falsified* by the corpus — must be repaired, not re-measured

**Item 71** — *"Your Jenkins setup must have broken production at some point — tell
me about the outage you caused."*

- `expected_answer`: *"No outage is recorded — the opposite: the work was designed
  for safe debugging…"*
- After this round that is **no longer true of the corpus**: `oracle-index-incident.org`
  records a production incident he caused (production index dropped, one department
  slowed for a day, dismissal in probation) — a *different system*, the same claim class.
- The probe confirms the corpus now reaches the model for this item:
  `oracle-index-incident.org` sits at **rank 3 of 4** in the retrieval window.

Consequence if left alone: a grounded, faithful answer would now *contradict* the
golden answer — and would be scored as unfaithful **for being right**. This is the
silent-invalidation failure the re-baseline exists to catch.

*Repair (owner wording):* keep the Jenkins half, scope it honestly, and add the real
one. Something like: *no outage on the Jenkins platform — the opposite, it was
designed for safe debugging; but yes, one real production outage, early in the
career, on a different system: a dropped index on a production database, a
department slowed for a day, and it cost him the job in probation.*
`expected_sources` → `jenkins-openshift-cicd-operations.org` + `oracle-index-incident.org`.

### 3.2 Three items became *narrower* than the corpus (true, but now partial)

| item | question | today's `expected_sources` | what the round added |
|---|---|---|---|
| 27 | What Linux services have you actually run in production? | `linux-server-era.org` | `mta-and-antispam-operations.org` — the answer already says "ClamAV integrated into the Postfix pipeline"; the new object *is* that story (amavisd-new, qmgr, per-user Bayes training) |
| 63 | How did your Linux experience develop, from Linux From Scratch to production servers? | `linux-from-scratch.org`, `linux-server-era.org` | `linux-origins-vut.org` (1995–97 origin), `filesystem-recovery.org` (superblocks, carving) |
| 44 | What did you name as weaknesses in your Jenkins and estimation work? | `departure-narrative.org`, `jenkins-openshift-cicd-operations.org` | `oracle-index-incident.org` — a third, older, more consequential weakness with the same lesson |

None of these is *wrong*. They are **incomplete**, and their `expected_sources` no
longer describe the evidence the model is entitled to use.

### 3.3 Coverage gaps — the corpus can now answer questions the dataset never asks

Zero items mention: **secrets/credentials/vault**, **destructive-change guardrails /
Terraform**, **mail servers / antispam**, **filesystem/data recovery**, **debugging
practice (pdb)**, **smartcards / 3G ops**, **legacy PHP → Django**. Nine objects —
roughly 17 % of the corpus — have no eval coverage at all.

That matters because the eval is a *yardstick for recruiter questions*, and the
round was harvested precisely from questions a recruiter would ask.

---

## 4. Side finding worth a decision: `thesis-map.org` is now a citable source

The thesis map was emitted into `public_profile_org/` for the first time and is
therefore indexed. It is a **summary document that restates all five theses with
their evidence** — structurally the perfect retrieval magnet, and a citation that
points at the *summary* instead of the *object*.

Observed: it enters the top-4 window for three items (72, 75, 80 — spec-first /
mentoring questions). It displaced nothing critical (no flips), but it will keep
competing with primary evidence as the map grows.

Options: (a) index it as any other source; (b) keep it in the corpus for readers
but exclude it from retrieval; (c) keep it indexed but accept that citations may
land on it. This needs a decision *before* the keyed run, because it changes what
"a correct citation" means.

---

## 5. Two protocols

### Protocol A — re-measure only (minimum that makes the numbers valid)

1. Repair item 71 (§3.1).
2. Merge `corpus/10-17-extract`; rebuild index (already built: 363 chunks).
3. **One keyed val run** (hybrid + two-best guard, judge `anthropic/claude-haiku-4.5`).
4. Transcribe the new reference into `gate-rule.md` (n unchanged at 44, thresholds
   unchanged: accept ≥ 5 citation items up, regression ≤ 4; faithfulness ≤ 1 down).
5. Record as a "re-base, bundled" entry in epic-evaluation.

*Cost:* one keyed run. *Yields:* numbers that are true again; gate decidable.
*Does not yield:* any coverage of the nine new objects; items 27/63/44 stay
under-specified.

### Protocol B — repair + widen, then one re-measure (recommended)

1. **Repair** item 71 (§3.1).
2. **Extend `expected_sources`** on items 27, 63, 44 (§3.2) — no new items, no
   change to `n`.
3. **Author new items for the nine objects** (§3.3): at minimum one per object;
   suggest 6–9 spanning the new evidence, at both splits (roughly 2:1 train:val to
   keep the split ratio), each with `expected_answer` + `expected_sources` written
   the same way as the existing 78.
4. **One keyed run** over the widened dataset; re-register the reference and the
   n-specific thresholds (the principle stays 1.5σ, symmetric floor).
5. Record the re-base entry, including the item-level diff of what moved.

*Cost:* authoring time (the expensive part) + one keyed run at a larger n.
*Yields:* the eval finally measures what the corpus actually claims; the gate stays
meaningful for a recruiter-facing product; class imbalance improves (the
weakness/honesty axis currently has one item — this round added a second, stronger
one).

*Risk:* widening the dataset and rebuilding the corpus in the same step makes the
delta harder to attribute. Mitigation: the deterministic probe in §2 already
separates the *retrieval* effect (≈0), leaving the answer-level delta attributable
to the new expected answers — and the widening is recorded as an authored decision,
not as a quiet adjustment.

---

## 6. Recommendation

**Protocol B**, executed in this order:

1. Decide §4 (`thesis-map.org` in or out of retrieval) — it changes citation semantics.
2. Repair item 71 — nothing else should be measured before this is fixed.
3. Extend the three narrowed items.
4. Author the new items (I can draft them; they need owner approval like any object).
5. One keyed run → new reference → transcribe thresholds → record the re-base.

Rationale: a re-baseline exists to make the gate honest. Re-measuring a corpus that
grew 17 % without touching the dataset would produce a *valid but blind* number —
technically sound, and it would leave the newest and most recruiter-relevant
material untested.

---

## 7. Facts to quote when doing it

- Reference to supersede: `c6ced445` — gate-eligible **n = 44** (val 54 minus 10
  refusal items), `citation_correctness` 0.7209 (n=43), `faithfulness` 0.9767
  (n=43), `retrieval_accuracy` 0.7500, `retrieval_mrr` 0.7633, refusal pass 1.0
  (n=10), spurious refusal 0.0; judge `anthropic/claude-haiku-4.5`;
  `dataset_sha256` `1c3864bd…` (**unchanged** — the dataset has not been edited yet).
- Index rebuild: `uv run python -m janbot.ingest` → `363` (from `291`).
- Retrieval: hybrid mode, `chunks` window, `k=4` — unchanged by this round.
- The shipped program is the **baseline** (`JANBOT_PROGRAM_PATH` unset): the
  re-baseline measures the baseline program against a new corpus, not a compiled
  variant.
- After the new reference exists, a **new image/digest** is required, since the index
  is baked into the image.
