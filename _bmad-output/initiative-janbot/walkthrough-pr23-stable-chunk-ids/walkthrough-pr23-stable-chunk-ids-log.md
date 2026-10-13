# Review log: walkthrough-pr23-stable-chunk-ids

Target: PR https://github.com/jstavel/janbot/pull/23 · branch `ingest-stable-chunk-ids` · commit `b50f3fd`.

## 1 — Orientation — narrative created

Session: unavailable · Timestamp: 2026-10-13T20:45:00+02:00

- Action: read the plan, the diff, and PR #23; wrote the review narrative and this log.
- Result: five blocks drafted. No findings yet.
- Evidence: commit `b50f3fd`; src/janbot/ingest/*, src/janbot/store/chroma.py; PR #23.
- Open: block-by-block human review pending.

## 2 — Block 1 Intent — accepted

Session: unavailable · Timestamp: 2026-10-13T20:46:00+02:00

- Action: presented the verbatim frozen Intent.
- Result: accepted as-is. No findings.
- Evidence: narrative Block 1.
- Open: none.

## 3 — Block 2 Broad strokes — accepted

Session: unavailable · Timestamp: 2026-10-13T20:47:00+02:00

- Action: presented the two surfaces (ingest ids; store scope-key reconcile).
- Result: accepted as-is. No findings.
- Evidence: narrative Block 2.
- Open: none.

## 4 — Block 3 Content-hash ids — accepted

Session: unavailable · Timestamp: 2026-10-13T20:48:00+02:00

- Action: presented `_chunk_id` and the duplicate-suffix loop in `read_org_file`.
- Result: accepted as-is. No findings.
- Evidence: narrative Block 3.
- Open: none.

## 5 — Block 4 Scope-key reconcile — accepted

Session: unavailable · Timestamp: 2026-10-13T20:49:00+02:00

- Action: presented `upsert`/`scope_keys` and `index_corpus`'s reconcile (with the scope-less fallback).
- Result: accepted as-is. No findings.
- Evidence: narrative Block 4.
- Open: none.

## 6 — Block 5 Periphery — accepted; review complete

Session: unavailable · Timestamp: 2026-10-13T20:50:00+02:00

- Action: presented the test/doc records.
- Result: accepted as-is. All 5 blocks accepted; no findings raised during the walkthrough.
- Evidence: narrative Block 5.
- Open: wrap-up — commit walkthrough artifacts, merge PR #23, mark story 2.8 done (closes epic-ingestion).
