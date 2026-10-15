# Golden dataset — per-item class mapping (entry 5.21, 2026-10-15)

Mapping of all 38 `eval/golden_dataset.yaml` items to the ten-class failure
taxonomy (epic-evaluation Notes, 2026-10-15). Class by the question's intent;
multi-source (class 3) by construction when `expected_sources` has ≥ 2 entries.

| idx | split | class | class name | question |
|----:|-------|------:|------------|----------|
| 0 | train | 2 | narrative / arc | Can you walk me through your career path and what drove the transitions? |
| 1 | val | 5 | weakness / honest self-assessment | Why did you leave your last job after so many years there? |
| 2 | train | 4 | strengths / depth | Can you give a concrete example of mentoring or leadership impact? |
| 3 | train | 1 | fact lookup | Tell me about your matching engine project. |
| 4 | val | 4 | strengths / depth | Have you implemented spec-first testing end to end, not just talked about it? |
| 5 | train | 1 | fact lookup | Have you used Clojure in production systems? |
| 6 | val | 1 | fact lookup | Do you have full-stack experience? |
| 7 | train | 1 | fact lookup | What experience do you have with event-driven architecture? |
| 8 | train | 1 | fact lookup | Tell me about your AI agent project, JanBot. |
| 9 | val | 1 | fact lookup | What model modes does JanBot support and why? |
| 10 | train | 1 | fact lookup | What experience do you have operating and debugging CI/CD infrastructure? |
| 11 | train | 4 | strengths / depth | How have you designed a test automation architecture at production scale? |
| 12 | val | 1 | fact lookup | What Clojure work did you do at Red Hat? |
| 13 | train | 4 | strengths / depth | How deep is your Linux knowledge? |
| 14 | val | 1 | fact lookup | Do you have security or PKI experience? |
| 15 | train | 6 | stance / opinion | What is your testing philosophy? |
| 16 | train | 6 | stance / opinion | Which books or ideas have most shaped how you work? |
| 17 | val | 1 | fact lookup | How do you use AI in your day-to-day work? |
| 18 | train | 4 | strengths / depth | How does your personal productivity system demonstrate system design? |
| 19 | val | 10 | voice / intro | Tell me about yourself. |
| 20 | val | 6 | stance / opinion | What do you prefer - remote, onsite, or hybrid? |
| 21 | train | 1 | fact lookup | How do you keep an AI assistant from making things up? |
| 22 | val | 9 | attribution trap | Where can I find the source for the eDeposit AMQP/pdfbox worker? |
| 23 | val | 9 | attribution trap | Which of your projects can I inspect right now, and where? |
| 24 | train | 9 | attribution trap | Is there work of yours I can't verify publicly? |
| 25 | val | 3 | multi-source synthesis | You've been at this a long time - what can you bring that a younger engineer can't? |
| 26 | train | 4 | strengths / depth | What can you offer to junior colleagues? |
| 27 | train | 1 | fact lookup | What Linux services have you actually run in production? |
| 28 | train | 3 | multi-source synthesis | Do you have experience monitoring infrastructure? |
| 29 | val | 1 | fact lookup | Have you done Infrastructure as Code? |
| 30 | train | 2 | narrative / arc | Where did your approach to testing come from? |
| 31 | train | 1 | fact lookup | How do you design internal tools? |
| 32 | val | 2 | narrative / arc | Why Clojure? What led you to it? |
| 33 | train | 3 | multi-source synthesis | Where have you used Clojure in production and in testing? |
| 34 | train | 3 | multi-source synthesis | How has your thinking on asynchronous systems evolved over the years? |
| 35 | train | 3 | multi-source synthesis | Do you know Kubernetes? |
| 36 | val | 1 | fact lookup | What is JanBot for? |
| 37 | train | 1 | fact lookup | How do you review the work of an AI agent? |

## Class distribution (all 38)

| class | name | all | train | val |
|------:|------|----:|------:|----:|
| 1 | fact lookup | 16 | 9 | 7 |
| 2 | narrative / arc | 3 | 2 | 1 |
| 3 | multi-source synthesis | 5 | 4 | 1 |
| 4 | strengths / depth | 6 | 5 | 1 |
| 5 | weakness / honesty | 1 | 0 | 1 |
| 6 | stance / opinion | 3 | 2 | 1 |
| 7 | adversarial / false premise | 0 | 0 | 0 |
| 8 | refusal / out-of-corpus | 0 | 0 | 0 |
| 9 | attribution trap | 3 | 1 | 2 |
| 10 | voice / intro | 1 | 0 | 1 |
| | **total** | **38** | **23** | **15** |

## Grounding pressure (two reproducible numbers + union)

- **X — by construction** (val items in classes 3/5/7): **2** — item 25 (class 3), item 1 (class 5).
- **Y — empirically observed** (items whose faithfulness verdict moved between the
  reference `e635c2bf` and the lever runs, computed from the stored
  `run-*-output.txt` artifacts; no new run): 2.9 changed {14, 29}, 2.10 {19, 29},
  2.11 {14, 17, 19, 22, 29, 36} (item 29 turned *faithful* — a move in the good
  direction — while 14/17/19/22/36 regressed) →
  **{14, 17, 19, 22, 29, 36} = 6**.
- **Z — union**: {1, 14, 17, 19, 22, 25, 29, 36} = **8**.
- The two criteria are **disjoint**: the levers' grounding pressure landed on
  fact-lookup (14, 17, 29, 36), voice (19) and attribution (22) items — none on
  the taxonomy-predicted 3/5/7 classes. **Class labels do not predict grounding
  pressure.** What the data supports: every observed item is single-source, so
  pressure is not explained by source count either; the one concrete
  multi-subtree datum is 2.11's item 22 (dropping the second `edeposit.org`
  subtree cost its pdfbox answer). The general mechanism is not established by
  this audit.
