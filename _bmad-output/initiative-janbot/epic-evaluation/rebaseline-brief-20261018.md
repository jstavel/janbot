# Re-baseline brief — corpus round 2026-10-18 (round 2)

**Status:** owner-approved **2026-10-19**. The extract, index and dataset change are applied
(commits `38e251a`, `9335eb6`, `3741fc9`, `ee38b18`). The keyed reference run was executed
on 2026-10-19 (`e7110d58`); the pre-registered triggers fired, so it was **not registered**
— see §5.7.

Source of truth: `~/org` (the corpus repository), pinned ref
**`05b11a78049190838069b5f5c6ad123ae420a104`**. The extract was taken from that pinned
ref, not from a moving HEAD.

---

## 1. What changed in the extract

| | before (`f49c8d3`) | after | delta |
|---|---|---|---|
| content files in `public_profile_org/` | 54 | **61** | **+7** |
| objects | 52 | **59** | **+7** |
| generated sections | 2 | 2 | 0 |
| `MANIFEST` | absent | present | +1 |

The seven new objects, copied byte-identically from the pinned ref:

- `knowledge-drift.org`
- `procedure-drift.org`
- `drift-closing-cadence.org`
- `substitutable-ai.org`
- `architect-not-coder.org`
- `api-key-rotation.org`
- `entering-an-unknown-system.org`

`thesis-map.md` was regenerated from `views/work-profile/index.org`: the 10-18 view adds
three evidence links (to `substitutable-ai`, `drift-closing-cadence`, and `procedure-drift`).
`public-proof-map.org` is byte-identical to `main`'s version.

`personal-intro.org` carries the owner's `<renegotiated>` TypeScript wording: *"Python and
Perl by hand, Clojure by heart, TypeScript with agents."* `architect-not-coder.org` carries
the owner's redaction of the interview details. `api-key-rotation.org` carries the
2026-10-19 reframing: the general parameter-consistency rule leads, the absolute spend
figures are gone (ratios only), and the store/validity/cap are recorded as in operation
while the rotator, monitoring and revocation playbook are not.

The diff against `main` is exactly **7 added object files + `MANIFEST` added +
`thesis-map.md` modified + `personal-intro.org` modified**; no other drift. `MANIFEST`
records the pinned corpus ref and `sha256` of every emitted file (61 entries; it does not
list itself), and recomputes identically.

## 2. Index rebuild

| | before | after |
|---|---|---|
| chunks | 357 | **417** |
| indexed `.org` sources | 53 | **60** |

The measured delta is **+60 chunks**, fully attributable to the seven new objects:

| object | chunks |
|---|---|
| `knowledge-drift.org` | 10 |
| `procedure-drift.org` | 9 |
| `drift-closing-cadence.org` | 7 |
| `substitutable-ai.org` | 8 |
| `architect-not-coder.org` | 8 |
| `api-key-rotation.org` | 9 (8 subtrees + the file-root chunk) |
| `entering-an-unknown-system.org` | 9 |
| **total** | **60** |

The estimate was approximately 415; the measured number is **417**. `thesis-map.md` remains
excluded by the `.org` whitelist; `MANIFEST` has no `.org` extension and is not indexed.

Startup scope cross-check: **0 out-of-scope chunks**; the foreign-index e2e test still
refuses to start. Retrieval smoke test: **7/7** top-4 windows contain the intended new
object. Note: the broad runbook phrasing now retrieves `entering-an-unknown-system` first;
the object-specific query retrieves `procedure-drift` in the top 4. That competition is a
finding, not a miss of the object.

## 3. Impact on the dataset

The dataset was 100 items (43 train / 57 val; 13 `should_refuse`; gate-eligible val 47).
**Zero existing items cite any of the seven new objects.**

### 3.1 Item 19 — contradiction resolved by the corpus

**Item 19 (0-based) — “Tell me about yourself.”** The pre-round intro claimed *“Professional
in … TypeScript”*, while `substitutable-ai.org` and `architect-not-coder.org` say TypeScript
is agent-assisted and not hand-written. The owner resolved it at the corpus level: the
personal intro was renegotiated to *“Python and Perl by hand, Clojure by heart, TypeScript
with agents.”*

