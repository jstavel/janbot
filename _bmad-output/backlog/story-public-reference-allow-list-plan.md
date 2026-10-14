---
title: 'Public-reference allow-list and answer verification'
type: 'feature'
ticket: 9
created: '2026-10-14'
status: done
baseline_revision: 'd18907c3c18d6eda3cb96b7a2d69454d8cdd216c'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** JanBot answers may name projects; the owner's rule is that an answer surfaces the full public URL when a project has one, and never invents one. Nothing enforces or measures that today — the eval has no public-reference check, and an invented or wrong-owner URL would pass unnoticed.

**Approach:** a static, versioned **allow-list** of valid public URLs (harvested from the corpus `:PUBLIC:` drawers and the generated proof map), plus an eval check with the owner's asymmetry: a URL **not** on the list is unverifiable (failure), and a URL present in an item's expected answer but **missing** from the model answer is incomplete (failure). Off-the-request-path, in the eval harness.

## Boundaries & Constraints

**Always:** derive the allow-list from the corpus (single source); keep `/chat` and its Pydantic contract unchanged; the check lives in the eval layer.

**Never:** no `/chat` behavior change in this story; no hand-maintained URL list that can drift from the corpus; no change to the citation contract (citations stay corpus paths).

**Decision (2026-10-14, resolved in review):** every explicit public reference in the corpus is valid and goes on the allow-list — a `:PUBLIC:` drawer, an org `[[url]]` link, or a reference-list bullet that leads with the URL — plus the generated proof map. The `:PUBLIC:` drawer is the object's **top-priority** reference. Generated into `eval/public_urls.yaml` by a script — single source, no drift.

**Decision (2026-10-14):** enforcement is **eval-only** in this story; a `/chat` refusal of an off-list URL is deferred as its own decision (a CAP-1/CAP-2 behavior change in the done `epic-rag-chat`), not built here.

**Decision (2026-10-14):** missing-URL detection derives the expected URLs from each item's `expected_answer` — no dataset schema change.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| All URLs allow-listed | answer names a project, URL on the list | metric passes | No error |
| Invented / wrong-owner URL | answer contains an off-list URL | scored as unverifiable (fail) | Flagged in the run |
| Expected URL missing | item's expected answer has a URL; the model answer does not | scored as incomplete (fail) | Flagged in the run |
| No URLs involved | neither expected nor answer has a URL | metric passes | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/eval/metrics.py:36` — `register_metric`; the new `public_references` metric registers here.
- `src/janbot/eval/runner.py:92` — runs `registered_metrics()` over outcomes; no change needed beyond the metric.
- `src/janbot/eval/dataset.py:20` — `GoldenItem(question, expected_answer, expected_sources)`; the expected URLs come from `expected_answer`.
- `public_profile_org/public-proof-map.org` — the generated public proof map (the URL source).
- corpus `:PUBLIC:` drawers — harvested for the allow-list.
- New: `src/janbot/eval/public_urls.py`, `eval/public_urls.yaml` (generated), `tests/test_eval_public_urls.py`.

## Tasks & Acceptance

**Execution:**
- [ ] `eval/public_urls.yaml` -- the generated allow-list (harvest `:PUBLIC:` drawers across `public_profile_org/` + the proof map) -- single source, no drift.
- [ ] `src/janbot/eval/public_urls.py` -- load the allow-list; extract URLs from a text -- the check's core.
- [ ] `src/janbot/eval/metrics.py` -- register `public_references`: fail on an off-list URL, fail on a missing expected URL -- the owner's asymmetry.
- [ ] `tests/test_eval_public_urls.py` -- allow-listed, invented, missing, and no-URL cases -- proves the matrix.
- [ ] `src/janbot/eval/runner.py`, `src/janbot/eval/__main__.py` -- report each failing item/URL in the run output -- the matrix's "flagged in the run", not just an aggregate float.
- [ ] `src/janbot/eval/public_urls.py` -- walk `.org` files locally, importing no `janbot.ingest`/`janbot.store` -- keep the eval package import-isolated.

**Acceptance Criteria:**
- Given an answer whose URLs are all allow-listed, when the metric runs, then it passes.
- Given an answer containing an off-list URL, when the metric runs, then it fails as unverifiable.
- Given an item whose expected answer carries a URL and a model answer without it, when the metric runs, then it fails as incomplete.

## Implementation Notes

- 2026-10-14 (walkthrough follow-up): hardened the two review thoughts — an explicit `_SHARED_HOSTS` set so a shared host (`github.com`, …) is never "dedicated" at any list size, closing the pathless-host hole a small corpus could reopen; and `is_public_reference` now reuses `_covers`, so the "unverifiable" and "missing" containment directions cannot drift apart.

## Plan Change Log

- 2026-10-14 (bad_plan + intent_gap loopback, review pass 1): the plan under-specified the URL contract (normalization, extraction, per-item flagging). Frozen harvest decision resolved with the owner — every explicit corpus reference is valid, `:PUBLIC:` is the top-priority one. Amended the non-frozen plan with the **URL contract** (Design Notes) and tasks for **per-item flagging** and **import isolation**. Reverted the first implementation; re-derived from the amended plan.
  - KEEP: the corpus-harvest generator + generated `eval/public_urls.yaml`; the `public_references` metric shape (off-list = unverifiable, missing = incomplete, no-URLs = pass); the 22-test coverage; the runner/CLI integration.

## Review Triage Log

## Review Triage Log

Review pass 1 (quick, pinned) — 9 findings:
- pathless expected URLs (e.g. `bazar-cd.cz`) dropped by the extractor, so a missing one is never flagged — **medium / bad_plan** — URL contract under-specified.
- `_covers` coarser-prefix rule lets off-list URLs pass (`https://github.com`, `https://www.brailcom.cz` verify) — **high / bad_plan** — URL contract.
- normalization misses `.git`, `#fragment`, `?query`, and deeper paths (`/tree/main`), flagging legit forms — **medium / bad_plan** — URL contract.
- a URL glued to following text (`,and`) keeps the glue and fails — **low / bad_plan** — URL contract.
- invented scheme-less domain with no path is never extracted — **low / defer** — documented trade-off; favours the owner's "prefer a missing link over a wrong one".
- `public_urls` imports `janbot.ingest.scope` → transitively chromadb, breaking the eval package's stated isolation — **medium / patch**.
- the I/O matrix promises "flagged in the run", but the metric returns only a float and nothing names the failing item/URL — **medium / bad_plan** — plan promised it.
- harvest reads bullets and `[[url]]` links across every file, broader than the frozen decision (`:PUBLIC:` + proof map) — **medium / intent_gap** — needs the owner.
- `CHANGELOG.md` not updated — **low / defer** — repo-wide gap already tracked.

