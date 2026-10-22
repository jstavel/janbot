---
title: 'Re-baseline round — extract procedure, index, pre-registered gate, new reference, cache, deploy'
type: 'feature'
ticket: ''
created: '2026-10-22'
status: 'in-progress'
baseline_revision: '63a55cf'
route: 'full'
route_source: 'auto'
risk: 'high'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** three layers diverge — the `~/org` view (`339359e`: five re-filings, new Mentoring/Career sections, four project subsections) is ahead of the extract (59 objects, old structure), the dataset (120 items, `c4786e1c…`) is ahead of the baked cache (`a8bd69dc…` — the image build refuses it), and the live demo cannot cite the objects that describe the actual agentic work. The previous re-extract's only trace is a commit message.

**Approach — the task's dependency chain, one corpus state:**
1. **The extract becomes a script** (`tools/extract_public_profile.py`): parse the view's `[[id:…]]` selection → per object: byte-copy the object file (extract filename = the object's internal filename; `:ID:` preserved) or, for a Czech object, emit the versioned English translation from `tools/extract_translations/` with **injected `:SOURCE-ID:`/`:SOURCE-SHA256:` pins** (sha256 of the object file at the pinned commit — the translation artifact never carries a hand-written pin); emit the two generated sections from the view (thesis map: thesis blocks only, `***`→`##`, `[[id:X][label]]`→label / `[[id:X]]`→X, fixed title line; proof map: fixed header template + bullets with `[[slug]]`→"the slug" + fixed closing paragraph); emit `MANIFEST` (commit pin, count line matching reality, sorted per-file sha256, excludes itself). A `--check` mode regenerates to a temp dir and requires byte-equality. A Czech `:TITLE:`/`:SYNOPSIS:` without a translation artifact is a hard error — no silent Czech in the extract. **Validation fixture:** run the emission against the `05b11a7` view and require byte-equality with the current extract files (the transforms must reproduce the last round exactly).
2. **Extract regenerated at pin `339359e`** — **62 objects (the view's full selection) + the two generated sections = 64 content files**; MANIFEST records the pin and per-file sha256. **Owner decision (2026-10-22): the task's "61 objects / 63 files" is corrected to 62/64 and the correction is recorded as a finding** — the task's count was derived from the stale extract's inventory instead of from the view, and a faithful extract must follow the view, not the previous extract. The round note names the pattern: this is the **third stale-pointer-class error in this round's inputs** (`c6ced445` from memory, the eDeposit false-premise item, now the extract inventory count) — the fix is the same in all three: **derive numbers from the current artifact, never from memory or from the previous state**.
3. **Index rebuilt** from the new extract; chunk count recorded; `out_of_scope_sources` passes at startup; no chunk cites a source the extract lacks.
4. **Gate re-registered BEFORE measuring** — gate-eligible **n = 55** (val 69 − 14 `should_refuse`, verified); the 1.5σ formula at the outgoing reference's own p projected to n=55 gives **citation_correctness accept ≥6 / regress ≤5** (5/55 = 0.0909 ≤ 0.0948) and **faithfulness accept ≥4 / regress ≤3** (3/55 = 0.0545 ≤ 0.0554 — exactly the noise-carry the task warns about); frozen as a new pre-registration in `gate-rule.md` (principle untouched: 1.5σ, symmetric floor, populations, metrics); the owner signs the pre-registration before the reference run.
5. **New reference measured** on the 120-item dataset (eval mode, locked snapshot, judge pinned `anthropic/claude-haiku-4.5`), registered in `gate-rule.md` (run id, config, n=55), artifact `run-<id>-output.txt`; `156b5d1a`/`c6ced445` stated historical (older corpus/dataset/population); round note written; DECISIONS.md touched only if a pin drifts (it is a read model over ADRs; a reference re-registration is not an ADR change).
6. **Cache regenerated** (one production run per `RUNBOOK.md` §4) → `cache/answers-<run>.json`; the Containerfile's `--source` repointed; `build_cache` validates the new dataset sha + corpus tree sha + the corpus commit pin (the extract commit must exist first).
7. **Deploy:** verified `terraform plan` (image via src+cache+Containerfile triggers, `JANBOT_RATE_LIMIT` already 20, `startup_cpu_boost` already on); **owner applies**; the post-apply cold start is measured per the runbook procedure and recorded beside ~50 s.
8. **gemini-2.5-flash re-measured** on the new instrument (eval mode, judge pinned), superseding `effd4854`; the citation-precision dip stays in the record; production routing untouched.

**Task constraints (binding):** one corpus state; no prompt/guard/model change (`openrouter/auto` stays); no new objects/re-filings beyond the view (`stepping-a-blocked-learner` stays out); **no squash-merge** for this branch (documentation pins SHAs); owner-run: the apply and the reference sign-off.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| DETERMINISM | `--check` after emission | byte-equal regeneration; tree ⊆ emission | any diff → exit non-zero |
| CZECH GUARD | Czech `:TITLE:`/`:SYNOPSIS:`, no translation artifact | hard error naming the object | no silent Czech in the extract |
| PIN | translation vs object at the pin commit | `:SOURCE-SHA256:` = the object file's sha at `339359e` | mismatch → hard error |
| ORPHANS | extract file not in the view's selection (or vice versa) | `--check` fails | no drift |
| MANIFEST | regenerated | count line = reality; sorted shas; excludes itself | count mismatch → hard error |
| GATE FREEZE | n=55, p from `156b5d1a` | citation ≥6/≤5, faithfulness ≥4/≤3, frozen before any measurement | post-hoc thresholds forbidden |
| REFERENCE | val 69 (55 gate-eligible), judge pinned | run id + artifact + registration; historical refs named | judge failure = faithfulness failure (contract) |
| CACHE | production run on the new index/dataset | artifact metadata: new dataset sha + corpus commit/tree | stale sha → build refuses |
| PLAN | the round's tree | image replace + cache/Containerfile triggers; **no other drift** | anything else is a finding |
| COLD START | ≥15 min idle after apply | one timed baked-question request; recorded beside ~50 s | warm instance invalidates the number |

</frozen-after-approval>

## Code Map

- `tools/extract_public_profile.py` (NEW, stdlib-only) — the procedure; `tools/extract_translations/` (NEW) — the versioned English translations (`intent-based-delegation.org`, `growth-in-any-role.org`, `style-references-as-intent.org`), extract-shaped, pin placeholder for injection.
- `public_profile_org/*` — regenerated: 62 objects + `public-proof-map.org` + `thesis-map.md` (64 content files; the task's "61/63" missed `style-references-as-intent` — view-listed, Czech, absent today; **owner-decided: included, count corrected, recorded as a finding with the stale-pointer pattern**) + `MANIFEST` (pin `339359e`).
- `src/janbot/ingest`, `src/janbot/store` — untouched; the index rebuild is `python -m janbot.ingest` (identity file recorded).
- `_bmad-output/initiative-janbot/epic-evaluation/gate-rule.md` — the n=55 pre-registration (arithmetic shown) inserted as a re-registration BEFORE the reference section is repointed; the reference section rewritten to the new run; history appended.
- `_bmad-output/initiative-janbot/epic-evaluation/run-<ref-id>-output.txt`, `rebaseline-round-20261022.md` (NEW round note), `measurement-gemini-2.5-flash-val.md` (superseded run recorded).
- `cache/answers-<run>.json` (NEW) + `Containerfile:74-76` (`--source` repointed); old artifact removed (git history keeps it).
- `RUNBOOK.md` — §2 already ulimit-free; the cold-start number lands in `epic-gcp-deploy/run-e3-public.md` after the apply.
- `eval/golden_dataset.yaml` — untouched (120 items are already committed; the dataset leads this round, it does not change in it).

## Tasks & Acceptance

**Execution (dependency order):**
- [x] `tools/extract_public_profile.py` + translations + `--check` green against the `05b11a7` fixture — the deficit closes. (commits `c8279d5` + mkdir fix; fixture 62 files byte-equal; edge-case matrix verified on a synthetic mini-corpus)
- [x] Regenerated extract + MANIFEST at pin `339359e`; committed (the corpus commit the cache pins). (janbot `1aae1d8`; 62 objects + 2 generated = 64 content files + MANIFEST)
- [x] Index rebuilt; chunk count + identity recorded; startup scope guard passes. (440 chunks / 63 sources, identity `930e0a3d…`, path-independent, `out_of_scope_sources` empty)
- [x] `gate-rule.md` n=55 pre-registration committed and **owner-signed** before the run. (committed `7161460`; signed 2026-10-22 before measuring, line recorded in `gate-rule.md`)
- [x] Reference run + artifact + registration + round note; historical refs named. (run `e1a0fa4e…`, artifact `run-e1a0fa4e-output.txt`, citation 34/55, faithfulness 47/55; `gate-rule.md` repointed; `156b5d1a`/`c6ced445` historical)
- [x] Cache regenerated; Containerfile repointed; `build_cache` validation green. (run `9f51134f…`, 55 entries, dataset `c4786e1c…`, corpus `a7752a0…`)
- [ ] Verified `terraform plan` → **owner applies** → cold start measured and recorded.
- [x] gemini re-run on the new instrument; measurement note supersession recorded. (run `3a7d8151…`, artifact `run-3a7d8151-output.txt`; fails the old "no regression on all four" rule: refusal_pass 14/14 → 13/14, citations dip 34 → 32; routing untouched)

**Acceptance Criteria:**
- Given the script and pin `339359e`, when the extract is emitted, then `--check` is byte-green, the MANIFEST count line matches reality, and every Czech selection carries pins.
- Given the rebuilt index, then `out_of_scope_sources` is empty and the chunk count is recorded.
- Given the frozen pre-registration, then the reference run is judged only by it (no post-hoc thresholds).
- Given the reference run, then `gate-rule.md` points at it with run id/config/n=55 and names `156b5d1a`/`c6ced445` historical.
- Given the cache artifact, then its metadata carries the new dataset sha and corpus pin, and the Containerfile bakes it.
- Given the flipped stack, then the plan shows only the named changes and the cold-start number is recorded beside ~50 s.
- Given the gemini re-run, then the note supersedes `effd4854` with the four metrics + the citation-precision dip.

## Implementation Notes

## Plan Change Log

- **2026-10-22 (execution).** Tasks 1–3 done and verified: the extract script with
  a byte-green `05b11a7` fixture (62 files), the extract regenerated at `339359e`
  (62 objects + 2 generated sections + MANIFEST; janbot `1aae1d8`), index rebuilt
  (440 chunks / 63 sources, identity `930e0a3d…`, scope guard empty). The n=55
  pre-registration is committed (`7161460`) but **unsigned** — the owner signs it
  before the reference run; the reference run, cache regeneration, Containerfile
  repoint, `terraform plan`/apply, cold-start measurement and the gemini re-run
  are therefore still open, in that order. The owner count correction (61/63 →
  62/64) is recorded as a finding in `rebaseline-round-20261022.md` with the
  stale-pointer pattern (the task's number came from the stale extract's
  inventory; the view selects 62 ids — `05b11a7` selects exactly the previous 59).
- **2026-10-22 (continuation).** The owner signed the n=55 pre-registration with
  the plan approval (`approve and continue`) before any measurement; the sign-off
  line is recorded in `gate-rule.md`. Reference run `e1a0fa4e…` (n=55: citation
  34/55, faithfulness 47/55) is registered, `156b5d1a`/`c6ced445` are historical.
  Cache regenerated from run `9f51134f…` (55 entries, dataset `c4786e1c…`,
  corpus `a7752a0…`), Containerfile repointed, `build_cache` green. Gemini
  re-measured on the new instrument (`3a7d8151…`): faithfulness/coverage improve,
  `refusal_pass_rate` regresses by one item, citations dip — no routing change
  proposed. Deploy remains owner-run.

## Review Triage Log

## Design Notes

- **Extract conventions discovered (the script encodes them, they are not invented):** extract filename = the object's internal filename (no rename table needed — the directory carries the dated id, e.g. `20261007-spec-first-evolution/spec-first-philosophy.org`); English extract files are **byte-identical** to their objects (verified across originals and the re-filed five at both `05b11a7` and `339359e`); `:ID:` stays the object's id, so citations and the golden dataset's `expected_sources` are filename-stable.
- **Why pins are injected, not hand-written:** the pin is a mechanical function of (object file, pinned commit); a hand-written pin is a second place to drift. When an object changes, the pin breaks — the README's named "translation drift" risk, caught mechanically.
- **Threshold arithmetic at n=55 (p from the outgoing reference `156b5d1a`, the only honest pre-measurement p):** citation p=33/49=0.6735 → σ=√(0.6735·0.3265/55)≈0.0632, 1.5σ≈0.0948 → 5/55=0.0909 is inside it, 6/55=0.1091 exceeds it → **accept ≥6, regress ≤5**; faithfulness p=45/49=0.9184 → σ≈0.0369, 1.5σ≈0.0554 → 3/55=0.0545 is inside it, 4/55=0.0727 exceeds it → **accept ≥4, regress ≤3**. If the new reference's own p shifts materially, that is recorded — the frozen floors still govern this round.
- **Cost:** the reference run (69 answers on the locked snapshot + 55 judge calls) and the gemini re-run (69 + 55) are paid but small; the key is present locally.
- **The demo's visible fix:** the index gains `growth-in-any-role`, `intent-based-delegation` (and `style-references-as-intent`), so *"Do you know agentic workflow?"* can cite the objects that describe the work.

## Verification

**Commands:**
- `uv run python tools/extract_public_profile.py --check` — byte-green regeneration at pin `339359e`.
- `uv run python -m janbot.ingest` + `uv run python -c "…index identity…"` — chunk count + identity recorded; the scope guard runs at app startup (`out_of_scope_sources` empty).
- `ulimit -n 16384 && uv run pytest -q` — the suite stays green (the dataset's own tests included).
- `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 OPENROUTER_API_KEY=… uv run python -m janbot.eval --split val` — the reference run (id + artifact recorded).
- `JANBOT_MODEL_MODE=production … uv run python -m janbot.eval --split val --cache-out cache/answers-<run>.json` + `python -m janbot.guardrails.build_cache --source … --out /tmp/answers.json` — the cache validates.
- `terraform -chdir=terraform validate && terraform -chdir=terraform plan …` — only the named changes.
- Post-apply: the cold-start curl per the runbook; the gemini re-run command as in the measurement note.
