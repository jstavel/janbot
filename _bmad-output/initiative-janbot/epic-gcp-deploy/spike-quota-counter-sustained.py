"""Spike B: sustained write rate on one document vs sharded (the case a burst cannot answer).

Firestore's documented guidance is ~1 sustained write/s per document; short bursts are
absorbed. This drives a steady rate for a fixed duration and reports errors and latency.

Run: uv run --with google-cloud-firestore python /tmp/spike_quota_sustained.py
"""

from __future__ import annotations

import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from google.cloud import firestore

PROJECT = "janbot-deploy-2026-10"
DB = "janbot-spike-quota"
import os
RATE = int(os.environ.get('RATE', '10'))
SECONDS = int(os.environ.get('SECONDS', '15'))
WORKERS = 8


def make_client() -> firestore.Client:
    return firestore.Client(project=PROJECT, database=DB)


def inc(client: firestore.Client, doc_id: str) -> float:
    t0 = time.perf_counter()
    client.collection("spike").document(doc_id).update({"count": firestore.Increment(1)})
    return (time.perf_counter() - t0) * 1000.0


def drive(client: firestore.Client, docs: list[str], label: str) -> None:
    for d in docs:
        client.collection("spike").document(d).set({"count": 0})

    lat: list[float] = []
    errors: list[str] = []
    n = RATE * SECONDS
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        t_start = time.perf_counter()
        futures = []
        for i in range(n):
            target = t_start + i / RATE
            now = time.perf_counter()
            if target > now:
                time.sleep(target - now)
            futures.append(pool.submit(inc, client, random.choice(docs)))
        for f in futures:
            try:
                lat.append(f.result())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {str(exc).splitlines()[0][:100]}")
        wall = time.perf_counter() - t_start

    total = sum(
        client.collection("spike").document(d).get().to_dict()["count"] for d in docs
    )
    ordered = sorted(lat)
    p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))] if ordered else None
    print(
        f"{label}: {n} writes at {RATE}/s over {wall:.1f}s | ok={len(lat)} errors={len(errors)} "
        f"| p50={round(statistics.median(lat), 1) if lat else None}ms p95={round(p95, 1) if p95 else None}ms "
        f"| max={round(max(lat), 1) if lat else None}ms | total={total} (expected {n})"
    )
    if errors:
        print(f"   first errors: {errors[:3]}")


def main() -> None:
    client = make_client()
    docs = os.environ.get("DOCS", "single")
    if docs == "shards":
        drive(client, [f"sustained-shard-{i}" for i in range(16)], "B) 16 shards")
    else:
        drive(client, ["sustained-single"], "A) single document")


if __name__ == "__main__":
    main()
