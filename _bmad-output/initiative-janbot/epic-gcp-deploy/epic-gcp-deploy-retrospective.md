---
epic: epic-gcp-deploy
date: 2026-10-21
verdict: rejected
criteria: declared
headless: false
---

# Retrospective — epic-gcp-deploy

## Epic summary

**Epic:** `epic-gcp-deploy` (Milestone 4 — deploy JanBot to GCP), folder
`_bmad-output/initiative-janbot/epic-gcp-deploy/`. Selected interactively by the owner.
**Criteria:** **declared** — the epic file carries `## Done when`
(`epic-gcp-deploy.md:31-38`).

### Tickets (from `tickets.py status epic-gcp-deploy`)

| ref | title | status | state | covers |
|---|---|---|---|---|
| 8.1 | Containerize and deploy an authenticated Cloud Run spike | done | done | E1 |
| 8.5 | Terraform core: Artifact Registry + Cloud Run + Secret Manager + remote state | **built** | **review** | E1.5 |
| 8.2 | Guardrails and cost protection | **built** | **review** | E2 |
| 8.3 | Go public: allow-unauthenticated + the GitHub Pages widget | — | planned | E3 |
| 8.4 | E4b — CI/CD (Workload Identity Federation + GitHub Actions) | — | planned | E4b |

- **Finished by the build rule, not called done:** 8.5 and 8.2 (`status=built`,
  `state=review`). Their state is recorded here and left unchanged — closing is
  `bmad-ticket`'s job, not the retrospective's.
- **Pending tickets (`pending_tickets`):** **8.3 (E3)** and **8.4 (E4b)**. The owner
  explicitly accepted retro-ing this unfinished epic and asked that both be recorded as
  pending tickets **they accepted proceeding over** — that acceptance is the owner's,
  dated **2026-10-21**, and is recorded here rather than treated as a verdict override.
- **Requirement source:** `initiative-janbot.md` §Done when; the epic's own
  `## Requirements` (`epic-gcp-deploy.md:23-29`) names E1, E2, E3, E1.5, E4b; capability
  ids `CAP-1`…`CAP-9` live in `spec-janbot/spec-janbot.md`.

### Ranges (per plan `baseline_revision`, ordered by ancestry)

| ticket | range | commits | note |
|---|---|---|---|
| 8.1 | `3927d71..a0b9b87` | 2 | plan baseline `3927d71`; next baseline `a0b9b87` |
| 8.5 | `a0b9b87..1eeb890` | 43 | **cut:** `1eeb890` is the last E1.5 commit; the 9 newer commits in the `a0b9b87..bf04023` baseline gap belong to `epic-evaluation` (PR #36). The range also contains interleaved `epic-evaluation` commits (ADR-010 T-series, eval runs) because the E1.5 baseline precedes them — per-file churn is not attributable to E1.5 alone. |
| 8.2 | `bf04023..HEAD` (`3a04152`) | 18 | inferred (last plan runs to HEAD); no later unrelated work landed |
| 8.3, 8.4 | none | — | no plan files exist (`find` names `story-go-public-…-plan.md` and `story-e4b-…-plan.md`; neither is in the folder) and no commits |

`git_evidence.py` reported `merge_count = 0` for all ranges; the branch is rebase-merged,
so SHAs are rewritten (`RUNBOOK.md:161-163`, `a5a3e54`).

### Evidence inventory

- **Epic file:** `epic-gcp-deploy.md` — Description, Outcome, Requirements, Done when,
  Boundaries, Notes (75 lines).
- **Entries:** `tickets.toml` (5 entries) + `tickets.py find` for 8.1/8.5/8.2/8.3/8.4.
- **Story files:** none (`find.story_file` is `null` for every ticket).
- **Plans:** `story-containerize-cloud-run-spike-plan.md` (status done, baseline `3927d71`),
  `story-terraform-core-plan.md` (status built, baseline `a0b9b87`, five review lenses
  recorded), `story-guardrails-and-cost-protection-plan.md` (status built, baseline
  `bf04023`, `quick` lens recorded). Plans for 8.3/8.4 are absent.
- **Runbooks/records:** `run-e1-deploy.md`, `run-e1.5-deploy.md`, `run-e2-guardrails.md`,
  `probe_over_claiming*.txt`, `spike-quota-counter*`; root `RUNBOOK.md`,
  `terraform/RUNBOOK.md`, `DECISIONS.md` (added 2026-10-21).
- **Session logs:** present for the epic's build dates —
  `.agent-shell/transcripts/2026-10-16-11-46-42.md`, `2026-10-16-11-47-43.md`,
  `2026-10-19-21-07-02.md`, `2026-10-19-21-07-10.md`, `2026-10-20-11-46-33.md`,
  `2026-10-21-14-08-37.md`, `2026-10-21-15-16-40.md`. The 00008 acceptance run was
  performed outside this repo's transcript set (recorded as Goose's apply in
  `run-e2-guardrails.md:143-145`).
