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

A golden recruiter Q&A dataset is run through the DSPy pipeline under the locked deterministic snapshot, and each run records retrieval-accuracy, citation-correctness and faithfulness metrics in MLflow with the config that produced them. Optimization stages — `BootstrapFewShot`, then `MIPROv2` — are applied only when the prior stage's recorded metrics show a need, so the program is improved by evidence rather than by hand-tuning.

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
- Decision (2026-10-14, S5): single-source golden items are scored by containment (`expected ⊆ cited`), not exact-set equality. `ChatProgram` already refuses every citation outside the retrieved set, so precision against the corpus is structurally enforced; an exact-set rule could only penalise a legitimately retrieved related source. Measured at `top_k=4`: 18/19 items are answered from a mixed context. An optional `acceptable_sources` dataset key is deliberately deferred until measured precision shows a real signal. Entry 4 is amended to match.
- Decision (2026-10-14, tuning): the retrieval default moved to `JANBOT_TOP_K=4` (was 3); it is a knob for the optimization stages (entries 8/9) and is revisited once entries 3–4 produce measured evidence.
- Decision (2026-10-14, S6): the 5.1 seed's "why Rust" rationale is signed off as covered by the matching-engine item (item 4's expected answer already states the zero-allocation/Rust rationale); the model-modes question is restored as its own golden item (AD-5 is load-bearing and was otherwise unmeasured).
- Decision (2026-10-14, proof-map): the public proof map lives in the corpus **view** `views/work-profile/index.org` (a curated read-model, not an immutable object) and is **generated** to `public_profile_org/public-proof-map.org` so it is retrievable. It grounds two items — which projects are inspectable (with full URLs under their real owners) and which are not — and is the source for the public-reference allow-list (backlog 9). The golden dataset is now 26 items.
- Decision (2026-10-14, exception to the expected-answer contract): the "Tell me about yourself" item keeps the owner's composed intro **verbatim** as its expected answer — it is a voice-fidelity item, not a fact-lookup, and the intro is the right faithfulness reference for that question. This is a deliberate exception to the 5.2 "short factual" rule, made because the intro is the owner's original prose and giving JanBot a personal voice is worth it.
- Decision (2026-10-14, baseline — entry 7): the baseline manual program was evaluated over the 36-item dataset at the locked snapshot (MLflow run `190dded9`, `top_k=4`, `dataset_sha256=06dda167…`): answer_coverage 0.97, public_references 0.97, retrieval_accuracy 0.78, citation_correctness 0.77, citation_precision 0.70, faithfulness 0.46 (35/36 judged; one item refused via `FabricatedCitation`). Every quality metric leaves clear headroom.
- Decision (2026-10-14, optimization go/no-go — entry 7): **BootstrapFewShot is needed** (entry 8) — the manual baseline is the thing to beat on retrieval (~0.78) and faithfulness (~0.46).
- Decision (2026-10-14, judge model — entry 7): `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5` — a stronger, different-family judge than the `gpt-4o-mini` answerer, to reduce self-bias, routed through OpenRouter. (The `claude-3.5-haiku` name does not exist on OpenRouter; the current haiku slug is `anthropic/claude-haiku-4.5`.)
- Decision (2026-10-14, re-baseline — entry 7): re-ran the baseline with the chosen judge (MLflow run `9d2f0f96`, `judge_model=anthropic/claude-haiku-4.5`, `dataset_sha256=06dda167…`): answer_coverage 0.97, public_references 0.97, retrieval_accuracy 0.78, citation_correctness 0.77, citation_precision 0.70, faithfulness 0.66 (35/36 judged; the same one item refused via `FabricatedCitation`). The different-family judge is less harsh than `gpt-4o-mini` (0.46). This is the canonical baseline entry 8 compares against.
- Decision (2026-10-14, BootstrapFewShot — entry 8): compiled the program over the golden set (4 bootstrapped demos; `max_labeled_demos=0`; teacher = the locked snapshot), persisted it at `eval/compiled_fewshot.json` + an MLflow artifact, pinned by `JANBOT_PROGRAM_PATH`. Compiled run `4e315484` vs baseline `9d2f0f96`: citation_correctness 0.80 vs 0.77, citation_precision 0.74 vs 0.70, retrieval equal 0.78, faithfulness 0.60 vs 0.66. Citation coverage improved; **faithfulness slightly regressed** — the deterministic compile metric scorable only citation coverage, not faithfulness. Whether this is a net win is weighed at entry 9.
- Decision (2026-10-14, Goodhart — entry 8 review): the faithfulness drop was **predicted**, not luck — a citation-only compile metric buys citation coverage with faithfulness, exactly what the objective rewards. MIPROv2 would intensify that trade at $6–15. So entry **14** makes the compile metric **multi-objective** (citation coverage + faithfulness, weighted or judge-based) and entry 9 (MIPROv2) waits on it. GEPA with a Pareto front (instead of a single scalar) is a deferred alternative for a later round.
- Design (2026-10-14, metric model — from the entry-8 review): two principles. (1) A compile objective contains only **program-controlled** terms — `retrieval_accuracy` and `answer_coverage` are data-level and only add constant noise (why retrieval did not move in 5.8). (2) Every metric derives from the same per-item atoms — `retrieved_ok`, `cited_ok`, `cited_precision_i`, `faithful`, `declined`, `urls_ok` — under **one** `eligibility(item, outcome)` that excludes a correct refusal, so a refusal is not scored as an uncited/unfaithful answer once entry 13 lands. Denominators are recorded as `<metric>__n`. The metric set: `retrieval_accuracy`, `retrieval_mrr` (new, entry 15), `citation_correctness` (recall/containment; do not rename—it is in the S5 ruling), `citation_precision`, `faithfulness` (over answered+judged only), `public_references` (narrow to URL-citing items), and `refusal_pass_rate` / `spurious_refusal_rate` (entry 13). The registry gains an explicit `higher_is_better` (entry 16).
- Design (2026-10-14, train/val split — entry 17): compilation and evaluation must not share items, or "compiled vs baseline" is train-on-test (memorization, not generalization — finding 4). A per-item `split: train|val` marker on `GoldenItem` (loader fail-closed; `split=None` = all, backward compatible), a compile CLI that refuses any split but `train`, an eval CLI `--split {all,train,val}` (gate runs explicitly `val`), `split` and `trainset_size` in run params plus a split-manifest artifact, and a re-measured **val baseline** (the entry-7 all-36 baseline is not a gate reference). Small-n caveat recorded: with ~14 val items a ~0.13 σ gives a ~3-item noise floor, so 5.8's +1-item gain cannot pass — "breadth gates optimization"; a 3-fold variant (3×12) is the small-n alternative. The per-item field is one schema pass with entry 13.
- Design (2026-10-14, gate rule — entry 18): the optimization gate is **pre-registered** before the val re-runs, so a stage is judged against a committed rule, not a post-hoc threshold. On the val split (~14 items, p≈0.66) the noise floor 1.5σ≈0.19 (~3 items); a stage is accepted only when it improves a targeted metric beyond the noise floor without regressing the other beyond its own, and a within-noise change is "no decision". "Breadth gates optimization" (a ~5% effect needs val ≈ 100); a 3-fold variant is the small-n alternative.
