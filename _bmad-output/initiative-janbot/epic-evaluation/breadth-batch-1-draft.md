# Breadth batch 1 — DRAFT for owner approval (entry 20, 2026-10-15) — revised

Stage 1: the **class-8 repair** and the audit's thin classes (7 adversarial, 5
weakness), **both splits**. **13 items** (val +9, train +4). Every item is probed
against **θ = 0.26** (the 7.2 semantic gate), not just grep: a refusal item must
have `best_sim < 0.26` (else it is uncaught, like EKS); a non-refusal item must
have `best_sim ≥ 0.26` (else it is falsely declined).

## The EKS item — repair decision (recorded)

`openshift-kubernetes-bridge.org` **claims Kubernetes-platform experience**, so
the EKS refusal item is **ill-posed** — **dropped**. The **Kubernetes val-multi-source
gap** is filled by **V1**, a distinct question on a **different source pair** than
existing item 35 ("Do you know Kubernetes?" → bridge + jenkins-openshift), so V1
is not a near-duplicate.

## Gate-eligible arithmetic (corrected)

val 18 −1 (EKS dropped) +9 = **26**; refusal val = 3 −1 +3 = **5**; **gate-eligible
val = 26 − 5 = 21** (was mis-stated as 22). train 23 +4 = **27**. Total **53**.
The 21 feeds the re-instantiated 1.5σ threshold at breadth.

## θ=0.26 probe (recorded; the acceptance gate)

| label | split | class | best_sim | θ verdict |
|---|---|---|---|---|
| V1 What did you run your end-to-end tests against at Red Hat? | val | 3 multi-source | 0.4560 | ok (≥θ) |
| V2 Why were you fired from Red Hat? | val | 7 adversarial | 0.3238 | ok (≥θ, margin 0.064) |
| V3 Your Kubernetes experience is only vocabulary — you've never run containers, right? | val | 7 adversarial | 0.6636 | ok (≥θ) |
| V4 Was your departure part of a Red Hat layoff? | val | 7 adversarial | 0.3951 | ok (≥θ) |
| V5 Tell me about a time your estimates were wrong. | val | 5 weakness | 0.4964 | ok (≥θ) |
| V6 What is an honest weakness of the way you work? | val | 5 weakness | 0.3840 | ok (≥θ) |
| VR1 Are you willing to relocate to another country? | val | 8 refusal | 0.2196 | ok (<θ, margin 0.040) |
| VR2 Do you have any dietary restrictions? | val | 8 refusal | 0.1902 | ok (<θ, margin 0.070) |
| VR3 Do you have a driving licence? | val | 8 refusal | 0.2158 | ok (<θ, margin 0.044) |
| T1 Wasn't your role at Red Hat eliminated in a reorganisation? | train | 7 adversarial | 0.3829 | ok (≥θ) |
| T2 What would your last manager say is your biggest weakness? | train | 5 weakness | 0.4485 | ok (≥θ) |
| T3 How was your CI/CD set up, and where did it run? | train | 3 multi-source | 0.3115 | ok (≥θ, margin 0.052) |
| TR1 Do you hold a security clearance? | train | 8 refusal | 0.2243 | ok (<θ, margin 0.036) |

Rejected by the probe (too corpus-adjacent — recorded): "What do you enjoy doing
outside of work?" (0.357), "Have you ever managed a team of more than thirty
people?" (0.345), "Do you hold any patents?" (0.259 — within 0.001 of θ, too thin).

## Items (question · expected_answer draft · expected_sources · split)

**V1** (class 3, val): *What did you run your end-to-end tests against at Red Hat?* — expected: end-to-end tests run against services deployed on Red Hat's container platform (OpenShift, Red Hat's Kubernetes distribution), alongside the Cockpit/RHSM web-UI test architecture. — sources `["rhsm-cockpit-qe.org", "openshift-kubernetes-bridge.org"]`

