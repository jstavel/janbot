---
tracker_id: ""
key: ""
type: epic
title: "A graceful insufficiency answer"
parent: initiative-janbot
covers: ["CAP-1", "CAP-3"]
after: []
assignee: ""
risk: high
---

# A graceful insufficiency answer

## Description

When a recruiter asks something the public corpus cannot answer — Kubernetes, salary, notice period — JanBot says so **in the same JSON contract** instead of returning a 5xx. The refusal gate splits: an explicit insufficiency reply is sanctioned, while a fabricated *cited* answer is still refused. The hard part is detection — deciding "not answerable from the public corpus" when retrieval always returns something.

## Outcome

An out-of-corpus question gets a graceful, contract-conforming "not in my public profile" reply; in-corpus questions still answer with citations — so the grounding promise holds without surprising failures.

## Requirements

- E1 (CAP-3): the `/chat` contract defines how an insufficiency reply is expressed — the Pydantic shape, and how `citations` behaves on a decline. (`spec-janbot.md`, CAP-3)
- E2 (CAP-1): the pipeline declines gracefully when a question is not answerable from the corpus, and still refuses a fabricated cited answer. (`spec-janbot.md`, CAP-1; `architecture-janbot.md`, AD-2)
- E3 (CAP-3): the decline is deterministic enough to evaluate under the locked snapshot. (`spec-janbot.md`, Constraints; `architecture-janbot.md`, AD-5)

## Done when

1. An out-of-corpus question (e.g. Kubernetes, salary) returns a contract-conforming insufficiency reply through `POST /chat` — not a 5xx.
2. An in-corpus question still returns a cited answer; a fabricated cited answer is still refused.
3. The decline shape is pinned by Pydantic and the derived OpenAPI (zero drift).
4. The decline path is covered by tests through the port.

## Boundaries

`api/` and `pipeline/` — the reply shape, the detection, and the refusal-gate split. Not the eval metrics or golden items (`epic-evaluation`), not ingestion, not deployment.

## References

- parent — `../initiative-janbot.md`, section Requirements
- spec — `../spec-janbot/spec-janbot.md`, capabilities CAP-1, CAP-2, CAP-3 and section Constraints
- architecture — `../architecture-janbot/architecture-janbot.md`, AD-1 (contract-first port), AD-4 (Pydantic source of truth), AD-5 (model mode as config)
- decision — `../spec-janbot/decisions.md` (a new ADR may be needed for the decline shape)

## Notes

