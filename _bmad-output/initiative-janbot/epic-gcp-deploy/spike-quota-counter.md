# Spike — global quota counter under concurrency (2026-10-20)

**Question.** Before E2 is designed: does the guardrail counter need sharding, and does the
guard fail closed when the store is unreachable?

**Setup.** Firestore **native**, `europe-central2`, throwaway database `janbot-spike-quota`
(deleted after the runs). Client `google-cloud-firestore` 2.34.1 over ADC; runs from the
owner's workstation. Scripts: `spike-quota-counter.py` (burst + fail-closed) and
`spike-quota-counter-sustained.py` (paced rate). Raw output: `spike-quota-counter-output.txt`.

## Results

| scenario | writes | errors | p50 | p95 | count exact |
|---|---|---|---|---|---|
| burst, one document, 20 workers | 100 | 0 | 120.6 ms | 171.3 ms | 100 ✓ |
| burst, 16 shards, 20 workers | 100 | 0 | 62.5 ms | 92.6 ms | 100 ✓ |
| **sustained 10/s, one document** | 150 | 0 | 47.9 ms | 55.6 ms | 150 ✓ |
| **sustained 50/s, one document** | 500 | 0 | 46.2 ms | 68.6 ms | 500 ✓ |
| **sustained 100/s, one document** | 1000 | 0 | 53.1 ms | 93.5 ms | 1000 ✓ |
| unreachable database | 1 | raises `NotFound` | — | — | — |

## What this settles

1. **The counter does not need sharding.** A single document absorbed **100 sustained
   writes/s (1000 writes, 0 errors, exact count)**. The documented "~1 sustained write/s per
   document" guidance is far more conservative than the service behaves. Expected traffic is
   well under 1 write/s (a handful of recruiters), so sharding would add complexity with no
   measured benefit — a detail that decorates rather than guarantees.
2. **Increments are atomic.** The final count equalled the number of writes in every run; no
   lost updates even at 20 concurrent workers.
3. **Fail-closed is demonstrable.** A client pointed at a non-existent database raises
   `NotFound` — so a guard can deny the request deterministically rather than silently
   letting it through.
4. **Cost of the guard:** ~50–90 ms per Firestore operation (p50/p95, same region). One or two
   operations per `/chat` is the expected addition; it is a latency cost to state, not a
   throughput risk.

## Caveats (what this does *not* show)

- One workstation, one region, 8–20 threads. Not tested: two Cloud Run instances contending,
  or hours-long sustained load.
- The burst case favours shards on p50 (62 vs 121 ms), which is a warm-up/queueing effect at
  20 concurrent writers — not a reason to shard at our rate.
- If abuse ever pushed writes past the measured ceiling, writes would start failing — and
  under **fail-closed** that denies requests. The hard cap therefore still holds; the
  failure direction is the safe one.

## Decision impact

The 2026-10-20 owner decision ("sharded counter") is **superseded by measurement**: implement
a **single-document counter** (`FieldValue.increment`) with **fail-closed** on any Firestore
error. Sharding stays unbuilt until a measurement shows the single document failing — and the
same scripts can answer that later without new design work.

## Raw output coverage (E2, 2026-10-20)

The committed `spike-quota-counter-output.txt` covers the burst rows and the
100/s sustained row; the 10/s and 50/s rows are summarized from the same script
and are not present in the raw file. The **implemented transactional counter**
is verified separately in `spike-quota-counter-e2-output.txt` against a
throwaway Firestore native database (`janbot-e2-verify`, deleted after):

- 20 concurrent quota increments at cap 10 → **exactly 10 allowed**;
- 11 concurrent rate checks at cap 10 → 9 allowed, 2 fail-closed store errors
  under first-write contention (the cap is never exceeded);
- an unreachable database → `store_error` for both controls (fail closed).

The implementation uses a read-then-set/increment transaction, not the spike's
plain `DocumentReference.update`.
