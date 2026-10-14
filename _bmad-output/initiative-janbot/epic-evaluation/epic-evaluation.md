---
tracker_id: ""
key: ""
type: epic
title: "Evaluation harness & cost-staged optimization"
parent: initiative-janbot
covers: ["CAP-8"]
after: []
assignee: ""
risk: high
---

# Evaluation harness & cost-staged optimization

## Description

A golden recruiter Q&A dataset is run through the DSPy pipeline under the locked deterministic snapshot, and each run records retrieval-accuracy, citation-correctness and hallucination metrics in MLflow with the config that produced them. Optimization stages — `BootstrapFewShot`, then `MIPROv2` — are applied only when the prior stage's recorded metrics show a need, so the program is improved by evidence rather than by hand-tuning.

## Outcome

The pipeline's answer quality is measured against a fixed dataset and improved by recorded, cost-staged optimization — the spec's CAP-8.

## Requirements

- E1 (CAP-8): A golden dataset of recruiter questions with expected answers and sources. (`spec-janbot.md`, Capabilities CAP-8; `roadmap.md`, Milestone 2)
- E2 (CAP-8): Metrics — retrieval accuracy, citation correctness, and hallucination detection via LLM-as-a-judge. (`spec-janbot.md`, Capabilities CAP-8)
- E3 (CAP-8): MLflow tracking records each run's config and metrics so runs are comparable. (`roadmap.md`, Milestone 2; `architecture-janbot.md`, Deferred)
- E4 (CAP-8): Cost-staged prompt optimization — manual → `BootstrapFewShot` → `MIPROv2`, each stage only if the prior shows a need. (`spec-janbot.md`, Constraints; `decisions.md`, ADR-002 addendum)
- E5 (CAP-8): The eval runs under the locked snapshot at `temperature=0` so metrics are comparable. (`spec-janbot.md`, Constraints; `architecture-janbot.md`, AD-5)

## Done when

1. A version-controlled golden dataset of recruiter questions with expected answers and sources exists.
2. Running the eval emits per-question and aggregate retrieval-accuracy and citation-correctness metrics.
3. Hallucination is measured by an LLM-as-a-judge over the golden answers.
4. Every run is recorded in MLflow with its config (model, snapshot, temperature, seed) and its metrics.
5. The eval is deterministic under the locked snapshot — repeated runs report the same retrieval and citation metrics — and any optimization stage (`BootstrapFewShot` then `MIPROv2`) is applied and recorded only when the prior stage's recorded metrics show a need.

## Boundaries

A new `eval/` module, the MLflow tracking setup, the golden dataset, and the compilation/optimization of the DSPy program. Not the pipeline's runtime behavior delivered in Milestone 1 (only the thing measured), not the test layer, not deployment. Consumes the running `/chat` pipeline and index from `epic-rag-chat` / `epic-ingestion`.

## References

- parent — `../initiative-janbot.md`, section Requirements
- spec — `../spec-janbot/spec-janbot.md`, capability CAP-8 and section Constraints
- roadmap — `../spec-janbot/roadmap.md`, Milestone 2
- architecture — `../architecture-janbot/architecture-janbot.md`, AD-5 (model mode is configuration)
- decision — `../spec-janbot/decisions.md`, ADR-002 addendum (cost of DSPy optimization)

## Notes

- Decision (2026-10-14, slicing): Milestone 2 is one epic — CAP-8 is one capability, one owner, and evaluation and optimization are one loop (you cannot decide an optimization stage without the recorded metrics).
- Decision (2026-10-14): the LLM-as-a-judge is a separate config-driven model (`JANBOT_JUDGE_MODEL`), defaulting to the locked snapshot; a stronger judge is a config change, not code.
- Decision (2026-10-14): MLflow runs on a tracking server with a config-driven `MLFLOW_TRACKING_URI`, not a bare local file store. The backend is SQLite (`sqlite:///mlflow.db`) with a local `mlflow-artifacts/` directory; both are gitignored.
- Decision (2026-10-14): the golden dataset lives at `eval/golden_dataset.yaml`, version-controlled; each item carries a question, an expected answer and expected sources.
- Decision (2026-10-14, sequencing): entry 1 is the tracer bullet — the thinnest path from the seed dataset through the pipeline into a recorded MLflow run. Entries 3/4/5 run in parallel because entry 1 owns the metric-registration interface and each metric is its own module; entry 6 completes run records, entry 7 records the baseline and the optimization decision, entries 8/9 are the gated optimization stages; entry 10 is the closing refactor sweep and entry 11 the closing end-to-end suite.
- Decision (2026-10-14): entry 9 (the `MIPROv2` stage, $6–15) carries `plan_checkpoint` for an unattended run.
- Decision (2026-10-14, from the 5.1 walkthrough): the compiled program from the optimization stages (entries 8/9) is a durable asset — persist it as an MLflow artifact and pin it by config, rather than recompiling on every run. Entries 8/9 own persisting it; entry 6's run records reference it.
- Decision (2026-10-14, from the 5.1 walkthrough): the judge model (entry 5) routes through OpenRouter too, so all model calls share one provider and one invoice; `JANBOT_JUDGE_MODEL` defaults to the locked snapshot.
