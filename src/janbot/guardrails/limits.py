"""Shared rate-limit and global-quota counters (ADR-009 controls 2 and 3).

Both counters live in one Firestore document each — no sharding (the spike
measured a single document absorbing 100 sustained writes/s with exact counts; see
``_bmad-output/.../spike-quota-counter.md``). Each check is a Firestore
transaction: read the count, refuse at the limit, otherwise increment atomically.

Operation count: a rate check is **1 read + 1 write**, a quota check is **1 read +
1 write**. A cache miss therefore adds four operations (200–360 ms at the
measured 50–90 ms/op); a cache hit adds two (the quota pair is skipped because no
model call is made).

**Fail closed:** every Firestore error (including an unreachable database) becomes
``GuardDecision(allowed=False, reason="store_error")``. The guard never fails open.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any, Protocol

RATE_LIMITED = "rate_limited"
QUOTA_EXCEEDED = "quota_exceeded"
STORE_ERROR = "store_error"
ALLOWED = "allowed"

COLLECTION = "janbot_guardrails"


@dataclass(frozen=True)
class GuardDecision:
    """The guard's verdict: allowed, or denied with a closed-set reason.

    A denial may carry ``retry_after_seconds`` — the honest number of seconds
    until the earliest moment the same call would be allowed again: the next
    window boundary for a rate refusal, the next UTC midnight for a quota
    refusal. ``None`` means the wait is unknown and must not be fabricated —
    the 503 store error stays header-free.
    """

    allowed: bool
    reason: str
    retry_after_seconds: int | None = None

    @classmethod
    def allow(cls) -> GuardDecision:
        return cls(True, ALLOWED)

    @classmethod
    def deny(cls, reason: str) -> GuardDecision:
        return cls(False, reason)

    @classmethod
    def deny_with_retry(cls, reason: str, retry_after_seconds: int) -> GuardDecision:
        return cls(False, reason, retry_after_seconds=retry_after_seconds)


class Limiter(Protocol):
    """The two shared controls the request path needs."""

    def check_rate(self, client_ip: str) -> GuardDecision: ...

    def consume_quota(self) -> GuardDecision: ...


def _rate_doc_id(client_ip: str) -> str:
    digest = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:24]
    return f"rate_{digest}"


class FirestoreLimits:
    """A per-IP fixed-window rate limit plus a global daily model-call quota."""

    def __init__(
        self,
        client: Any,
        *,
        rate_limit: int,
        rate_window_seconds: int,
        daily_quota: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if rate_limit < 1 or rate_window_seconds < 1 or daily_quota < 1:
            raise ValueError("rate and quota limits must be positive")
        self._client = client
        self._rate_limit = rate_limit
        self._rate_window_seconds = rate_window_seconds
        self._daily_quota = daily_quota
        self._clock = clock or (lambda: datetime.now(UTC))
        self._collection = client.collection(COLLECTION)

    @classmethod
    def from_config(cls, config: Any) -> FirestoreLimits | None:
        """Build from config, or return ``None`` when no Firestore project is set.

        Production mode already refuses to start without a project (config
        validation); an unset project outside production means the local/eval run
        has no shared store, so the layer runs without the two counters.
        """
        if not config.firestore_project:
            return None
        from google.cloud import firestore

        client = firestore.Client(
            project=config.firestore_project, database=config.firestore_database
        )
        return cls(
            client,
            rate_limit=config.rate_limit,
            rate_window_seconds=config.rate_window_seconds,
            daily_quota=config.daily_quota,
        )

    def check_rate(self, client_ip: str) -> GuardDecision:
        """Count one request for ``client_ip``; deny the N+1th request in the window.

        The refusal's ``retry_after_seconds`` points at the next window
        boundary — the earliest moment this IP's count resets and a slot
        frees. ``int(now)`` floors the truncation on purpose: the header never
        promises a slot earlier than the boundary.
        """
        now = self._clock()
        window = int(now.timestamp() // self._rate_window_seconds)
        ref = self._collection.document(_rate_doc_id(client_ip or "unknown"))
        try:
            allowed = self._increment_within(
                ref, self._rate_limit, now, window=window
            )
        except Exception:
            return GuardDecision.deny(STORE_ERROR)
        if allowed:
            return GuardDecision.allow()
        boundary = (window + 1) * self._rate_window_seconds
        return GuardDecision.deny_with_retry(
            RATE_LIMITED, boundary - int(now.timestamp())
        )

    def consume_quota(self) -> GuardDecision:
        """Count one request that reached the program for the UTC day.

        This is a **conservative request quota**, not an exact model-call meter:
        a pre-LM refusal (empty retrieval / low relevance) consumes a slot even
        though it makes no model call. It therefore bounds spend from above, and
        a refusal flood can exhaust the daily quota (availability trade; the
        per-IP rate limit bounds its rate, not the total). Exact model-call
        counting would need a pre-LM hook inside the AI core, which E2's boundary
        forbids.

        The refusal's ``retry_after_seconds`` is the seconds to the next UTC
        midnight — the daily counter's honest reset point, not a per-IP window
        boundary. ``math.ceil`` keeps the header from promising a slot before
        the day actually rolls over.
        """
        now = self._clock()
        ref = self._collection.document(f"quota_{now.date().isoformat()}")
        try:
            allowed = self._increment_within(ref, self._daily_quota, now)
        except Exception:
            return GuardDecision.deny(STORE_ERROR)
        if allowed:
            return GuardDecision.allow()
        midnight = datetime.combine(
            now.date() + timedelta(days=1), time.min, tzinfo=UTC
        )
        return GuardDecision.deny_with_retry(
            QUOTA_EXCEEDED, math.ceil((midnight - now).total_seconds())
        )

    def _increment_within(
        self,
        ref: Any,
        limit: int,
        now: datetime,
        *,
        window: int | None = None,
    ) -> bool:
        from google.cloud import firestore

        @firestore.transactional
        def update(transaction: Any) -> bool:
            snapshot = ref.get(transaction=transaction)
            if window is not None:
                # One document per IP; a new window resets the count in place.
                current = (
                    int(snapshot.get("count") or 0)
                    if snapshot.exists and snapshot.get("window") == window
                    else 0
                )
                if current >= limit:
                    return False
                data = {
                    "count": current + 1,
                    "window": window,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }
                if not snapshot.exists:
                    data["created_at"] = firestore.SERVER_TIMESTAMP
                transaction.set(ref, data)
                return True

            current = int(snapshot.get("count") or 0) if snapshot.exists else 0
            if current >= limit:
                return False
            if snapshot.exists:
                transaction.update(
                    ref,
                    {
                        "count": firestore.Increment(1),
                        "updated_at": firestore.SERVER_TIMESTAMP,
                    },
                )
            else:
                transaction.set(
                    ref,
                    {
                        "count": 1,
                        "created_at": firestore.SERVER_TIMESTAMP,
                        "updated_at": firestore.SERVER_TIMESTAMP,
                        "bucket": now.isoformat(),
                    },
                )
            return True

        return bool(update(self._client.transaction()))