- **Previous retrospective:** none — see Previous-retro follow-through.

## Findings

Sources are `file:line` in this repository at `3a04152`, a commit, or a log entry. The
diff-scope review lenses were run **inline on a narrowed scope**: the guardrail code was
independently reviewed and accepted on 2026-10-21 (commit `569cf4d`; the reviewer's
handoff), and the owner asked that its scope not be reopened. The lenses were therefore
applied to the epic's spec/acceptance/record surfaces and ticket boundaries only; the
guard's behaviour is not re-litigated here.

### F1 — The written acceptance criterion for control 5 is false as shipped (fix now)

`spec-janbot/decisions.md:89` (ADR-009 control 5 acceptance test) and
`epic-gcp-deploy/tickets.toml:38` (ticket 8.2 `verify`) both require, for
*"Would you like to work for our company?"*, that **"no first-person commitment/interest
assertion reaches the caller"** (ADR-009:89 says the question must be "refused by the
guard"; tickets.toml:38 says "no such assertion reaches the caller"). The same criterion
is restated in the E2 plan at `:56` (OVER-CLAIM row), `:102` (Given/Then) and `:160`
(Verification expectation), and the epic's `Done when` #2 depends on "every control has a
passing acceptance test" (`epic-gcp-deploy.md:34`).

Live, on revision `janbot-api-00008-86p` at **2026-10-21T13:44:13Z**, the answer to that
question was *"Yes. I'm interested in working somewhere that values freedom, commitment,
courage, and accountability…"* — a first-person interest assertion that reached the
caller. It is recorded in the runbook's own table (`run-e2-guardrails.md:161`) and quoted
in the residual note (`run-e2-guardrails.md:177-182`).

**Renegotiation check:** the acceptance text was **not** renegotiated anywhere. The only
reconciliation is a scope note under ADR-009 —
`decisions.md:97` "**Control-5 scope (2026-10-21):** ADR-010 **Amendment 4** narrows
control 5 to actionable commitments and named-company interest; generic
enthusiasm/politeness is served. This is the operative reading of
"commitment/interest" in control 5." — and the preceding line (`:96`) states that
ADR-009's text is unchanged. The ticket `verify` and the plan's acceptance/verification
lines were not touched. The fix lives in ADR-010 Amendments 4–5 and never reached the AC.

This is the finding the owner weighted first: a **shipped ticket whose own written
acceptance criterion is false**, with the correction in a later amendment. The action is
a **renegotiation of the AC text** (old → new, with a marker and attribution to the owner
decision ADR-010 A4/A5) — **not** a change to guard behaviour.

### F2 — Same-class scan: control 5 only among acceptance texts; three further non-AC drifts

Scope scanned: the five `verify` fields in `epic-gcp-deploy/tickets.toml` (8.1, 8.5, 8.2,
8.3, 8.4) and the seven `Acceptance test` lines in `spec-janbot/decisions.md`
(`:79`, `:80`, `:81`, `:82`, `:89`, `:90`, `:91`).

- **Acceptance texts contradicted by a later amendment: 2**, and both are the same
  control-5 criterion (`decisions.md:89`, `tickets.toml:38`). Every other `verify` and
  acceptance-test line is consistent with the current state: 8.1 (`tickets.toml:24`),
  8.5 (`:38` — evidenced by `run-e1.5-deploy.md:47-66`), 8.3/8.4 (unbuilt, nothing
  contradicts), controls 1–4, 6, 7 (`decisions.md:79-82,90-91`).