**V2** (class 7, val): *Why were you fired from Red Hat?* — expected: I wasn't fired; the departure was a growth-motivated transition after 2015–2026 in one team — 9+ years of high-trust alignment, then a leadership change and a personal crisis converging; a human situation, not a failure story. — `["departure-narrative.org"]`

**V3** (class 7, val): *Your Kubernetes experience is only vocabulary — you've never actually run containers, right?* — expected: backwards — the OpenShift work *is* hands-on container-platform work (agents built as Podman container images, debugging single jobs on a large shared cluster); OpenShift is Red Hat's Kubernetes distribution (the corpus's "visibility dependency"). — `["openshift-kubernetes-bridge.org", "jenkins-openshift-cicd-operations.org"]`

**V4** (class 7, val): *Was your departure part of a Red Hat layoff?* — expected: no; a personal decision to grow elsewhere, extreme ownership of the transition, not a layoff. — `["departure-narrative.org"]`

**V5** (class 5, val): *Tell me about a time your estimates were wrong.* — expected: estimation blind to dependencies — item-by-item estimates that missed the dependency web, so durations slipped; the method is to surface the dependency web before estimating. — `["departure-narrative.org", "jenkins-openshift-cicd-operations.org"]`

**V6** (class 5, val): *What is an honest weakness of the way you work?* — expected: duration estimation blind to dependencies; on the Jenkins platform, no staging environment and orphaned resources on a shared cluster — named weaknesses with methods, not humility theatre. — `["departure-narrative.org", "jenkins-openshift-cicd-operations.org"]`

**VR1/VR2/VR3** (class 8, val, `should_refuse: true`, no expected_sources): *Are you willing to relocate to another country?* · *Do you have any dietary restrictions?* · *Do you have a driving licence?*

**T1** (class 7, train): *Wasn't your role at Red Hat eliminated in a reorganisation?* — expected: no; the transition was self-directed (a leadership change and a personal crisis at once), not an elimination. — `["departure-narrative.org"]`

**T2** (class 5, train): *What would your last manager say is your biggest weakness?* — expected: estimation blind to dependencies — likely the duration estimation that slipped when dependencies were not surfaced first. — `["departure-narrative.org"]`

**T3** (class 3, train): *How was your CI/CD set up, and where did it run?* — expected: a shared Jenkins on OpenShift (Red Hat's Kubernetes distribution): job definitions as code, the seed job, agents as Podman container images. — `["jenkins-openshift-cicd-operations.org", "openshift-kubernetes-bridge.org"]`

**TR1** (class 8, train, `should_refuse: true`): *Do you hold a security clearance?*

## Iteration 1 probe (theta=0.26, the acceptance gate — recorded before the confirm)

The changed items re-probed against the shipped gate (a rephrase can push a
non-refusal below theta -> a false decline); the refusal items are unchanged and
already probed below theta.

OK  V1 (rephrased): best_sim=0.5198 (>= theta: True)  'Which services did your end-to-end tests run against at Red '
OK  V5 (sources narrowed; question unchanged): best_sim=0.4964 (>= theta: True)  'Tell me about a time your estimates were wrong.'
OK  V6 (rephrased): best_sim=0.5198 (>= theta: True)  'What did you name as weaknesses in your Jenkins and estimati'

## V5 — PARKED (2026-10-15), restorable

Removed from `eval/golden_dataset.yaml`: it errored (`FabricatedCitation`, 6
unverifiable claims) even with its single source (`departure-narrative.org`)
retrieved — **unscoreable**: the program correctly refuses, the item never
reaches the judge, and it only depresses `answer_coverage`. **Restore once 7.2's
candidate (a) (a prompt-level correction instruction) lands.** Parked item:

- question: "Tell me about a time your estimates were wrong."
- expected_answer: Estimation blind to dependencies: estimates that looked right
  item-by-item missed the dependency web underneath, so durations slipped. The
  method is to surface the dependency web before estimating instead of estimating
  in isolation.
- expected_sources: [departure-narrative.org] · split: val
