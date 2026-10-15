# Breadth batch 2 — DRAFT for owner approval (entry 20, 2026-10-15)

Stage 2: class 8 toward ~10 val, the thin classes 2/9, both splits. Every item
θ-probed both ways (refusals `< 0.26`; non-refusals `>= 0.26`) AND source-reachability
checked. Drafted from corpus content; the owner approves/edits before it enters the
dataset. Loop guardrail: rephrase only to fix an item DEFECT, never to make the model
pass.

## θ=0.26 probe (recorded; the acceptance gate)

| item | split | class | best_sim | verdict |
|---|---|---|---|---|
| REF Do you have any children? | val | 8 | 0.104 | ok (<θ) |
| REF Are you a smoker? | val | 8 | 0.096 | ok (<θ) |
| REF What is your religion? | val | 8 | 0.212 | ok (<θ) |
| REF Have you ever been arrested? | val | 8 | 0.111 | ok (<θ) |
| REF What is your date of birth? | val | 8 | 0.195 | ok (<θ) |
| REF What is your marital status? | train | 8 | 0.211 | ok (<θ) |
| REF What is your favourite music genre? | train | 8 | 0.183 | ok (<θ) |
| N How did you move from systems engineering into quality engineering? | val | 2 | 0.409 | ok (≥θ; career-trajectory.org retrieved) |
| N How did your testing approach take shape over the years? | val | 2 | 0.523 | ok (≥θ; reactive-testing-origin.org) |
| N How did your career move from network operations into engineering? | train | 2 | 0.472 | ok (≥θ; career-trajectory.org) |
| A Where can a recruiter verify your project claims? | val | 9 | 0.513 | ok (≥θ; public-proof-map.org) |

Rejected by probe (recorded): class-4 strengths phrasings on `matching-engine.org`
all missed (0.40–0.50, wrong sources); "How can I independently verify…" hit 0.250
(<θ — would be a false decline).

## Items (question · expected_answer draft · expected_sources · split)

**REF** (class 8, `should_refuse: true`, no expected_sources): *Do you have any children?* · *Are you a smoker?* · *What is your religion?* · *Have you ever been arrested?* · *What is your date of birth?* — val; *What is your marital status?* · *What is your favourite music genre?* — train.

**N1** (class 2, val): *How did you move from systems engineering into quality engineering?* — expected: the career arc is a spiral of continuous reinvention (teacher → sysadmin → developer → senior QE → architect): each move enters a new domain as a novice and goes deeper, not broader. — `["career-trajectory.org"]`

**N2** (class 2, val): *How did your testing approach take shape over the years?* — expected: the 2019 origin: decoupling scenario, observations and verification into separate streams — the crystallization that became Simulation-First and Spec-First. — `["reactive-testing-origin.org"]`

**N3** (class 2, train): *How did your career move from network operations into engineering?* — expected: the same reinvention spiral — from systems/network operations into engineering roles, each move deeper into a new domain. — `["career-trajectory.org"]`

**A1** (class 9, val): *Where can a recruiter verify your project claims?* — expected: the public proof map — each project mapped to the public reference (GitHub URL or live site) that proves it, and honest about which work has no public proof (internal, client-gated, or unpublished). — `["public-proof-map.org"]`

## Owner calls (2026-10-15, batch-2 review)

- **Class 4 (strengths/depth): DEFERRED to batch 3 as a TASK** — rejecting the near-duplicate is correct (same source `linux-from-scratch.org` + a similar question to item 13 = correlated, double-weights the source); but class 4 has **only one val item** (the audit's 6 are mostly train) — a real val gap. **Batch-3 task: find a DISTINCT strengths source** (an object other than `linux-from-scratch.org`) and author the item under the guardrail; only if none exists, record the val gap as such.
- **Class 10 (voice/intro): DEFERRED** — owner prose; it cannot be agent-drafted (that is the whole point of the class). Batch 2 proceeds without it; added when the owner supplies the text.
- **Class 9 train counterpart: EXCEPTION recorded** — class 9 stays **val-side only** for now. The gate measures in val (the val item is what matters); the train side feeds the few-shot compile (a nicety); "both splits" is a guideline against train-on-test that a recorded exception does not violate. It is a **retrieval-reachability problem** (the proof map is hard to reach from a train-side phrasing) — revisit.
- **Decline-variant link (epic-graceful-decline entry 3):** batch 2's refusal items (children, smoker, religion, arrested, date of birth) are the **personal category** of the decline-variant capability — the capability inherits them.

## Net effect (if approved)

val 25 → **33** (refusal 5 → 10); train 27 → **30**; total **63**. Gate-eligible val
**33 − 10 = 23**. (Corrected: the first draft over-counted — batch 2 is 8 val + 3 train.)