**P1 Option B is approved and applied:** item 19's `expected_answer` now reads:

> Stories bring the power to know; success fuels the power to grow. Trust builds joy, and
> shared joy is twice the joy. Python and Perl by hand, Clojure by heart, TypeScript with
> agents. I build systems whose output can be verified, not merely demonstrated. I cherish
> the fleeting moments that remind me I am still growing.

The question, split, `expected_sources` and absent `should_refuse` are byte-identical.
The item now tests the honest TypeScript version instead of the over-claim.

### 3.2 N15 — corrected after the source object was reframed

N15 was drafted against the pre-reframe `api-key-rotation.org`. The owner's reframe replaced
key-specific properties and absolute figures with the general rule — **a control whose
parameters disagree becomes a scheduled failure** — and recorded the store, validity and cap
as in operation. The approved N15 text was therefore stale in both directions (it
under-claimed the deployed state and omitted the governing rule). It was rewritten before
application; the new text keeps the same question, source and `train` split.

The general lesson, recorded for future rounds: **a falsification scan is a point-in-time
check — after a correction lands, re-scan the pending texts derived from the old version,
not only the dataset.**

### 3.3 Items 17 and 97 — narrower, not false; untouched

- **Item 97 — “How do you handle credentials and secrets?”** The new `api-key-rotation.org`
  adds the parameter-consistency rule and the in-operation store/validity/cap. The existing
  answer remains true; it is incomplete on the new policy. `expected_sources` is
  deliberately **not** widened before the run — that would be tuning to an unmeasured
  outcome.
- **Item 17 — “How do you use AI in your day-to-day work?”** The new
  `architect-not-coder.org` sharpens “the architect role” into “architect and still able to
  implement.” The existing answer is not false; it is incomplete. Untouched.

### 3.4 Explicit scan result

- **Item 19:** contradiction found and resolved by the corpus renegotiation; P1 applied.
- **N15:** pending text found stale after the source reframe; corrected before application.
- **Items 17/97:** narrower but true; no edits.
- **No falsification or contradiction found in the other items.**

## 4. Approved change and next step

Owner approval **2026-10-19**: N10–N15, the **4 train / 2 val** split, **P1 Option B**, and
the N14 redaction. Dataset:

| | before | after |
|---|---|---|
| items | 100 | **106** |
| train | 43 | **47** |
| val | 57 | **59** |
| `should_refuse` | 13 | **13** |
| gate-eligible val | 47 | **49** |
| `dataset_sha256` | `78761c13…109d` | **`a8bd69dc10f0c9da5dc1b4d0c9639908c75323b7ced9671a0266a7d33ac11c90`** |

The keyed val run was executed on 2026-10-19 (`e7110d580277493b93f292f8bce3a67e`). The
pre-registered triggers fired, so the run was **not registered** — see §5.7 and the
investigation in `epic-evaluation.md`. The next step is the investigation, not a reference.

The proposals document
(`rebaseline-item-proposals-20261018-round2.md`) is the frozen contract for N10–N15 and P1.

---

## 5. Decision rule for the reference run — pre-registered

**Written 2026-10-19, before any metric from the run existed.** No number in this section
was chosen after seeing a result; the thresholds are derived from the floors already in
`gate-rule.md` rather than invented alongside this round.

### 5.1 What the run is, and what it is not

It registers **one reference** for the corpus/dataset state at `a8bd69dc…`, judged against
the previous reference `4c0d848c`. It is **not** a gate verdict: no lever is being accepted
or rejected, no optimisation stage is opened, and the baseline program still ships.

Registering a reference is still a decision, and this rule is what makes it checkable.

### 5.2 Pre-registered expectations — movement that has a named cause

| # | Expectation | Consequence if observed |
|---|---|---|
| E1 | Observed n may differ from the gate-eligible 49 (declines, missing observations) | acceptable **only** with a named cause; an unexplained change in n is a trigger |
| E2 | Item 19's answer text changes, because the intro it grounds on was rewritten | expected; verify the answer literally does not claim TypeScript expertise |
| E3 | Item 101 (`"Why does a runbook have to be run by hand?"`) may cite `entering-an-unknown-system` instead of `procedure-drift`, because the new onboarding object competes for that exact phrasing | **pre-registered as the expected single citation regression.** Recorded as a finding, not a defect, and not repaired in this round |
| E4 | Item 97 (`"How do you handle credentials and secrets?"`) may retrieve `api-key-rotation` alongside `secret-management-evolution` | expected; recorded, `expected_sources` **not** edited |

