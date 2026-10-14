---
id: 4
type: story
title: "Static GitHub Pages widget calling /chat"
parent: none
covers: []
after: [3]
refined: false
hitl: false
risk: medium
---

# Static GitHub Pages widget calling /chat

## Description

A small static JavaScript page on GitHub Pages that calls `POST /chat` and renders the cited answer — a live, recruiter-facing demo of the service.

## Acceptance Criteria

Verify: the published Pages page posts a question to the deployed `/chat` and renders the answer with its citations.

## Boundaries

- Must not change: the `/chat` contract; the widget is a thin caller with no AI logic (AD-2).
- Must not change: no new public interface without a superseding decision (AD-1).

## References

- source — `intake-gh-pages-chat-widget.md`
- architecture — `_bmad-output/initiative-janbot/architecture-janbot/architecture-janbot.md`, AD-1 (no other public interface without a superseding decision)
- spec — `_bmad-output/initiative-janbot/spec-janbot/spec-janbot.md`, Assumptions (guardrails before recruiter deployment)

## Notes

- Unknown: the API has no public URL — the deployment decision gates this.
- Unknown: a browser-facing widget plus a CORS allowance is a new public interface; it needs a superseding decision/ADR.
- Unknown: the anonymization/guardrails gate — a public demo counts as deployment.
- Open question: CORS origin and the read-only/rate-limit posture.