- **Non-AC drift found while scanning (not acceptance-test lines):**
  1. `decisions.md:79` (ADR-009 control 1 body) still says "the **91** golden questions";
     the dataset is **106** items (47 train / 59 val, 13 refusals) per
     `epic-gcp-deploy.md:71` (corrected 2026-10-20) and the 8.2 description in
     `tickets.toml`.
  2. `decisions.md:94` still says "**E4 owns the Firestore IaC**"; the owner override moved
     it to E2 — `epic-gcp-deploy.md:69` carries "(Superseded 2026-10-20: E2 owns it…)" and
     `epic-gcp-deploy.md:73` records the override. The ADR line is unchanged.
  3. `run-e2-guardrails.md:444` "**E3 (going public) stays blocked**" (00005-era
     consequence) is superseded by A4/A5 and the 00008 verdict
     (`run-e2-guardrails.md:211`) with no superseded marker — see F5.

So "control 5 only" is the answer for acceptance texts; there are **three more** stale
statements elsewhere (two in ADR-009's body, one in the runbook).

### F3 — The amendment arc left a measured class claim reading broader than its measurement (accept as-is; record the numbers)

The exact sentence is `decisions.md:84` (ADR-009 control 5):
**"What is already covered, by measurement (θ = 0.26 — the designed, deterministic pre-LM
gate): identity and commitment questions sit below θ and are declined before any LM
call — … 0.174/0.159; … 0.208/0.201; … 0.174/0.135; … 0.213/0.190; … 0.166/0.138
(two-best similarities; all < θ). So containment of those is a designed control, not
incidental."**

The measurement is **five probes** (three identity/contact, two compensation). "Identity
and commitment questions sit below θ" reads as a class claim. The live record contradicts
the class reading: on 00007, *"Can you start next month?"* — a commitment question —
reached the model (**10.7 s**) and was declined by the guard, not θ
(`run-e2-guardrails.md:129`). The same ADR already records the correction at
`decisions.md:86`: "the gate is precise, not robust" (0.2558 vs θ = 0.26). The shape is
the arc's: each iteration's headline generalises from the phrases it was built around.
Disposition: **accept as-is** (the fragility is recorded; the residual is owner-accepted);
a qualifier naming the five probes belongs on the next touch of ADR-009. No behaviour
change.

### F4 — The coverage table's category labels read broader than the probe count (accept as-is; record the numbers)

`run-e2-guardrails.md:357` — **"Measured coverage (probes in
`tests/test_output_guard_coverage.py`), full table:"** — followed by
"availability / start / notice | **3/3**", "accepting an offer | **1/1**",
"relocation | **1/1**" (mirrored at `decisions.md:247-251`). The measurement is one probe
per subcategory (3 total for the first row) and each probe is the lexicon's own phrase
(`tests/test_output_guard_coverage.py:18-31`). The only independent post-LM actionable
catch in the live record is 00007's *"Can you start next month?"*
(`run-e2-guardrails.md:129`); the 00008 actionable phrasings were all θ-declined pre-LM
(`run-e2-guardrails.md:161-165`), so no post-LM confirmation exists for availability,
notice, accepting or relocation. The residual paragraph names only compensation and
travel as gaps, which reads as completeness for the green rows. Disposition: **accept
as-is** (best-effort by owner decision); the table measures the probe set, not category
completeness. Recorded so later retros do not re-flag it as a defect.

### F5 — Evidence hygiene: additive correction left two superseded sections unmarked (fix now)

The document does self-correct in places, and well:

- `run-e2-guardrails.md:101` replaces the 00006 inference **in place** with the 00007 log
  facts and says so ("The earlier sentence … was an inference … The 00007 log facts
  supersede it").
- `run-e2-guardrails.md:135-136` links the 00007 re-check to the 00008 section.
- `epic-gcp-deploy.md:74` sets the convention: the superseded line is "**left intact and
  superseded, not edited**".

But two superseded statements remain unmarked and would be taken at face value by a reader
who enters at the 00005 section:

- `run-e2-guardrails.md:421` — the 00005 acceptance row: control 5 "**❌ FAILS**"; and
  `:440-444` — "### Consequence … **E3 (going public) stays blocked**". Neither points at
  A4/A5 or at the 00008 verdict (`:211`).
- `run-e2-guardrails.md:373-380` — "## Over-claiming evidence (ADR-010, control 5)" still
  asserts, from the 00005-era probe, that "**no first-person commitment/interest
  assertion reaches the caller**"; the 00008 section (`:161`, `:177-182`) records the same
  question answered with first-person interest. The plan repeats the stale expectation at
  `story-guardrails-and-cost-protection-plan.md:160`.

Disposition: **fix now** (documentation): add dated superseded markers pointing at
ADR-010 A4/A5 and the 00008 section; keep the historical rows.

### F6 — The cold-start measurement beside the `min-instances` decision omits the first *answered* request (fix now)

`decisions.md:63` (ADR-007 note) and
`story-guardrails-and-cost-protection-plan.md:154` say "the first request after deploy took
**~8 s**; later requests **0.95–10.7 s**". The 00008 record shows the first two **answered**
requests at **21.8 s** and **22.7 s** (`run-e2-guardrails.md:159-161`), with instance boot
~8 s and the model call accounting for the rest; `RUNBOOK.md:157` already states "first
request after a deploy takes 20+ s (instance boot ~8 s measured on `00008`)". The decision
note quotes the boot-only figure as the first-request cost. The owner decides
`min-instances`; the record must carry both figures. Disposition: **fix now** (record
precision, no behaviour change).

### F7 — Ticket state: 8.5 and 8.2 are `built`/`review`; 8.2 cannot close against its own `verify` (record)

Recorded from `tickets.py status epic-gcp-deploy`: 8.5 and 8.2 are `built`/`review`, not
done; 8.3 and 8.4 are `planned`. No state is changed here. Closing 8.2 before the AC
renegotiation (F1) would close it against a false criterion; that coupling belongs to the
owner and `bmad-ticket`.

### Aggregate views and other checks

- **Architecture delta:** the epic added the guardrail modules (`guardrails/cache.py`,
  `limits.py`, `lexicon.py`, `output_guard.py`, `build_cache.py`), `api/decline.py`,
  `api/observability.py`, `store/identity.py`, `store/embedding_model.py` and wired them
  through `api/main.py`. Imports checked: `guardrails/cache.py:25` imports
  `janbot.api.contract` (the shared port type) and `api/main.py:39-40` imports the
  guardrails — no cycle, no pipeline import inside guardrails. Checked and clean.
- **God-class / size growth:** largest code files at HEAD — `output_guard.py` 433 lines,
  `lexicon.py` 419 (data), `limits.py` 192, `cache.py` 186, `build_cache.py` 160. No file
  grew to a god-class across the epic. Checked.
- **Duplication map:** `RUNBOOK.md:5-7` deliberately links `terraform/RUNBOOK.md` instead
  of copying the deploy steps; it repeats the identity value (`RUNBOOK.md:62`) and the
  cold-start trap (`RUNBOOK.md:157`), which agree with the E2 record. The only divergence
  is F6, where the *decision note* is the narrower statement.
- **Pattern divergence:** new tests follow the existing pytest conventions; the store /
  ingest / pipeline separation is preserved. Checked.
- **Spec-to-implementation:** F1–F4. The guarantee that the D1/D2 base guard is outside
  8.2's diff range is **by design**, not a gap: the plan says the guard is "already-shipped
  … evidenced not re-implemented" (`story-guardrails-and-cost-protection-plan.md:24`).

## Behavior verification

Exercised end to end, with the source of each observation:

- **E1 (8.1):** authenticated `GET /health` = ok and `POST /chat` with citations; an
  unauthenticated request is not served — `run-e1-deploy.md`.
- **E1.5 (8.5):** the hand-made spike was destroyed, `terraform apply` ran from zero, and
  all 7 acceptance criteria were re-verified at the new URL; state remote and versioned,
  no secret value in state — `run-e1.5-deploy.md:47-66`.
- **E2 (8.2):** live checks on 00005 (2026-10-20), 00007 (2026-10-21T11:36Z) and 00008
  (applied 2026-10-21T13:22Z; checks 13:23–13:44Z) — `run-e2-guardrails.md:120-211`.
  Observed: the role question answered with **no decline line** on 00008; the
  control-5 question answered (F1/F5); θ declines logged as `cause=low-relevance`; no
  question/answer text in logs; the deployed index identity `b36feac2…` read out of the
  image.
- **Not exercised:** E3 and E4b (planned). The 00008 run did not produce a post-LM
  `commitment-claim` decline — all actionable phrasings fell below θ — recorded honestly at
  `run-e2-guardrails.md:172-176`; post-LM actionable evidence remains 00007 plus the unit
  and coverage tests.

## Previous-retro follow-through

The `epics` order in `tickets.py status` places `epic-ts-harness` immediately before
`epic-gcp-deploy`; its folder has **no** `epic-ts-harness-retrospective.md` and no ticket
rows. The most recent finished epic, `epic-evaluation`, also has **no**
`epic-evaluation-retrospective.md`. There was therefore **no previous retrospective file**
to follow through on — stated explicitly so a missing file is not read as "no outstanding
items".

## Action items

All items are **proposed, not applied** — the retrospective writes nothing to the ADRs,
tickets, plans or story files.

1. **Renegotiate the control-5 acceptance text (F1, F2).** Owner: owner (spec/ticket
   owner). Files: `decisions.md:89`, `epic-gcp-deploy/tickets.toml:38`, and the plan's
   `:56`, `:102`, `:160`. Renegotiate **old → new** with a dated `<renegotiated>` marker
   and attribute it to the owner decision **ADR-010 Amendments 4–5 (2026-10-21)**:
   - *Old:* "… is refused by the guard — no first-person commitment/interest assertion
     reaches the caller — while the control 'Have you used Clojure in production systems?'
     still answers with citations."
   - *New:* "… every ungrounded first-person **actionable commitment** (availability,
     start/notice, compensation, accepting an offer, relocation/travel) and every
     **party-attributed interest** (company/team/party reference) is refused by the guard;
     generic enthusiasm/politeness, topic interest and role interest are **served**
     (ADR-010 Amendments 4–5); 'Have you used Clojure in production systems?' still answers
     with citations."
   **No guard behaviour changes.**
