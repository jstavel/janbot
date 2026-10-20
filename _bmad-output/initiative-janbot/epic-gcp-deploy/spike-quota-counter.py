"""Spike: global quota counter under concurrency (Firestore, sharded vs single doc).

Answers three questions before E2 is designed:
  A) does a single-document counter survive N concurrent increments (and at what latency)?
  B) does a sharded counter (S shards, random shard per write) do better?
  C) when the database is unreachable, does the client raise (so a guard can fail closed)?

Run: uv run --with google-cloud-firestore python /tmp/spike_quota.py
"""

from __future__ import annotations

import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from google.cloud import firestore

PROJECT = "janbot-deploy-2026-10"
DB = "janbot-spike-quota"
N = 100  # increments per test
WORKERS = 20  # concurrent writers


def make_client(database: str) -> firestore.Client:
    return firestore.Client(project=PROJECT, database=database)


def timed_increment(client: firestore.Client, doc_id: str) -> float:
    ref = client.collection("spike").document(doc_id)
    t0 = time.perf_counter()
    ref.update({"count": firestore.Increment(1)})
    return (time.perf_counter() - t0) * 1000.0


def run_parallel(client: firestore.Client, pick_doc, n: int, workers: int) -> dict:
    latencies: list[float] = []
    errors: list[str] = []
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(timed_increment, client, pick_doc()) for _ in range(n)]
        for f in futures:
            try:
                latencies.append(f.result())
            except Exception as exc:  # noqa: BLE001 - the point is to classify failures
                errors.append(f"{type(exc).__name__}: {exc}")
    wall = time.perf_counter() - t0
    ordered = sorted(latencies) or [0.0]
    p = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]  # noqa: E731
    return {
        "n": n,
        "ok": len(latencies),
        "errors": len(errors),
        "error_sample": errors[:2],
        "wall_s": round(wall, 2),
        "throughput_per_s": round(len(latencies) / wall, 1) if wall else 0.0,
        "p50_ms": round(statistics.median(latencies), 1) if latencies else None,
        "p95_ms": round(p(0.95), 1) if latencies else None,
        "max_ms": round(max(latencies), 1) if latencies else None,
    }


def main() -> None:
    client = make_client(DB)

    # baseline: one sequential write
    client.collection("spike").document("warmup").set({"count": 0})
    t0 = time.perf_counter()
    client.collection("spike").document("warmup").update({"count": firestore.Increment(1)})
    print(f"baseline single write: {(time.perf_counter() - t0) * 1000:.1f} ms\n")

    client.collection("spike").document("quota-single").set({"count": 0})
    print("A) single document, 100 increments, 20 workers")
    a = run_parallel(client, lambda: "quota-single", N, WORKERS)
    final_a = client.collection("spike").document("quota-single").get().to_dict()["count"]
    print(f"   {a}\n   final count = {final_a} (expected {N})\n")

    shards = [f"quota-shard-{i}" for i in range(16)]
    for s in shards:
        client.collection("spike").document(s).set({"count": 0})
    print("B) 16 shards, 100 increments, 20 workers")
    b = run_parallel(client, lambda: random.choice(shards), N, WORKERS)
    total = sum(
        client.collection("spike").document(s).get().to_dict()["count"] for s in shards
    )
    print(f"   {b}\n   sum of shards = {total} (expected {N})\n")

    print("C) fail-closed: a database that does not exist")
    try:
        bad = make_client("janbot-spike-does-not-exist")
        bad.collection("spike").document("x").update({"count": firestore.Increment(1)})
        print("   NOT fail-closed: the call succeeded (unexpected)")
    except Exception as exc:  # noqa: BLE001
        print(f"   raised {type(exc).__name__} -> a guard can deny the request")
        print(f"   message: {str(exc).splitlines()[0][:160]}")


if __name__ == "__main__":
    main()
