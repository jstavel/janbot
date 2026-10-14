---
id: 9
type: story
title: "Public-reference allow-list and answer verification"
parent: none
covers: []
after: []
refined: false
hitl: false
risk: medium
---

# Public-reference allow-list and answer verification

## Description

Design realized from the golden-question brainstorm: a static, versioned **allow-list of valid public URLs** (GitHub repos under their real owners — `jstavel`, `edeposit`, `RedHatQE` — plus the published CV PDF and LinkedIn) harvested from the corpus, against which every answer is verified. A URL in an answer that is **not** on the list is an unverifiable claim (refused); a URL that is **expected but missing** (the answer names a project with an allowable reference and omits it) is an incomplete answer (rejected), not a soft miss. Mirrors the citation grounding guard for proof links.

## Acceptance Criteria

Verify: an answer whose URLs are all allow-listed passes; an invented or wrong-owner URL is refused; a missing-but-expected URL is rejected as incomplete.

## Boundaries

- Must not change: the citation contract (`/chat` citations stay corpus paths); grounding — every reference an answer should surface must come from a corpus fact.

## References

- brainstorm — `_bmad-output/initiative-janbot/brainstorm-golden-dataset-questions/.memlog.md`
- epic — `_bmad-output/initiative-janbot/epic-evaluation/epic-evaluation.md`, entry 12 (dataset expansion) and the S5 decision (citation containment)

## Notes

- Decision (2026-10-14): missing-when-expected is rejected (hard signal) so DSPy optimizers get a real gradient on surfacing the right link; invented URL is refused.
- Unknown: whether the allow-list is derived at ingest/eval from a corpus `:PUBLIC:`-drawer harvest or maintained as a separate file; the holder of the check (a metric in 5.3–5.5, or the runner) is to be settled when it is built.