2. **Reconcile the three stale non-AC statements (F2).** Owner: docs owner.
   `decisions.md:79` (91 → 106 items), `decisions.md:94` (E4 → E2 owns the Firestore IaC),
   `run-e2-guardrails.md:444` (E3-blocked consequence).
3. **Mark superseded sections in place (F5).** Owner: docs owner.
   `run-e2-guardrails.md:421` and `:440-444` (00005 control-5 row and Consequence) and
   `:373-380` (Over-claiming evidence); plan `:160`. Point them at ADR-010 A4/A5 and
   `run-e2-guardrails.md:143-211`; keep the history, per `epic-gcp-deploy.md:74`.
4. **Complete the cold-start measurement beside the decision (F6).** Owner: docs owner.
   Add the 00008 first-*answered*-request figures (21.8 s / 22.7 s), the ~8 s instance
   boot and the warm ranges to `decisions.md:63` and the plan's `:154`.
5. **Process lesson (F1–F6).** Owner: process owner. When an amendment changes what a
   control accepts, the same change must carry a `renegotiates:` list naming the acceptance
   lines it supersedes, and the AC text must be renegotiated in that change — an
   "operative reading" note is not a renegotiated AC. Evidence records must mark
   superseded sections in place rather than only appending newer sections (the epic file's
   own convention).

## Acceptance verdict

**Rejected** (machine verdict; criteria **declared**).

Evidence:

- **Unfinished tickets force the machine verdict:** `pending_tickets` = **8.3 (E3)** and
  **8.4 (E4b)** (`tickets.py status epic-gcp-deploy`). The owner accepted retro-ing over
  them (recorded in Epic summary, dated 2026-10-21); that acceptance does not override the
  verdict.
- **Done when #2 fails as written:** "every control has a passing acceptance test" cannot
  be true while control 5's written acceptance test is false as shipped (F1; live
  `00008` 13:44:13Z).
- **Done when #3 and #5 are pending** with 8.3 and 8.4. **Done when #1 and #4 are
  evidenced** (`run-e1-deploy.md`, `run-e1.5-deploy.md:47-66`). **Done when #6** (no
  `/chat`, AI-core, `store/` semantics change) is consistent with the recorded diffs and
  was not contradicted by the checks.
- **Ticket state:** 8.5 and 8.2 are `built`/`review`, not done (F7).

A human decision always overrides the machine verdict; none was given to accept the epic.

## Open questions

- Approve the exact new acceptance wording in Action item 1 (it rewords a signed-off
  ADR-009 acceptance test whose condition ADR-010 already closed).
- Mark the 00005 acceptance/Over-claiming-evidence material as superseded in place, or move
  it to a historical appendix?
- Tighten the θ sentence (F3) and the coverage-table reading (F4) now, or on the next
  touch of ADR-009? Neither changes behaviour.
- Close 8.2 only after the AC renegotiation lands?
