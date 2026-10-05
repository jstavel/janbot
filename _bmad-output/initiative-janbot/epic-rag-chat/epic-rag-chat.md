---
tracker_id: ""
key: ""
type: epic
title: "DSPy answer + citation pipeline via /chat"
parent: initiative-janbot
covers: ["CAP-1", "CAP-2", "CAP-3", "CAP-6"]
after: []
assignee: ""
risk: high
---

# DSPy answer + citation pipeline via /chat

## Description

A recruiter-style question posted to `POST /chat` gets an answer synthesized by a DSPy program that retrieves from the indexed public corpus and returns the source documents it used. The program is a `dspy.Module` with a *query → answer + citations* signature, starting from a manual prompt (no compilation — that is Milestone 2). Output is the Pydantic `ChatResponse`/`Citation` contract, validated at the API boundary. The model is selected by configuration: a locked deterministic snapshot at `temperature=0` for CI/eval, `openrouter/auto` for production.

## Outcome

A recruiter can ask a real question and receive an accurate answer with correct citations through the `/chat` JSON contract — the spec's CAP-1, CAP-2, CAP-3 and CAP-6.

## Requirements

- CAP-1: A recruiter can ask a natural-language question and receive an answer grounded in the owner's public documentation. (`spec-janbot.md`, Capabilities)
- CAP-2: Every answer names the source document(s) it was derived from. (`spec-janbot.md`, Capabilities)
- CAP-3: The service exposes a single `/chat` HTTP endpoint with a stable, machine-validated JSON contract (answer + citations). (`spec-janbot.md`, Capabilities)
- CAP-6: Two model modes — a locked deterministic snapshot for CI/evaluation and a flexible auto-routed mode for production. (`spec-janbot.md`, Capabilities)

## Done when

1. `POST /chat` with a real recruiter question returns an answer grounded in the indexed corpus.
2. Every response carries at least one citation naming the source document actually used; an uncited answer is rejected.
3. The response validates against the Pydantic `ChatResponse` contract; a malformed request is rejected with the standard error envelope.
4. The same query under the locked snapshot at `temperature=0` returns identical output across runs; switching to `openrouter/auto` requires only configuration.
5. No answer is produced from content outside `public_profile_org/`.

## Boundaries

`pipeline/`, `llm/` and `api/` — the DSPy program, the OpenRouter adapter/model-mode config, and the FastAPI route with its Pydantic contract. Not the ingestion/scope filter (`epic-ingestion`); not the end-to-end suite (`epic-verification`); not DSPy compilation or prompt optimization (Milestone 2). Consumes the index built by `epic-ingestion`.

## References

- parent — `../initiative-janbot.md`, section Requirements
- spec — `../spec-janbot/spec-janbot.md`, capabilities CAP-1, CAP-2, CAP-3, CAP-6
- architecture — `../architecture-janbot/architecture-janbot.md`, AD-1 (contract-first port), AD-2 (isolated core), AD-4 (Pydantic source of truth), AD-5 (model mode as config)
- constraint — `../spec-janbot/spec-janbot.md`, Constraints (determinism, Pydantic source of truth, baseline manual prompt)

## Notes

- Decision (2026-10-05, slicing): the pipeline and the `/chat` endpoint are one epic — the contract is an invariant (AD-1/AD-4), the work is one owner, and a pipeline without an endpoint is not demoable.
- Open question: the exact locked snapshot id (`gpt-4o-mini-2024-07-18` vs `claude-3.5-sonnet`) must be chosen for CI/eval; AD-5 binds the two modes, the concrete id is set at configuration.
- Unknown: whether the baseline manual prompt meets acceptable answer quality on the first pass, or a `BootstrapFewShot` step is pulled forward; the epic delivers the manual baseline regardless.
