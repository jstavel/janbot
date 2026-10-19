# Re-baseline item proposals — corpus round 2026-10-18

**Status:** **APPROVED by the owner on 2026-10-19** — N10–N15, the 4 train / 2 val split,
P1 Option B, and the N14 redaction. N15 was corrected before application after the source
object was reframed (see the note in §C). The approved texts are frozen; the dataset change
is applied in commit `ee38b18`.

**Companion:** `rebaseline-brief-20261018.md` (the diagnosis).

Source of truth for the corpus: `~/org` at pinned ref
**`05b11a78049190838069b5f5c6ad123ae420a104`**. Extract and index are built
(`public_profile_org/` = 61 content files + `MANIFEST`; index = 417 chunks, 60 sources).

---

## A. Split proposal and rationale

**Proposed: 4 train / 2 val.**

- **train — N10, N11, N14, N15:** knowledge drift, procedure drift, the Clojure interview,
  and API-key rotation. These are procedural, security, and architecture claims; they
  broaden the compile learning set.
- **val — N12, N13:** the closing cadence and substitutable AI. These are the two most
  over-claim-prone, recruiter-facing items: one is honest about an unproven cadence, the
  other states the TypeScript/Clojure gap plainly. They test the weakness/honesty axis,
  which the taxonomy has kept thin.

Rationale for 4/2: the previous round appended 6 train / 3 val (2:1) for nine items; 4/2
continues that pattern and still grows the gate-eligible val population (47 → 49). A 3/3
split (moving N15 to val) was considered and rejected because it would put both credential
items in val and duplicate the class.

If P1 (item 19) is approved, it changes only the `expected_answer` of an existing val item;
the question and split stay byte-identical, so the counts below do not change.

## B. Numbering

The current dataset is **100 items** (0-based indices 0–99). The six proposals are appended
at **100–105**:

| proposed id | index | object | split |
|---|---|---|---|
| N10 | 100 | `knowledge-drift.org` | train |
| N11 | 101 | `procedure-drift.org` | train |
| N12 | 102 | `drift-closing-cadence.org` | val |
| N13 | 103 | `substitutable-ai.org` | val |
| N14 | 104 | `architect-not-coder.org` | train |
| N15 | 105 | `api-key-rotation.org` | train |

No existing item is renumbered, reordered, or re-split.

## C. Six new items (apply verbatim after approval)