E3 and E4 were written from a smoke test that saw the competition before the run. Naming
them here is what stops them being discovered afterwards as an explanation.

### 5.3 Investigation triggers — do not register, investigate first

Any one of these blocks registration until it is understood:

1. **Faithfulness drops by ≥2 items.** The gate tolerance is a regression of ≤1; two items
   is beyond the floor that already exists, and cannot be attributed to a corpus round that
   changed six item texts and added six more.
2. **Any refusal metric leaves its floor** — `refusal_pass_rate` < 1.0 or
   `spurious_refusal_rate` > 0.0. Both were perfect at the previous reference; a change is a
   signal, not noise.
3. **`citation_correctness` drops by ≥5 items.** The gate's accept threshold is +5, so a
   loss of that size is the mirror image of a decided gain.
4. **A regression on an item that cites none of the seven new objects.** Such an item had no
   reason to move; movement means something other than this round changed.
5. **Observed n changes without a named cause** (see E1).

A movement that falls *inside* these bounds but has no explanation is not a trigger — it is
a finding to record. The rule separates "unexplained" from "unacceptable".

### 5.4 Outcome states

- **Register** — every movement is attributable to E1–E4 and no trigger fired.
- **Register with an open finding** — attributable, no trigger, but a named item needs
  follow-up (E3 is the likely one). The finding goes into `epic-evaluation.md` as an open
  item; the corpus decision to reduce the redundancy between `procedure-drift` and
  `entering-an-unknown-system` is a separate round.
- **Do not register** — any trigger fired. The reference is not created, the previous one
  stays in force, and the investigation is written up before anything else happens.

### 5.5 What is prohibited after the run

- editing `expected_sources` (or any item text) because the numbers came out a particular
  way;
- re-splitting, renumbering, or dropping an item to tidy a metric;
- re-running until a better number appears, or swapping the judge;
- attributing a movement to "the judge being harsh" without evidence from the captured
  per-item verdicts.

If this rule turns out to be insufficient — a case it does not cover — the amendment is
**appended** with its date and `old → new → why`, in the same way corpus objects are
renegotiated. It is never rewritten in place after the fact.

### 5.6 Status of the rule itself

Round-specific, and a candidate for the standing protocol: the pre-registration discipline
already exists for the *levers* (`gate-rule.md`), and this extends the same discipline to
the *reference*, which until now had no written decision rule at all.

### 5.7 Outcome (2026-10-19) — **DO NOT REGISTER**

Run **`e7110d580277493b93f292f8bce3a67e`** was executed under the pinned config (val, 59
items; nominal gate-eligible 49; observed n=45 for citation/faithfulness;
`dataset_sha256` `a8bd69dc…`; index 417 chunks / 60 sources). Metrics:
`answer_coverage` 0.9184 (45/49), `retrieval_accuracy` 0.6939 (n=49), `retrieval_mrr`
0.7415 (n=49), `citation_correctness` 0.6889 (31/45), `citation_precision` 0.6815 (n=45),
`faithfulness` 0.9556 (43/45), `public_references` 0.9796 (n=49), `refusal_pass_rate` 1.0
(n=10), `spurious_refusal_rate` 0.0217 (1/46).

**Two §5.3 triggers fired:** (2) the spurious refusal (item 41, “Why were you fired from
Red Hat?” declined `out_of_corpus`); (4) regressions on old items citing none of the seven
new objects — items 4, 41, 71, 83, 84, 32 and 87. Per §5.4 the reference is **not created**;
`4c0d848c` remains in force and `gate-rule.md` is untouched.

