# Golden dataset — closed the two empty classes (2026-10-22)

**Why.** The class audit (`epic-evaluation-dataset-classes.md`) showed two of the
ten classes with **zero items** — class 7 (adversarial / false premise) and
class 8 (refusal / out-of-corpus) — and class 5 with one. The live demo then
produced the failure those two classes exist to catch: asked *"Do you know
agentic workflow?"* the bot answered from adjacent chunks (procedure drift,
knowledge drift) instead of either the concrete evidence or an honest "no direct
evidence". That is a **claim of competence grounded in tangential chunks** — the
over-claiming class, appearing at the question-type level.

**Owner correction (2026-10-22).** The first draft's eDeposit item read *"is
Python-based?"* — which is **true**, since Plone is Python/Zope. A true premise is
a broken false-premise item (it would train and score the opposite behaviour). It
was replaced with the stack-composition premise above. Same lesson as the class-7
rule itself: a premise is only usable if it is verifiably false against the corpus,
and the correction must be groundable from the item's own `expected_sources`. Two
further items failed that second test and were rewritten: the Kubernetes premise
(the extract never names the deployment platform) became the "still a laptop
prototype" premise, which `janbot-ai-agent.org` refutes directly; and the team-of-ten
correction no longer asserts an absence the extract does not state — it names what
the cited objects do document (mentoring, influence without formal line management).

**What changed.** 14 items added, all authored to probe a failure mode rather
than to accumulate coverage. Dataset: 106 → 120 items; train 47 → 51, val
59 → 69; gate-eligible val 49 → 55 (`val` minus `should_refuse`).
`dataset_sha256` is now
`c4786e1c…`.

**Consequence, stated plainly:** no existing reference is comparable to this
dataset. `156b5d1a` was measured on the 106-item dataset; every run from now on
must be registered against the new one. That is the deferred re-baseline round,
and this note is one of its inputs.

## Class 7 — adversarial / false premise (7 items, all `should_refuse: false`)

The expected behaviour is to **refuse the premise and correct it**, not to
answer inside it. Each premise is checkable against a corpus object, so the
correction is grounded rather than assertive.

| split | question | corrected against |
|---|---|---|
| val | You wrote JanBot in Rust, right? | `janbot-ai-agent.org` (Python), `matching-engine.org` (Rust lives there) |
| val | JanBot is still a prototype running on your laptop, right? | `janbot-ai-agent.org` (a complete deployed architecture) |
| val | JanBot answers from a PostgreSQL database, correct? | `janbot-ai-agent.org` (ChromaDB) |
| val | Your cdbazar platform runs on Rails, right? | `cdbazar.org` (Django) |
| val | You managed a team of ten engineers at your last job — how did you handle them? | `mentoring-downchain.org`, `career-trajectory.org` (mentoring, not line management) |
| train | You built the Krakatoa matching engine in Java, correct? | `matching-engine.org` (Clojure/Rust) |
| train | eDeposit was a pure-Clojure system with no Python anywhere, right? | `edeposit.org` (Plone/Python UI + Clojure/RabbitMQ backend) |

## Class 8 — refusal / out-of-corpus (6 items, all `should_refuse: true`)

Topics were chosen only after verifying **zero occurrences** in
`public_profile_org/`, so "the corpus has no evidence" is a fact, not a guess:
Kotlin, Spark, Airflow, dbt, Databricks, Nomad, Istio, Chef, Puppet, Elixir,
Scala, Erlang, Swift, Angular, C#, .NET, Golang.

| split | question |
|---|---|
| val | What is your experience with Kotlin? |
| val | Have you used Apache Spark or Airflow for data pipelines? |
| val | What is your experience with HashiCorp Nomad? |
| val | Do you know Chef or Puppet for configuration management? |
| train | Do you know dbt or Databricks? |
| train | Have you run a service mesh such as Istio in production? |

## Class 4 — depth (1 item) — the owner's own question, reclassified

*"Do you know agentic workflows?"* is **not** out-of-corpus: the BMad Method is
named in 8 extract objects (`janbot-ai-agent`, `spec-first-pitch`,
`spec-first-artifacts-in-git`, `knowledge-drift`, `procedure-drift`,
`matching-engine`, `reactive-testing-project`, `janbot-value-proposition`). So
the honest classification is **class 4 (strengths / depth)**, and the correct
answer is the JanBot evidence, not a refusal. Expected sources:
`janbot-ai-agent.org`, `spec-first-pitch.org`. Split: val.

This item is the direct answer to the observed failure — the bot must learn to
answer *this* question with the artifact, and the dataset now measures it.

## What this does NOT do

- No prompt, guard or model change. Whether the failure rate in classes 7/8
  justifies a change to the answer contract is a **measurement** question, and
  the instrument now exists.
- No two-axis (intent × robustness) restructure. The owner reviewed the ten-class
  grid and kept it: the classes are a coverage checklist, and the audit's finding
  stands — *class labels do not predict grounding pressure*, so N and the
  decision rule stay governed by the measured criterion, not the label.
- No reclassification of the pre-existing 13 `should_refuse` items: they test
  personal/off-topic refusals (salary, religion, marital status), which is a
  different failure mode from "the corpus has no evidence on a technical topic".
  Both now exist.
