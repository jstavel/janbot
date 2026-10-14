---
id: 8
type: story
title: "Publish the CV publicly via a git-crypt repo and GitHub Pages"
parent: none
covers: []
after: []
refined: false
hitl: true
risk: low
---

# Publish the CV publicly via a git-crypt repo and GitHub Pages

## Description

Publish the EN LaTeX CV as a public PDF from a `jstavel/cv` repo: the public source carries redacted defaults, the personal data lives in a git-crypt'd file, CI builds the redacted PDF to GitHub Pages, and a local `make` target injects the revealed personal fields to build the full PDF (never committed).

## Acceptance Criteria

Verify: the Pages URL serves `cv-en.pdf`; the CI build contains no personal data; the local build produces the full PDF from the git-crypt'd values.

## Boundaries

- Must not change: no personal data may appear in the public repo or its history; the LaTeX source stays self-contained (`.cls`, images committed).

## References

- brainstorm — `_bmad-output/initiative-janbot/brainstorm-golden-dataset-questions/.memlog.md`
- related — `_bmad-output/backlog/story-linkedin-profile-public-reference.md`

## Notes

- Decision (2026-10-14): git-crypt (one aligned repo) over SOPS + env-injection; EN variant only; source public; the live URL joins the JanBot public-reference allow-list.
- Privacy: decide which fields are redacted (address, phone, photo, personal IDs) before the first public push.