- Decision (2026-10-14, from the golden-dataset brainstorm): the owner wants a **graceful decline**, not hard 5xx refusals, for questions the public corpus cannot answer.
- Source conflict: CAP-2 says "an answer with no citations is rejected", and CAP-3's success implies every response carries citations — a decline carries none. This epic needs a **spec touch-up** (a decline is not an "answer" in the CAP-2 sense) and possibly an ADR for the decline shape; offer `bmad-spec` / `bmad-architecture`.
- Unknown: how "not answerable" is detected — a prompt-level instruction, a retrieval relevance threshold, or a classifier; entries wait on it.
- Unknown: the exact contract shape (empty `citations` allowed on a decline, a `status` field, or a distinct response type); entry 1 settles it with the owner.
- Decision (2026-10-14, decline shape): a decline is a `ChatResponse` with `status: "answered" | "insufficient"` — citations are required when `answered` and may be empty when `insufficient`; the decline returns **HTTP 200**, leaving 5xx for genuine failures. Chosen over empty-citations-only (callers cannot distinguish) and a distinct response type (union overhead for the Zod harness). This shape is what `epic-evaluation` entry 13 detects.
- Waits on epic-rag-chat because: the decline changes the pipeline and contract that epic delivered.
- Decision (2026-10-14, sequencing): entry 1 is the **tracer bullet** — the thinnest decline path end to end (shape → contract → one decline through the port); entry 2 builds the real detection and the refusal-gate split on that shape. Entry 1 carries `plan_checkpoint` (the owner approves the decline shape before the pipeline work).
- Decision (2026-10-14, scope): E3 (the decline's determinism under the locked snapshot) is owned here, not by `epic-evaluation`; AD-5 governs it.
- Shared setup: the port test harness (pytest + httpx) is owned by `epic-rag-chat` (delivered); both entries' checks run through it.
- Decision (2026-10-15, entry 2 — detection method chosen by MEASUREMENT): candidate **(b) retrieval relevance threshold** is adopted. A deterministic no-model probe first (`run-7.2-theta-probe.txt`; best top_k=4 cosine similarity per val item) showed salary **0.232** and notice-period **0.2528** sit **below every in-corpus item** (lowest **0.2787**, the voice/intro item), so a θ ∈ (0.2528, 0.2787) declines salary+notice with `spurious_refusal_rate` 0.0; the managed-Kubernetes item scores **0.5111**, and **nine** of the fifteen in-corpus items sit below it — so **no θ declines the Kubernetes item without also declining nine in-corpus items** (three more than the first draft of this note recorded). The keyed run at **θ = 0.26** (locked snapshot; MLflow `bc1b2f55`) confirmed: **`refusal_pass_rate` 0.333 → 0.667 (+1 item) with `spurious_refusal_rate` 0.0**, and **every in-corpus metric identical to `9c7260da`** (citation_correctness / faithfulness / retrieval_accuracy 0.7333 ×3, n=15). The decline is a **new `LowRelevance` signal** mapped to the identical `insufficient` reply (API **and** the 5.13 eval runner mapping), so the shape is production-identical; the gate is embedding-driven and runs before the LM call. **E3 verified**: a second identical run (`54b67a9f`) declines the same two items (`refusal_pass_rate` 0.667, `spurious_refusal_rate` 0.0). Candidate **(a)** (prompt-level) was **not measured** — it was ordered second (its outcome is not model-independent) and (b) met the criterion, so it was not run; candidate **(c)** (classifier) likewise not run.
- Caveat (2026-10-15, entry 2 — n=3 power): `refusal_pass_rate`'s population is **3 val items**, so the +1 item is exact but a coarse sample of the out-of-corpus population — the same "breadth gates" limit as the gate at n=15, only coarser. The win is therefore **directional, not decidable**; a decidable one needs entry 20 to grow class 8 (golden items are `epic-evaluation`'s boundary, not 7.2's). The store change (exposing the discarded Chroma top similarity as a `similarity` key) is a **store-owned extension** (epic-ingestion), useful beyond 7.2 (the deterministic probes, the per-source cap, the embedder swap). The **Kubernetes/EKS item remains uncaught by a relevance gate** because its topic is corpus-adjacent (the `openshift-kubernetes-bridge.org` object, similarity 0.511) — the item may be **ill-posed** (the corpus does discuss Kubernetes vocabulary) or need candidate (a); flagged for entry 20's class-8 authoring.
- Adoption (2026-10-15, entry 2): the measured **θ = 0.26** is **adopted as the shipped default** (`DEFAULT_RELEVANCE_THRESHOLD = 0.26`) — the epic's done-when ("an out-of-corpus question returns a contract-conforming insufficiency reply") is delivered by the default, not behind a knob. Recorded caveats: the win is **directional (n=3)** — a decidable one needs entry 20 to grow class 8; the threshold is corpus- and embedder-specific (MiniLM cosine) and remains tunable; the **Kubernetes/EKS item remains uncaught by a relevance gate** because its topic is corpus-adjacent (the `openshift-kubernetes-bridge.org` object, similarity 0.5111) — the item may be **ill-posed** (the corpus does discuss Kubernetes vocabulary) or need candidate (a); flagged for entry 20's class-8 authoring. The store change (exposing the discarded Chroma top similarity as a `similarity` key) is a **store-owned extension** (epic-ingestion), useful beyond 7.2.
- Margin audit (2026-10-15, entry 2 — the shipped θ bounded by the FULL in-corpus population): the deterministic probe was extended to every in-corpus item in the golden dataset (`run-7.2-theta-probe-incorpus.txt`; 38 items, train + val). **The true minimum is 0.2787 (item 19, the voice/intro item, val) — margin to θ=0.26: +0.0187, thin, resting on that one item; 0 items sit below θ.** The θ band is pinned from both sides: below by the notice-period refusal item (0.2528 — θ must stay above it or the decline is lost) and above by item 19 — the band is only 0.0259 wide, and θ=0.26 is deliberately biased toward the false-decline-safe side (a false decline of a legitimate in-corpus question is the worst UX and contradicts the grounding promise). **Lowering θ further is blocked** by the notice-period pin, so no default change is made; the recorded follow-up is a **second guard** (e.g. requiring the second-best similarity to also fall below θ, or a lexical cross-check) if a future legitimate item lands inside the band. Item 19 itself is the watch item: a false decline there would cost the profile's showcase answer.
- Val evidence (2026-10-16, entry 7.3 — the keyed val run, the unified decline + `reason` metadata): MLflow `3f34c5a2` (artifact `run-7.3-decline-reason-val.txt`, 54 val items). `refusal_pass_rate` **1.0000 (n=10)**, `spurious_refusal_rate` **0.0000 (n=43)**; the renderer prints **exactly 10** `decline: <q> — personal` lines and **0** `— out_of_corpus`, with 0 refusal failures. Every in-corpus metric is **bit-identical** to reference `c6ced445` (9/9, +0.0000 each, including faithfulness) at the same dataset SHA `1c3864bd…`. The reason classification is deterministic (no model call), so the section stays green while the human-visible decline text is unified. Verified by querying `mlflow.db` directly.
- Caveat (2026-10-16, entry 7.3 — topical branch measured only by construction): as recorded in the plan (Q1=A), the val set holds **no topical refusal item** (managed-Kubernetes was dropped as ill-posed), so `out_of_corpus` is proven by unit tests and the fail-open default, not by a measured val item — deferred to entry 20's class-8 authoring.
