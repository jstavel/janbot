# Review log: walkthrough-pr17-determinism

Target: PR https://github.com/jstavel/janbot/pull/17 · branch `e2e-4.4-determinism` · commit `049ba0c`.

## 1 — Orientation — narrative created

Session: unavailable · Timestamp: 2026-10-13T17:40:00+02:00

- Action: read the 4.4 plan (post-replan), the build diff, and PR #17; wrote the review narrative and this log.
- Result: five blocks drafted (Intent, Broad strokes, two slices, Periphery). No findings yet.
- Evidence: commit `049ba0c`; tests/e2e/test_determinism_e2e.py, tests/e2e/conftest.py; PR #17.
- Open: block-by-block human review pending.

## 2 — Block 1 Intent — accepted

Session: unavailable · Timestamp: 2026-10-13T17:41:00+02:00

- Action: presented the verbatim frozen Intent.
- Result: accepted as-is. No findings.
- Evidence: narrative Block 1.
- Open: none.

## 3 — Block 2 Broad strokes — accepted

Session: unavailable · Timestamp: 2026-10-13T17:42:00+02:00

- Action: presented the three entry points.
- Result: accepted as-is. No findings.
- Evidence: narrative Block 2.
- Open: none.

## 4 — Block 3 Cache-cold seam — accepted

Session: unavailable · Timestamp: 2026-10-13T17:43:00+02:00

- Action: presented the `extra_env` seam, `DETERMINISM_ENV` pin, and `cold_service` factory.
- Result: accepted as-is. No findings.
- Evidence: narrative Block 3.
- Open: none.

## 5 — Block 4 Determinism row — accepted

Session: unavailable · Timestamp: 2026-10-13T17:44:00+02:00

- Action: presented the two-cold-run row and its byte comparison.
- Result: accepted as-is. No findings.
- Evidence: narrative Block 4.
- Open: none.

## 6 — Block 5 Periphery — accepted; review complete

Session: unavailable · Timestamp: 2026-10-13T17:45:00+02:00

- Action: presented README, plan, and the deferred-work resolution.
- Result: accepted as-is. All 5 blocks accepted; no findings raised during the walkthrough.
- Evidence: narrative Block 5.
- Open: wrap-up — commit walkthrough artifacts, merge PR #17, mark story 4.4 done.
