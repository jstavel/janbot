# Breadth batch 5 — DRAFT for owner approval (entry 20, 2026-10-15)

Leaning into the **hybrid-mover class** (from the batch-4 diagnosis: the expected
source is a semantic neighbour the base dense window MISSES but hybrid retrieves) —
they miss at the baseline **by design** and recover under hybrid, so they are the
highest-value gain movers. Axis B also fed. Every candidate θ-probed both ways and
screened; DROPs recorded; the axis-note governs (A = movers, B = θ + a plausible
adversarial premise).

## Probe results (KEEPs)

| candidate | sim | base window | verdict |
|---|---|---|---|
| BE What is the Beaker CI you worked with? | 0.303 | not in base | **KEEP** (AXIS A hybrid-mover: rhsm-ansible-qe.org ENTERS hybrid) |
| CM What are the custom metrics in your monitoring stack? | 0.543 | not in base | **KEEP** (AXIS A hybrid-mover: departure-narrative.org ENTERS hybrid) |
| PYGLUE Your Python work is just glue scripts, not real systems work, right? | 0.379 | not in base | **KEEP** (AXIS A hybrid-mover AND AXIS B adversarial: audio-transcription-pipeline.org ENTERS hybrid) |
| TOY The matching engine is a toy, not a real product, right? | 0.303 | in base | **KEEP** (AXIS B adversarial; source reachable) |
| CHEAT You learned Kubernetes from a cheat sheet, not from real work, right? | 0.441 | in base | **KEEP** (AXIS B adversarial) |
| EDEP The eDeposit work was just one library — not substantial, right? | 0.528 | in base | **KEEP** (AXIS B adversarial) |
| CI-RAN You never actually ran anything in CI — it was just talk, right? | 0.333 | in base | **KEEP** (AXIS B adversarial) |
| BE-T What is Beaker CI? (train) | 0.299 | in base | **KEEP** (train counterpart) |
| HOBBY The audio transcription pipeline was a weekend hobby project, wasn't it? (train) | 0.526 | in base | **KEEP** (train counterpart) |

DROPs recorded (measured): "What is CCT in your monitoring stack?" (no reach), "What
is the estimate-in-ranges method?" / "Xapian?" / "seed job?" / "Cockpit UI?" /
"AMQP pdfbox worker?" / "granular playbook patterns?" / "mini-seed pattern?" /
"container agents?" / "What did the Cockpit/RHSM synthesis?" / the trading /
stock-update / Perl-to-Clojure / eDeposit-specific / matching-engine-depth
phrasings (dense-reachable, no move) — see the probe logs. The hybrid-mover class is
**scarce in a small corpus**: most objects are dense-reachable, so a true
mover (dense-missed, hybrid-found) required featural phrasing; 3 were found.

## Items (question · expected_answer draft · expected_sources · split)

**BE** (class 3, val): *What is the Beaker CI you worked with?* — expected: Beaker CI — Red Hat's automation server for installing, configuring and testing systems at scale; the RHSM Ansible + Robot Framework test architecture ran on it. — `["rhsm-ansible-qe.org"]`

**CM** (class 4, val): *What are the custom metrics in your monitoring stack?* — expected: the monitoring stack's custom metrics alongside CCT and node_exporter, all under Ansible automation — built for the testing-at-scale proof of concept. — `["departure-narrative.org"]`

**PYGLUE** (class 7 + mover, val): *Your Python work is just glue scripts, not real systems work, right?* — expected: backwards — the audio transcription pipeline is a real systems build in Python, not glue. — `["audio-transcription-pipeline.org"]`

**TOY** (class 7, val): *The matching engine is a toy, not a real product, right?* — expected: backwards — the matching engine is a serious, spec-driven project (expected answer per the corpus object; the owner refines). — `["matching-engine.org"]`

**CHEAT** (class 7, val): *You learned Kubernetes from a cheat sheet, not from real work, right?* — expected: backwards — the OpenShift platform work IS Kubernetes experience delivered through real container-platform work (Jenkins agents as Podman images, debugging jobs on a shared cluster). — `["openshift-kubernetes-bridge.org", "jenkins-openshift-cicd-operations.org"]`

**EDEP** (class 7, val): *The eDeposit work was just one library — not substantial, right?* — expected: backwards — the eDeposit work spans libraries (clj-amqp, amqp.pdfbox, amqp.kramerius) and the AMQP/pdfbox worker. — `["edeposit.org"]`

**CI-RAN** (class 7, val): *You never actually ran anything in CI — it was just talk, right?* — expected: backwards — a test architecture at production scale ran in Beaker CI: 60+ playbooks, a 737-line orchestrator, custom plugins. — `["rhsm-ansible-qe.org"]`

**BE-T** (class 3, train): *What is Beaker CI?* — `["rhsm-ansible-qe.org"]` (classic fact-lookup, train counterpart).

**HOBBY** (class 7, train): *The audio transcription pipeline was a weekend hobby project, wasn't it?* — expected: the correction (the pipeline is a real build, not a hobby). — `["audio-transcription-pipeline.org"]`

## Net effect (if approved)

val (gate-eligible) 37 → **44** (+7); refusal val stays 10; train 35 → **37**; total 82 → **91**.
Projected confirmed citation-pressure (UPPER BOUND): 6 (hybrid, round 3) + 3 hybrid-movers = **9** —
squarely nearing N_citation ≈ 10; the keyed confirm (k=6 AND hybrid, n-consistent) gives the truth.
Guard population (adversarial): 3 → **8** — the faithfulness ceiling lifts further.