```yaml
- question: "How do you keep a team able to own an AI-assisted codebase?"
  expected_answer: >-
    By reducing the unbounded body of knowledge to the finite set of decisions the
    team must be able to defend. For each decision, the test has three parts: what
    holds, what alternative was rejected, and what breaks if it changes — "I know
    we use a digest" is half an answer unless you can say why not a tag. The
    artifact is a derived index, not a second source of truth: `_bmad-output/` stays
    the write model (ADRs and specs), and `DECISIONS.md` is a read model over it,
    one row per ADR id (no new numbering), with no pin/no row, the ADR winning on
    conflict, idempotent regeneration that never overwrites the human-owned
    `verified` column, and holes left visible because the hole is the metric.
    Verification is an answer produced in the human's own words against the pinned
    line, sampled by blast radius and longest-unverified; honest limit: it is a
    self-assessment mediated by the agent, not an objective measurement.
  expected_sources:
    - knowledge-drift.org
  split: train
  should_refuse: false

- question: "Why does a runbook have to be run by hand?"
  expected_answer: >-
    Because know-what is closed by reading and know-how only by executing: a
    procedure is believed only when someone who did not watch the agent runs it.
    `RUNBOOK.md` is a primary artifact, authored not generated, and the single
    source for how; `_bmad-output/` remains the single source for what and why.
    It is written for the agent first and the human second because the agent starts
    every session from zero while a human pays a missing line once — a gap is a tax
    at every execution. The drift is measured free from traces: the delta between
    commands actually executed and the runbook, stale entries nobody has run for N
    months, and the agent's own questions, since every session tests the runbook.
    The work is filtered by blast radius: must (deploy, key rotation, destructive
    operations) always closed and periodically re-verified, should closed over
    time, never legitimately agent-only and not a debt. Honest limit: no question
    log exists yet; the continuous test is a design, not a measured instrument.
  expected_sources:
    - procedure-drift.org
  split: train
  should_refuse: false

- question: "How do you keep up with your own AI-assisted work?"
  expected_answer: >-
    By scheduling the closing rather than waiting for it: the drift is closed on a
    calendar, not on demand. Three instruments: a compressed onboarding document —
    not a Q&A bank, but one dense map that AI writes and re-compresses and that
    grows as knowledge accumulates; a weekly block reserved with no development in
    it, where unfinished work is closed or explicitly parked across knowledge,
    experience, workflow and team; and a daily close that asks the agent what new
    knowledge appeared, then closes both axes by hand — one decision defended out
    loud (decision, rejected alternative, failure mode) and one runbook command
    actually executed — before the day is closed emotionally as well. The honest
    limit: the drift is already a month deep, so the cadence may still lose; it is
    an experiment, not a verified method, but closing must be scheduled because
    unscheduled learning is how the gap accumulates.
  expected_sources:
    - drift-closing-cadence.org
  split: val
  should_refuse: false

- question: "Does the AI have to be substitutable too, and are you?"
  expected_answer: >-
    Yes, and it is symmetrical: if a team member is not substitutable it is a
    single point of failure, and that applies to the agent exactly as it applies to
    me. The concrete test is to turn the AI off — can I debug, extend and fix what
    was shipped? The honest competence map: Python, Perl and JavaScript are expert,
    written by hand for years; Clojure is deep experience but currently rusty;
    TypeScript produced a large project with agents, but I cannot write a line
    unaided and without agents I am a beginner there. The strategic choice is
    conservative (AI only where expertise already exists) or expansive (AI to enter
    a new stack only with active personal practice); expansive without the practice
    clause is dependency with the guarantee removed. The gap is open, not closed:
    this is a rule for future work, not a claim of current mastery.
  expected_sources:
    - substitutable-ai.org
  split: val
  should_refuse: false

- question: "What did the Clojure interview actually test?"
  expected_answer: >-
    A final round for a Clojure role where the hands-on part was deliberately small
    and the question that carried the signal was the trade-offs between the
    libraries one would reach for — not a request for a large amount of code. It
    tested trade-off knowledge and design judgement, not typing speed. The tempting
    reading, "I only need to design, not code", is half true and dangerous:
    trade-off knowledge without implementation is opinion, and implementation
    without trade-off knowledge is typing; a senior is expected to hold both. The
    honest consequence is to declare TypeScript as a new skill built with agents
    rather than let the workflow imply expertise — the artifact shows architecture,
    specification and verification, not language mastery. The specific library
    trade-offs were not recalled in the interview itself; that is recorded as a
    learning item, not a strength.
  # owner instruction 2026-10-19: interview identifying details redacted here and in
  # architect-not-coder.org (see its <renegotiated> marker) — anonymisation + the
  # specifics carry no part of the lesson.
  expected_sources:
    - architect-not-coder.org
  split: train
  should_refuse: false

- question: "How should an API key held by an agent be rotated?"
  expected_answer: >-
    Treat the threat as persistence, not leakage: an agent that touches the key can
    write it down and keep it, so the grant survives the task and no prompt fixes
    that. The rule that governs the rest is that a control whose parameters disagree
    with each other becomes a scheduled failure. Validity has to outlive the rotation
    interval with margin — a 30-day validity rotated weekly leaves three weeks of
    headroom, a 7-day validity rotated weekly leaves none. The spend cap is computed
    for one key's lifetime rather than per month, because rotation resets it: monthly
    exposure is keys × cap, so the exposure multiplier equals the cap's margin. The
    reset period stays off, so a cap that is reached doubles as a rotation-lapse
    detector, at the price that a capped key looks like a broken key. Everything sits
    in one authoritative store (Secret Manager) with ephemeral retrieval, never on
    disk, logs or a user-visible context. Honest status: store, validity and cap are
    in place; the rotator, anomaly monitoring and the revocation playbook are not.
  expected_sources:
    - api-key-rotation.org
  split: train
  should_refuse: false
```

**N15 correction (2026-10-19).** The first N15 draft was written against the pre-reframe
`api-key-rotation.org`. The owner's reframe replaced key-specific properties and absolute
figures with the general parameter-consistency rule and recorded the store, validity and
cap as in operation. The draft was therefore stale in both directions — it under-claimed
the deployed state and omitted the governing rule. The expected answer above is the
corrected text; the superseded draft is not reproduced. The same question, source and
`train` split are unchanged.

**A rule for future rounds:** a falsification scan is a **point-in-time** check. After a
correction lands, re-scan the pending texts derived from the old version, not only the
dataset.

## D. Falsification / contradiction scan of the existing 100 items

### D.1 Contradiction — item 19 (0-based): “Tell me about yourself.”

