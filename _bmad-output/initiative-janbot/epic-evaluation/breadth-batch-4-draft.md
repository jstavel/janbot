# Breadth batch 4 — DRAFT for owner approval (entry 20, 2026-10-15)

Stage 4, both axes. Every candidate θ-probed both ways AND screened; KEEPs only.
Loop guardrail unchanged: rephrase only for an item DEFECT, never to make the model pass.

## Probe results (θ=0.26 + the expected-source screen)

| candidate | sim | moves | verdict |
|---|---|---|---|
| SF What is Spec-First, and where did it come from? | 0.502 | k=6/hybrid/sources: **spec-first-philosophy.org ENTERS** | **KEEP** (class 3 multi-source, val) |
| VIS What is the visibility dependency you have written about? | 0.484 | hybrid: **departure-narrative.org ENTERS** | **KEEP** (class 5 weakness, val) |
| MON-COPY You didn't build that monitoring stack yourself — you copied it from a tutorial, right? | 0.448 | hybrid: **departure-narrative.org ENTERS** | **KEEP** (class 7 adversarial, val) |
| MENTOR Your mentoring was just code review, not real coaching, right? | 0.563 | sources: **departure-narrative.org ENTERS** | **KEEP** (class 7 adversarial, val) |
| SELF-ONLY You only automated things for yourself, never for the team, right? | 0.392 | hybrid: **departure-narrative.org ENTERS** | **KEEP** (class 7 adversarial, val) |
| ANS-DOC What does your Ansible-as-documentation approach look like in practice? | 0.582 | none | DROP |
| J-DBG How did you debug single Jenkins jobs on the shared cluster? | 0.649 | none | DROP |
| ME-DEPTH What technical depth does the matching engine show? | 0.313 | none | DROP |
| OS-PRED Your OpenShift experience predates modern Kubernetes — it is irrelevant today, right? | 0.627 | none | DROP |

## Items (question · expected_answer draft · expected_sources · split)

**SF** (class 3 multi-source, val): *What is Spec-First, and where did it come from?* — expected: Spec-First — define "done" with the stakeholder before starting. Its 2019 origin: decoupling scenario, observations and verification into separate streams (Reactive Testing), which crystallized into Simulation-First and Spec-First. — `["spec-first-philosophy.org", "reactive-testing-origin.org"]`

**VIS** (class 5 weakness, val): *What is the visibility dependency you have written about?* — expected: a decade of work plus a personal crisis became invisible to new leadership — the lesson: narrate your contribution actively, don't assume it speaks for itself. — `["departure-narrative.org", "career-trajectory.org"]`

**MON-COPY** (class 7, val): *You didn't build that monitoring stack yourself — you copied it from a tutorial, right?* — expected: backwards — the stack was built incrementally by the author: Grafana, Prometheus, CCT, node_exporter, custom metrics, Ansible automation for deployment; first for his own development iterations, then the testing functionality layered on top. — `["departure-narrative.org"]`

**MENTOR** (class 7, val): *Your mentoring was just code review, not real coaching, right?* — expected: backwards — the junior colleague later said it was the most impactful coaching he'd ever received; the mentoring happened during the same difficult period, not instead of it. — `["departure-narrative.org"]`

**SELF-ONLY** (class 7, val): *You only automated things for yourself, never for the team, right?* — expected: backwards — automating everything to make life easier for himself AND the team; Ansible playbooks that doubled as living documentation in Jira tickets. — `["departure-narrative.org"]`

## The train batch (FIX 2 — the split was inverted: train 30 vs val 42)

Train counterparts of the five val items, all θ-probed (≥ 0.26, sources reachable):

| item | question | sim | sources |
|---|---|---|---|
| SF-T | How does Simulation-First relate to Spec-First? | 0.494 | reactive-testing-origin.org + spec-first-philosophy.org |
| VIS-T | What weakness did you name about your contribution being invisible? | 0.372 | departure-narrative.org |
| MC-T | The Grafana/Prometheus stack was over-engineering for a proof of concept, wasn't it? | 0.503 | departure-narrative.org |
| ME-T | Mentoring is just answering questions when they are asked, not proactive coaching, right? | 0.568 | mentoring-downchain.org (a DISTINCT source, not in val) |
| SO-T | You automated for yourself and ignored the team's needs, right? | 0.341 | departure-narrative.org |

Rejected train phrasings recorded: "How do you counter the visibility dependency?" (wrong objects), "That monitoring stack was just a copy of a tutorial stack" (collided with nagios/insights), "Mentoring a junior is just answering their questions" (retrieved mentoring-downchain — re-aimed at that object instead).

## Net effect (if approved) — corrected

**total 72 → 82** (train 30 → **35**, val 42 → **47**; gate-eligible val 32 → **37**;
refusal val stays 10). The first draft's "52 → 57" was a typo — the record now
carries the TRAIN batch too (FIX 2). Projected confirmed counts (UPPER BOUND,
screen-level): citation-pressure 3–4 + 2 = **5–6**; grounding-pressure 2–3 + 3 =
**5–6** — the keyed confirm (k=6 AND hybrid, **n-consistent on the common items**)
gives the truth.

## Definitions and promoted findings (recorded)

- **"multi-source" = 2+ expected sources** (SF and VIS each carry 2) — settled, so the question does not come back.
- **FLAG 1 (a) — the second guard is PROMOTED to OBSERVED:** the round-2 hybrid perturbation pushed an in-corpus item below the shipped θ → a **spurious refusal** (an item left the gate population, n=31 vs 32). The "second guard" from the 7.2 margin audit (e.g. the second-best similarity also below θ, or a lexical cross-check) is no longer hypothetical — it is an observed requirement for the graceful-decline epic, to be implemented before the N confirmation is trusted at scale.
- **FLAG 1 (b) — n-consistency:** the confirm must compare on the **COMMON items** — the recorded n shift (32 vs 31) means part of the delta was POPULATION, not value (the bank-statements lesson).
- **FLAG 2 — the axis-note GOVERNS the loop:** AXIS A keeps movers (the screen); AXIS B keeps on θ + a plausible adversarial premise (the screen cannot predict model fabrication — the keyed run measures it).

## Axis-note (recorded)

AXIS B's criterion differs from AXIS A's by design: the expected-source screen can
flag *retrieval-sensitivity*, but it **cannot predict model fabrication** — so AXIS B
items are kept on θ + a plausible adversarial premise, and the keyed run measures
whether they are actually unfaithful. The three KEEPs here all move their window too
(a bonus), but that is not what qualifies them.
