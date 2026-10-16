---
id: 3
type: story
title: "Deploy the service to GCP via Terraform"
parent: none
covers: []
after: []
refined: false
hitl: false
risk: high
---

# Deploy the service to GCP via Terraform

## Description

Provision and deploy the FastAPI/DSPy service on GCP with Terraform: Artifact Registry for the container image, Cloud Run for the service, Secret Manager for keys, and a least-privilege service account for IAM.

## Acceptance Criteria

Verify: `terraform apply` yields a public Cloud Run URL where `GET /health` returns ok and `POST /chat` answers a real question with citations.

## Boundaries

- Must not change: the `/chat` contract or the AI core.

## References

- source — `gcp-deployment.md` (raw intake deleted 2026-10-14; harvested into this ticket in `529296a`)
- spec — `_bmad-output/initiative-janbot/spec-janbot/spec-janbot.md`, Open Questions (deployment/hosting target)
- architecture — `_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md`, Deferred (deployment & hosting)

## Notes

- Unknown: the hosting/deployment target is a long-standing spec Open Question; this proposes GCP Cloud Run and needs the decision recorded before it starts.
- Unknown: the anonymization/guardrails pre-deployment gate must be resolved before any real recruiter deployment.
- Open question: container base image, and how the vector index and API keys are supplied at runtime.
- **Incepted (2026-10-16) into `epic-gcp-deploy`** (initiative epic 8, Milestone 4) — this ticket's work is delivered by E1 (authenticated Cloud Run spike), E3 (go public) and E4 (Terraform + WIF). Do not re-plan it here. Deploy target settled by ADR-007; guardrails gate scoped by ADR-009 (both DRAFT, awaiting owner).