The pre-round intro said: *“Professional in Perl and Python, JavaScript and TypeScript, yet
Clojure is the true passion.”* The new corpus contradicted the TypeScript part (the
`substitutable-ai.org` and `architect-not-coder.org` claims that TypeScript is
agent-assisted, not hand-written).

**Resolved at the corpus level, then approved as P1 Option B.** The owner renegotiated
`personal-intro.org` to *“Python and Perl by hand, Clojure by heart, TypeScript with
agents.”* The item's `expected_answer` now matches that honest version:

```yaml
- question: "Tell me about yourself."
  expected_answer: >-
    Stories bring the power to know; success fuels the power to grow. Trust builds joy,
    and shared joy is twice the joy. Python and Perl by hand, Clojure by heart,
    TypeScript with agents. I build systems whose output can be verified, not merely
    demonstrated. I cherish the fleeting moments that remind me I am still growing.
  expected_sources:
    - personal-intro.org
  split: val
  should_refuse: false
```

The question, split, `expected_sources` and `should_refuse` are byte-identical; only the
`expected_answer` changes. **Rationale:** the corpus now declares TypeScript as
agent-assisted, so the item tests the honest version instead of the over-claim.

### D.2 Narrower, but not false (no repair proposed)

- **Item 97 — “How do you handle credentials and secrets?”** (`val`). The reframed
  `api-key-rotation.org` adds the general parameter-consistency rule (a control whose
  parameters disagree becomes a scheduled failure) and records the store, validity and cap
  as in operation, while the rotator, monitoring and revocation playbook are not built. The
  existing answer remains true; it is incomplete on the new rule. `expected_sources` is
  deliberately **not** widened before the run — that would be tuning to an unmeasured
  outcome. No repair proposed.
- **Item 17 — “How do you use AI in your day-to-day work?”** (`val`). The new
  `architect-not-coder.org` sharpens “the human role is architect” into “architect and still
  able to implement.” The existing answer is not false; it is incomplete on that point. No
  repair proposed.

### D.3 Explicit result

- **Item 19:** contradiction found, resolved by the corpus renegotiation and P1 Option B.
- **N15:** pending text found stale after the source reframe; corrected before application.
- **Items 17/97:** narrower but true; untouched.
- **No falsification or contradiction found in the other items.**

## E. Arithmetic

| | now | after N10–N15 | note |
|---|---|---|---|
| items | 100 | **106** | +6 |
| train | 43 | **47** | +4 |
| val | 57 | **59** | +2 |
| `should_refuse: true` | 13 | **13** | unchanged |
| gate-eligible val | 47 | **49** | val − 10 refusals |

P1 Option B is applied: it changes one existing val item's `expected_answer` only; counts
and split do not change. The new `dataset_sha256` is
**`a8bd69dc10f0c9da5dc1b4d0c9639908c75323b7ced9671a0266a7d33ac11c90`**.

## F. Approval checklist (owner, 2026-10-19)

- [x] **N10** knowledge-drift — text and `train`
- [x] **N11** procedure-drift — text and `train`
- [x] **N12** drift-closing-cadence — text and `val`
- [x] **N13** substitutable-ai — text and `val`
- [x] **N14** architect-not-coder — text and `train` (redacted)
- [x] **N15** api-key-rotation — text as corrected 2026-10-19 and `train`
- [x] **Split** 4 train / 2 val
- [x] **P1** item 19: Option B

## G. Hard limits for the builder

- The approved texts are frozen; change one only with a new owner approval or a
  `<renegotiated>` marker.
- Do not change any existing question string; the P1 question stays byte-identical.
- Do not add items beyond N10–N15; no renumbering, no re-splitting.
- Do not touch the seven new objects, the `/chat` contract, the AI core, or the guardrail
  behaviour.
- Do not run the keyed eval without the owner's explicit go.
- This is a re-baseline, not a gate verdict.

## H. Approval record

- **Owner approval:** 2026-10-19.
- **Approved:** N10–N15 (texts in §C; N15 as corrected), 4 train / 2 val, P1 Option B,
  N14 redaction.
- **Corpus pin:** `05b11a78049190838069b5f5c6ad123ae420a104` (59 objects, 61 content files).
- **Dataset:** 100 → 106; train 43 → 47; val 57 → 59; `should_refuse` 13; gate-eligible val
  47 → 49.
- **`dataset_sha256`:**
  `a8bd69dc10f0c9da5dc1b4d0c9639908c75323b7ced9671a0266a7d33ac11c90`.
- **Frozen:** the §C item texts and the §D.1 item-19 `expected_answer`.
