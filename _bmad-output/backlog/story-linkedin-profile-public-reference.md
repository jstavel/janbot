---
id: 7
type: story
title: "Complete the LinkedIn profile as a public reference JanBot can cite"
parent: none
covers: []
after: []
refined: false
hitl: true
risk: low
---

# Complete the LinkedIn profile as a public reference JanBot can cite

## Description

Bring the LinkedIn profile in line with the rest of the public presentation — filled-out intro, projects with links (repos, the published CV), and a link back — so it becomes another verifiable public reference the owner's JanBot answers can point recruiters to.

## Acceptance Criteria

Verify: the LinkedIn profile is complete (intro, projects with URLs, CV link) and its URL joins the public-reference allow-list so JanBot can cite it.

## Boundaries

- Must not change: nothing in the corpus needed unless the profile link becomes a corpus fact for grounding.

## References

- brainstorm — `_bmad-output/initiative-janbot/brainstorm-golden-dataset-questions/.memlog.md`
- related — `_bmad-output/backlog/story-gcp-deployment-terraform.md`, `_bmad-output/backlog/story-gh-pages-chat-widget.md` (other public-surface work)

## Notes

- Decision (2026-10-14): raised in the golden-dataset brainstorm — the public-reference allow-list (CV URL under a git-crypt repo, GitHub repo links, LinkedIn) is the set JanBot validates answers against; the LinkedIn URL lives here until it becomes a grounded corpus fact.
- Open question: whether the profile link needs grounding in `public_profile_org/` (re-extraction) or only allow-list membership.