**Item 19 (E2):** judged faithful, but the answer still says *“I have a strong foundation in
programming languages like Python, Perl, Clojure, and TypeScript”* — it **still claims
TypeScript expertise**; the E2 verification fails. **Item 97 (E4):** retrieves
`secret-management-evolution` ×4; `api-key-rotation` does not displace it. **E3:** item 101
is a train item, so the val run cannot observe it.

Full per-item investigation: `epic-evaluation.md`.

---

## 5.8 Amendment 1 to the decision rule — trigger 4's rationale (appended 2026-10-19, after the run)

Appended under §5.5, not rewritten in place.

**old:** *"a regression on an item that cites none of the seven new objects — such an item had
no reason to move."*

**new:** *"a regression on an item that cites none of the seven new objects. Such an item can
still move, because hybrid retrieval fuses dense rank with BM25 whose IDF is collection-wide:
adding chunks changes the lexical statistics for every query. The trigger stays as written —
the reference must describe what the system does now — but the diagnosis changes: a movement
on an item whose **dense** rank is unchanged and whose **hybrid** rank moved is a
**measurement-fragility finding**, not a content regression."*

**why — the experiment.** The 357-chunk index of `4c0d848c` was rebuilt locally from the
extract at `053a5c9` (deterministic, no model call) and the four items that became new
retrieval misses were re-queried against both indexes:

| item | expected source | dense rank old → new | **hybrid** rank old → new |
|---|---|---|---|
| 41 *"Why were you fired…"* | `departure-narrative.org` | 7 → 7 (unchanged) | **2 → 6** |
| *"custom metrics in your monitoring stack"* | `departure-narrative.org` | 6 → 6 (unchanged) | **4 → 5** |
| *"Jenkins … tell me about the outage"* | `oracle-index-incident.org` | 5 → 5 (unchanged) | **4 → 6** |
| *"Python work is just glue scripts…"* | `audio-transcription-pipeline.org` | 6 → 7 | **3 → 5** |

Three of the four have an **identical dense rank** before and after. All four were inside
top-4 previously **only by lexical fusion** — they were never semantically in the window.
So the corpus round did not degrade embeddings; it withdrew a keyword advantage.

**Consequence for how references are compared.** `retrieval_accuracy` / `retrieval_mrr` are
**collection-size dependent** through BM25. The previous reference's `0.7660` was partly
lexical luck that a larger corpus cannot preserve. Cross-reference comparison of those two
metrics is therefore not apples-to-apples when the corpus grows. Two measures follow from
this, both cheap:

1. Record **dense-only** retrieval accuracy alongside the hybrid one at each reference, so a
   collection-independent number exists for comparing rounds.
2. Diagnose any future retrieval movement with the two-index method above (rebuild the
   previous extract locally, re-query, compare ranks) **before** attributing it to content.

**Also proven by the same experiment:** item 101 (train, so outside the val run) retrieves
`entering-an-unknown-system` at rank 1 and `procedure-drift` at rank 2 — pre-registered
hypothesis E3 confirmed at retrieval level, at zero cost. Item 97 retrieves
`secret-management-evolution` at rank 1 in both indexes; E4 not observed, as reported.

**Not yet established:** item 4's `FabricatedCitation` on an old-only window, and item 19's
over-claim despite `personal-intro.org` being retrieved at rank 2. Both point at the
generation side, not the corpus: item 19 is the known over-claiming class for which the owner
already required a deterministic output-level guard (ADR-009, E2), and the judge scored that
answer `faithful` — so the judge does not see paraphrase-level over-claim either. Two open
findings, no re-run proposed.

---

## 6. Run B — pre-registration for the retrieval-window lever

**Written 2026-10-19, before run B.** Owner decision: run the window lever alone; item 41
staying out of the window is accepted and is **not** a trigger for this run.

### 6.1 The lever, and what is held constant

| | |
|---|---|
| Lever | `JANBOT_RETRIEVAL_WINDOW`: `chunks` → **`sources`** |
| Held constant | `k = 4`, hybrid fusion, corpus (`05b11a7`, 61 content files), index (417 chunks), dataset (`a8bd69dc…`) |
| Compared against | run **A** = `e7110d58` (same corpus/dataset/k, `chunks`), *not* against `4c0d848c` |

