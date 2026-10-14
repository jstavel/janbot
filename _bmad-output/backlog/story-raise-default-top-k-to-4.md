---
id: 6
type: story
title: "Raise the default retrieval top_k to 4"
parent: none
covers: []
after: []
refined: true
hitl: false
risk: low
---

# Raise the default retrieval top_k to 4

## Description

The retrieval default `JANBOT_TOP_K` was 3; raise it to 4 so an answer grounds on a broader context. It is also a tuning knob for the evaluation epic's optimization stages.

## Acceptance Criteria

1. **Default is 4**
   **Given** no `JANBOT_TOP_K` set
   **When** config loads
   **Then** `top_k` is 4
2. **Invalid value still fails fast**
   **Given** an invalid or non-positive `JANBOT_TOP_K`
   **When** config loads
   **Then** it fails fast
3. **Docs match**
   **Given** the README configuration table
   **When** the `JANBOT_TOP_K` row is read
   **Then** its default is 4

## Boundaries

- Must not change: the fail-fast validation or scoped retrieval at the store.

## References

- code — `src/janbot/config.py`
- tests — `tests/test_config.py`
- docs — `README.md`, Configuration

## Notes

- Decision (2026-10-14): implemented; record it as a tuning knob revisited once `epic-evaluation` entries 3–4 produce measured evidence.
