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

## Net effect (if approved)

val (gate-eligible) 32 → **37** (+5); refusal val stays 10; total 52 → **57**; train stays 30.
Projected confirmed counts (UPPER BOUND, screen-level): citation-pressure 3–4 + 2 = **5–6**;
grounding-pressure 2–3 + 3 = **5–6** — the keyed confirm (k=6 AND hybrid) gives the truth.

## Axis-note (recorded)

AXIS B's criterion differs from AXIS A's by design: the expected-source screen can
flag *retrieval-sensitivity*, but it **cannot predict model fabrication** — so AXIS B
items are kept on θ + a plausible adversarial premise, and the keyed run measures
whether they are actually unfaithful. The three KEEPs here all move their window too
(a bonus), but that is not what qualifies them.
