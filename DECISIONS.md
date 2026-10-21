# DECISIONS.md — derived index over the ADRs

> **This file is a read model, not a source of truth.**
> Authority: [`_bmad-output/initiative-janbot/spec-janbot/decisions.md`](_bmad-output/initiative-janbot/spec-janbot/decisions.md) — the ADRs are the write model.
> When this file and an ADR disagree, **the ADR wins and this file is wrong.**
> What it answers: *which decisions bind this project, what state are they in, and where do I read the reasoning?*
> It does **not** carry the reasoning. That lives in the ADR, reached through the pin.

## Contract

- **`id` is the ADR id.** No second numbering, ever: a second identity is a mapping table, and a mapping table is drift.
- **`pin` is mandatory**: `<path>@<commit>:<line>`. A row without a pin does not hold; delete the row rather than fix the pin from memory.
- **`verified` is the only human-owned column.** Everything else is derived and regenerable; on regeneration `verified` is **never** overwritten. It records *"the owner has re-checked that this row still says what the ADR says"* — nothing else.
- **A decision with no ADR does not appear in the bindings table.** The gap is the metric — see §Gap.
- **On conflict the ADR wins.** This file is never edited to disagree with an ADR; the ADR is amended instead.

### Regeneration — NOT IMPLEMENTED (open item)

There is no generator yet. Until there is:

- this file is **hand-maintained**, and
- the acceptance criterion *"a regeneration produces a diff only in the `verified` column"* is **not satisfied**.

Do not treat this file as derivable. The blocker is stated rather than hidden: the ADRs carry their reasoning as prose, so the judgment columns cannot be derived mechanically. A generator can only ever emit `id`, `title`, `status`, `date` and the pin — everything else is judgment.

### Deliberate deviation from the plan's example table

`~/org/projects/drift-closing-plan.org` sketches columns for *rejected alternative / reason / what breaks / blast radius*. They are **not** here, on purpose: those are prose judgments, so putting them in the index would make the index a second write model — the exact failure the plan warns about. They stay in the ADR, reached through the pin.

If they are wanted here, the ADRs must first carry a machine-readable triple (`Decision:` / `Rejected:` / `Breaks:` on one line each). That is a change to the ADR format, not to this file.

## Bindings — every ADR that exists

| id | decision (ADR title) | status | pin | verified |
| --- | --- | --- | --- | --- |
| ADR-001 | LlamaIndex + ChromaDB as RAG base | **SUPERSEDED** by ADR-002 | `spec-janbot/decisions.md@a5a3e54:5` | — |
| ADR-002 | Revise AI stack — DSPy as core pipeline, MLflow for evaluation | ADOPTED 2026-10-04 | `spec-janbot/decisions.md@a5a3e54:11` | — |
| ADR-003 | Clojure orchestrator | **FUTURE** (not in force) | `spec-janbot/decisions.md@a5a3e54:22` | — |
| ADR-004 | Model routing — deterministic for CI/eval, auto for production | **PROPOSED** 2026-10-05 | `spec-janbot/decisions.md@a5a3e54:28` | — |
| ADR-005 | Milestone 1.5 re-scope — thin TS harness, reactive-testing deferred | **PROPOSED** 2026-10-13 | `spec-janbot/decisions.md@a5a3e54:37` | — |
| ADR-006 | Metric selection — construct orthogonality from the failure taxonomy | ADOPTED 2026-10-15 | `spec-janbot/decisions.md@a5a3e54:45` | — |
| ADR-007 | Deployment & hosting target — GCP Cloud Run (EU) + Artifact Registry + Secret Manager | ADOPTED 2026-10-16 | `spec-janbot/decisions.md@a5a3e54:54` | — |
| ADR-008 | A second public interface — the GitHub Pages widget + CORS | ADOPTED 2026-10-16 | `spec-janbot/decisions.md@a5a3e54:64` | — |
| ADR-009 | Minimum guardrail layer — the pre-recruiter-deployment gate | ADOPTED 2026-10-16, **CONDITIONAL** (condition closed by ADR-010) | `spec-janbot/decisions.md@a5a3e54:73` | — |
| ADR-010 | Deterministic output-level guard against fabricated citations and over-claiming | ADOPTED 2026-10-19 | `spec-janbot/decisions.md@a5a3e54:97` | — |

Path prefix for every pin: `_bmad-output/initiative-janbot/`.

## Gap — decisions that bind but have no ADR

This is a **metric**, not a record: it names the hole and where the decision currently
lives. The decisions themselves are not restated here (that would make this file a write
model).

Pins are deliberately absent for rows whose work is on an unmerged branch: this repo does
not pin an unmerged SHA, because a rebase-merge rewrites it and a rewritten pin is a
falsified one. Pin after the merge.

| subject | why it is a gap | where it lives now |
| --- | --- | --- |
| Reversibility of "Terraform owns the image" (option (c)) | **ADR candidate.** The reversibility claim was the justification for adopting option (c); it turned out false and was corrected. A decision whose rationale was falsified deserves a dated record, not only a plan design note. | `epic-gcp-deploy/story-terraform-core-plan.md` §Design Notes — branch `m4-e15-closeout-review-fixes` (unmerged) |
| Durable rollback: `keep_remotely`, `create_before_destroy`, per-sha tags, 30-day horizon | **ADR candidate.** A stated guarantee with a stated horizon — "what we promise" rather than "how we build it". | same plan + `terraform/README.md` — unmerged |
| Secret replication inside `europe-central2` | **Fold into ADR-007**, not a new ADR: it is a consequence of the recorded region claim that was not previously enforced. | unmerged round |
| `registry_auth` block with a path, no token | Mechanically forced by provider behaviour; recorded as a `<renegotiated>` marker inside the plan's frozen block. No ADR: it is not a choice. | plan marker — unmerged |
| Secret version stays out-of-band (no `google_secret_manager_secret_version`) | Boundary already stated in the plan's frozen `Always`; rejected as a finding (A5). ADR-worthy only if it ever becomes contested outside this plan. | plan frozen block |
| Round scope / sequencing (which fix groups now, which deferred) | Epic-level sequencing, not architecture. Lives in tickets. | `epic-gcp-deploy/` — unmerged |
| Tag scheme = per-sha | Implementation detail of the rollback decision above. | `terraform/main.tf` — unmerged |

## What this file is not

- Not a changelog — git and the ADRs carry history.
- Not a rationale store — that is the ADR's job, and duplicating it here guarantees divergence.
- Not a task list — that is the tickets' job.
- Not a place to record a decision that has no ADR. If a decision matters enough to be
  listed, it matters enough to be an ADR first.
