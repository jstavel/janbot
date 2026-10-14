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
- Waits on epic-rag-chat because: the decline changes the pipeline and contract that epic delivered.
- Decision (2026-10-14, sequencing): entry 1 is the **tracer bullet** — the thinnest decline path end to end (shape → contract → one decline through the port); entry 2 builds the real detection and the refusal-gate split on that shape. Entry 1 carries `plan_checkpoint` (the owner approves the decline shape before the pipeline work).
- Decision (2026-10-14, scope): E3 (the decline's determinism under the locked snapshot) is owned here, not by `epic-evaluation`; AD-5 governs it.
- Shared setup: the port test harness (pytest + httpx) is owned by `epic-rag-chat` (delivered); both entries' checks run through it.