`k` is deliberately **not** raised. `retrieval_accuracy` is monotone in `k` — a larger window
satisfies "all expected sources present" arithmetically — so changing `k` and the window
together would make the accuracy number uninterpretable. Holding `k` fixed keeps the
comparison valid, which is the whole reason this lever goes first.

### 6.2 Known in advance — the retrieval half is deterministic

Retrieval involves no model call, so these numbers are **measured, not predicted**
(hybrid, k=4, over the 49 val in-corpus items):

| | A (`chunks`) | B (`sources`) |
|---|---|---|
| `retrieval_accuracy` | 34/49 = 0.6939 | **38/49 = 0.7755** |
| items gained | — | **71, 75, 83, 84** |
| items lost | — | **none** |

Because retrieval is deterministic, **any** deviation from this table during run B means the
run did not execute the registered configuration — a hard stop, not a finding.

Item 41 (`"Why were you fired from Red Hat?"`) remains outside the window in both
configurations. Accepted by the owner; its spurious refusal is carried forward as a known,
open defect with its own future lever.

### 6.3 Predictions for the half that needs the model

| metric | A | prediction for B | mechanism |
|---|---|---|---|
| `citation_correctness` | 31/45 (0.6889) | flat to +2 items | four recovered items bring their expected source back into the window |
| `citation_precision` | 0.6815 | **flat to better** | `sources` de-duplicates the window: four distinct sources instead of up to four chunks from one — fewer same-source citations competing |
| `faithfulness` | 43/45 (0.9556) | flat | the recovered items were hallucinations-by-absence; grounding returns |
| `refusal_pass_rate` | 1.0 | 1.0 | unchanged items |
| `spurious_refusal_rate` | 1/46 (item 41) | **1/46, unchanged** | exempted by decision |
| `answer_coverage` | 45/49 | ≥ 45/49 | more windows contain a groundable source |

These are predictions written down before the numbers exist. A prediction that fails is a
finding about the *mechanism*, not a reason to re-interpret the result.

### 6.4 Judgment — accept or do not register

**Register B** only if all of the following hold against A:

1. `citation_correctness` regresses by **≤ 4 items** (the `gate-rule.md` regress floor);
2. `faithfulness` regresses by **≤ 1 item** (same floor);
3. `refusal_pass_rate` stays **1.0**;
4. `spurious_refusal_rate` stays **1/46** — no *new* spurious refusal beyond item 41;
5. observed `n` matches the previous denominators or changes with a named cause;
6. the retrieval side matches §6.2 exactly.

**Do not register** if any of the six fails. No override by re-reading the numbers; an owner
override is possible but must be written down *as an override with its reason*, never as
"the run passed".

### 6.5 If B is accepted — a consequence that must not be skipped

A reference must describe **what ships**. The shipped default is
`JANBOT_RETRIEVAL_WINDOW=chunks`; registering a reference measured with `sources` while the
default stays `chunks` would make the reference fiction. So acceptance implies, in the same
round:

- an **ADR** recording the window change (`/chat` contract and answer shape unchanged — only
  which chunks reach the prompt), with the §6.2/§6.3 evidence attached;
- flipping the config default to `sources`;
- re-recording the reference so its configuration matches the shipped default.

### 6.6 Prohibitions after run B

As §5.5: no `expected_sources` edits, no re-split, no re-run for a better number, no judge
swap, no post-hoc redefinition of what "register" means. Any insufficiency of this
pre-registration is appended (date, `old → new → why`), never edited in place.

---

## 6.7 Run B outcome (2026-10-19) — **NOT REGISTERED**

Run **`f9ae28f24b2643fdaefeff50f819865b`** (FINISHED), pinned config except
`JANBOT_RETRIEVAL_WINDOW=sources`, `k=4`, hybrid, θ=0.26, judge `claude-haiku-4.5`,
`program=baseline`, `dataset_sha256` `a8bd69dc…`, index 417 chunks / 60 sources.
Captured output: `run-f9ae28f2-output.txt`.

