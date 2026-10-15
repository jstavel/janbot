# Breadth batch 3 — DRAFT for owner approval (entry 20, 2026-10-15)

Stage 3, on **TWO axes** (the gate has two populations):
- **AXIS A — citing-pressure** (the GAIN-CARRIER): items whose **cited set can move** — the expected source **enters or leaves the window** under a perturbation (k=6 / hybrid / sources). Confirmed so far: 2; target N_citation ≈ 10.
- **AXIS B — grounding-pressure** (the GUARD): adversarial items where the model may invent — this **lifts the faithfulness ceiling** (more unfaithful items create room below 0.9565, so faithfulness becomes movable again).

Every candidate: θ-probed both ways (non-refusals ≥ 0.26; refusals < 0.26) AND the **redefined expected-source screen** → **KEEP only the movers**. Rejected candidates recorded.

## The redefined screen (recorded; replaces the tautological window-diff screen)

Old screen (the window changes across top_k 4/6, dense/hybrid, chunks/sources): flagged **23/23** — tautological. New screen (does the item's **expected source enter/leave** the window): flags **3/23** — items 23, 29, 42; the k=6 confirm moved 2 of them (29, 42) and item 23's move is hybrid-predicted (untested). Validated.

## Probe results (KEEP/DROP)

| candidate | sim | moves | verdict |
|---|---|---|---|
| A2 How did your Linux experience develop, from Linux From Scratch to production servers? | 0.571 | hybrid: **linux-server-era.org LEAVES** | **KEEP** (class 2/3, val) |
| MON What monitoring stack did you build for the testing-at-scale proof of concept? | 0.566 | hybrid: **departure-narrative.org ENTERS** | **KEEP** (class 4, val) |
| NAG What did you build to monitor Red Hat QA systems? | 0.469 | **k=6 / hybrid / sources: nagios-snmp-monitoring.org ENTERS** | **KEEP** (class 4, val) |
| OS What was the OpenShift platform work at Red Hat, and what ran on it? | 0.676 | k=6/sources: **jenkins-openshift-cicd-operations.org ENTERS** | **KEEP** (class 3, val) |
| B3 You only ever wrote playbooks — you never touched the container platform itself, right? | 0.297 | k=6/hybrid: **jenkins-openshift-cicd-operations.org ENTERS** | **KEEP** (class 7, val) |
| A1 What did the Cockpit test architecture and the RHSM Ansible work have in common? | 0.635 | none | DROP |
| MON2 What monitoring systems have you built or operated? | 0.459 | none | DROP |
| A4 How do you design internal tools? / the intranet pattern phrasing | 0.48–0.57 | none | DROP |
| ANS What did you build with Ansible at Red Hat, and what did it automate? | 0.647 | none | DROP |
| B1 Wasn't the monitoring project just scope creep that failed? | 0.483 | none | DROP |
| B2 Since your estimates were unreliable, why should we trust your delivery dates? | 0.409 | none | DROP |
| B4 Wasn't your Jenkins work just babysitting a build server? | 0.527 | none | DROP |
| B5 You say you debug systems — but you never debugged anything at scale, right? | 0.376 | none | DROP |
| M1/M2 What makes the matching engine technically interesting? / technically notable | 0.374–0.377 | none | DROP |

## Items (question · expected_answer draft · expected_sources · split)

**A2** (class 2/3, val): *How did your Linux experience develop, from Linux From Scratch to production servers?* — expected: from a 1.44MB Linux From Scratch boot floppy (built as a school IT admin with only netcat and dd to clone Windows 95 machines across the network — deep Linux fundamentals with minimal resources) to running and debugging production Linux servers and services at Red Hat scale. — `["linux-from-scratch.org", "linux-server-era.org"]`

**MON** (class 4, val): *What monitoring stack did you build for the testing-at-scale proof of concept?* — expected: a complete monitoring/observability stack built incrementally — Grafana, Prometheus, CCT, node_exporter and custom metrics, with Ansible automation for deployment. — `["departure-narrative.org"]`

**NAG** (class 4, val): *What did you build to monitor Red Hat QA systems?* — expected: monitoring infrastructure for Red Hat QA systems — Nagios/SNMP-based monitoring and an Insights health-monitoring architecture (expected answer per the corpus objects; the owner refines the wording). — `["nagios-snmp-monitoring.org", "insights-health-monitoring.org"]`

**OS** (class 3, val): *What was the OpenShift platform work at Red Hat, and what ran on it?* — expected: hands-on ownership of a shared Jenkins CI/CD on OpenShift — job definitions as code, the seed job, agents built as Podman container images, debugging single jobs safely on a large shared cluster — plus the Cockpit/RHSM web-UI tests running against services deployed on the same container platform. — `["jenkins-openshift-cicd-operations.org", "rhsm-cockpit-qe.org"]`

**B3** (class 7, val): *You only ever wrote playbooks — you never touched the container platform itself, right?* — expected: backwards — the work included agents built as Podman container images and debugging single jobs safely on a large shared OpenShift cluster; the playbooks were one part of hands-on platform operations. — `["jenkins-openshift-cicd-operations.org"]`

## Net effect (if approved)

val (gate-eligible) 23 → **28** (+5, all citing-pressure or grounding-pressure movers);
refusal val stays **10**; total 52 → **57**; train 27 → 30 stays. **Projected confirmed
citation-pressure: 2 + 5 movers = 7** (approaching N_citation ≈ 10; the next confirm
measures it).

## Owner calls recorded

- **Class 4 val gap: FILLED by this batch** — two DISTINCT strengths sources (`nagios-snmp-monitoring.org`, `departure-narrative.org`'s monitoring stack), neither `linux-from-scratch.org` (which near-duplicates item 13).
- **Class 10 (voice):** still deferred — owner prose.
- **Class 9 train counterpart:** still the recorded exception (retrieval-reachability).