Review pass 2 (quick, after the re-derivation) — 2 findings, both patched:
- `normalize_reference` stripped `.git` before the trailing `/`, so `.../janbot.git/` escaped both — **low / patch** — fixed: strip the trailing `/` first.
- the deeper-path branch skipped pathless listed entries, so `bazar-cd.cz/kniha` under listed `bazar-cd.cz` was off-list while `_covers` treated it as covered — **medium / patch** — fixed: a path under a listed pathless dedicated host verifies.

## Design Notes

**URL contract (settles the review's URL findings).**
- *Normalization:* strip scheme, a leading `www.`, a trailing `.git`, a trailing `#fragment`, a trailing `?query`, and trailing punctuation; lower-case host and path; drop a trailing `/`.
- *On-list:* a candidate is on the list iff it equals a listed entry, is a **deeper path under** a listed entry (`github.com/jstavel/janbot/tree/main` under `github.com/jstavel/janbot`), or is a **listed pathless host** (`brailcom.cz` for `brailcom.cz/projects`). A pathless candidate covers only a pathless listed entry — `github.com` must NOT verify as a prefix of every listed `github.com/...` repo.
- *Extraction:* a scheme'd or `www.` URL always counts; a bare domain counts when it carries a path, or when it matches a listed host (so an expected pathless reference like `bazar-cd.cz` is still checked). Prose tokens (`WebDriver.io`, `test-clj.testng`) stay out.
- *Splitting:* a URL glued to following text by `,` `;` `:` is split; those characters are not part of a URL body.
- *Missing:* an item fails as incomplete when an expected URL (extracted the same way) is not surfaced by the answer.
- *Flagging:* a failing item or URL is reported per item in the run output (the I/O matrix's "flagged in the run"), not only as an aggregate float.
- *Isolation:* the eval package must not import `janbot.ingest`/`janbot.store`; walk `.org` files locally.

## Verification

**Commands:**
- `uv run pytest -q tests/test_eval_public_urls.py` -- expected: green.
- `uv run python -m janbot.eval --dataset eval/golden_dataset.yaml` -- expected: the `public_references` metric is logged in the run.

**Manual checks (if no CLI):**
- Read `eval/public_urls.yaml` and confirm every URL is a live public reference under its real owner.