| metric | A (`chunks`, `e7110d58`) | B (`sources`, `f9ae28f2`) |
|---|---|---|
| `retrieval_accuracy` | 34/49 = 0.6939 | **38/49 = 0.7755** |
| `retrieval_mrr` | 0.7415 | **0.7619** |
| `answer_coverage` | 45/49 = 0.9184 | **42/49 = 0.8571** |
| `citation_correctness` | 31/45 = 0.6889 | **30/42 = 0.7143** |
| `citation_precision` | 0.6815 | **0.7262** |
| `faithfulness` | 43/45 = 0.9556 | **40/42 = 0.9524** |
| `refusal_pass_rate` | 1.0 (n=10) | **1.0** (n=10) |
| `spurious_refusal_rate` | 1/46 = 0.0217 | **1/43 = 0.0233** |

**T1 was reproduced exactly before spending:** `chunks` 34/49, `sources` 38/49, gained
**71, 75, 83, 84**, lost **none**. The run's retrieval side matches that table exactly.

### Which criterion failed

**Criterion 2 — faithfulness regressed by more than one item on the pre-registered item
count: 43 passes (A) → 40 passes (B), −3.** The rate is nearly flat (0.9556 → 0.9524) and
on the 42 items observed in both runs it is **40/42 vs 40/42**; the three missing passes
are items that **left the observed population** as new `FabricatedCitation` errors. That is
the named cause for the n change (criterion 5), but it is also a real quality regression:
`answer_coverage` fell **45/49 → 42/49** and the §6.3 prediction `≥ 45/49` is falsified.
Per §6.4 and the “no post-hoc redefinition” rule, B is **not registered**.

The other criteria: (1) citation passes 31→30, −1 ≤ 4 — holds (on the common 42 items it is
29→30, +1); (3) refusal pass 1.0 — holds; (4) the spurious-refusal **count** is still 1
(item 41) but the denominator changed 46→43 — no new spurious refusal, denominator change
named by the three new errors; (5) n 45→42 with the named cause above; (6) retrieval
matches §6.2 exactly.

### Item-level deltas (attribution)

- **Item 71** — retrieval gained `oracle-index-incident.org` (rank 3 under `sources`), but
  the citation still misses it; the answer remains the orphaned-pods story. Prediction
  “recovers its expected citation” **falsified**.
- **Item 75** — retrieval gained `departure-narrative.org` (rank 3), but the citation still
  misses it. **Falsified.**
- **Item 83** — retrieval gained `departure-narrative.org` (rank 3), but the item now errors
  `FabricatedCitation`; it is worse than A. **Falsified.**
- **Item 84** — retrieval gained `audio-transcription-pipeline.org` (rank 4) and the
  citation now passes. **Confirmed.**
- **Item 41** — still declined `out_of_corpus`; exempted by the owner.
- **Item 19** — still over-claims TypeScript (“a strong foundation in … TypeScript”);
  generation-side, unchanged by the window. **Confirmed as a known defect.**
- **Item 4** — still `FabricatedCitation`; generation-side, unchanged. **Confirmed.**
- **New errors (B only):** item **74** (“You didn't build that monitoring stack…”), item
  **83**, and item **97** (“How do you handle credentials and secrets?”) now error
  `FabricatedCitation`. Item 97's window is `secret-management-evolution.org` (rank 1),
  `api-key-rotation.org` (rank 2), `infrastructure-guardrails.org`, `core-values-vs-framework.org`
  — the fabricated claim is generation-side, not a retrieval miss.
- **Faithfulness set:** A's unfaithful items were 32 and 87; B's are 65 and 67. The
  unfaithful count is 2 in both; the raw pass count falls only because three items left the
  observed population. **`citation_precision`** improved 0.6815 → 0.7262 (n=42), as
  predicted for de-duplicated sources.

### Next candidate lever

The failure is dominated by **generation-side `FabricatedCitation` / over-claim**, not by
the retrieval window: the `sources` window de-duplicates chunks and the model fabricated
citations on items **74, 83 and 97**, while items 71/75 still under-cite. The shipped
default therefore **stays `chunks`**. The next candidate is the **deterministic
citation/over-claim guard (ADR-009, E2)** — it addresses item 19, item 4 and the new
errors together. If a retrieval lever is tried instead, the collection-independent
**dense-only** measurement from §5.8 is the one to take first; another window variant
before the generation guard would repeat this run's failure mode.
