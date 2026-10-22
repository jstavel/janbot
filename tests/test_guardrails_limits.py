"""Shared counter tests: rate N/N+1, exact quota cap under concurrency, fail closed."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import pytest
from google.cloud import firestore

from janbot.guardrails.limits import (
    QUOTA_EXCEEDED,
    RATE_LIMITED,
    STORE_ERROR,
    FirestoreLimits,
)


class _Snapshot:
    def __init__(self, data: dict | None) -> None:
        self._data = data
        self.exists = data is not None

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default) if self._data else default


class _Ref:
    def __init__(self, store: dict[str, dict], doc_id: str, lock: threading.RLock) -> None:
        self.store = store
        self.doc_id = doc_id
        self.lock = lock

    def get(self, transaction: Any = None) -> _Snapshot:
        with self.lock:
            return _Snapshot(self.store.get(self.doc_id))


class _Transaction:
    def __init__(self, ref: _Ref, fail: bool) -> None:
        self.ref = ref
        self.fail = fail

    def update(self, ref: _Ref, data: dict) -> None:
        if self.fail:
            raise RuntimeError("unreachable")
        with ref.lock:
            current = ref.store.setdefault(ref.doc_id, {"count": 0})
            increment = data["count"]
            current["count"] += getattr(increment, "value", increment)

    def set(self, ref: _Ref, data: dict) -> None:
        if self.fail:
            raise RuntimeError("unreachable")
        with ref.lock:
            ref.store[ref.doc_id] = dict(data)


class _Collection:
    def __init__(self, store: dict[str, dict], lock: threading.RLock, fail: bool) -> None:
        self.store = store
        self.lock = lock
        self.fail = fail

    def document(self, doc_id: str) -> _Ref:
        return _Ref(self.store, doc_id, self.lock)


class FakeFirestore:
    """A transactional single-document counter store, serialized like Firestore."""

    def __init__(self, *, fail: bool = False) -> None:
        self.store: dict[str, dict] = {}
        self.lock = threading.RLock()
        self.fail = fail

    def collection(self, name: str) -> _Collection:
        return _Collection(self.store, self.lock, self.fail)

    def transaction(self) -> _Transaction:
        # The transactional decorator is patched in the fixture to run the
        # function under this shared lock, so read-then-increment is atomic.
        return _Transaction(_Ref(self.store, "", self.lock), self.fail)


class _Increment:
    def __init__(self, value: int) -> None:
        self.value = value


@pytest.fixture(autouse=True)
def _patch_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    def transactional(func):
        def wrapper(transaction):
            with transaction.ref.lock:
                return func(transaction)

        return wrapper

    monkeypatch.setattr(firestore, "transactional", transactional)
    monkeypatch.setattr(firestore, "Increment", _Increment)
    monkeypatch.setattr(firestore, "SERVER_TIMESTAMP", object())


def _limits(client: FakeFirestore, **overrides) -> FirestoreLimits:
    values = {
        "rate_limit": 10,
        "rate_window_seconds": 600,
        "daily_quota": 500,
        "clock": lambda: datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return FirestoreLimits(client, **values)


def test_nth_request_is_served_and_n_plus_one_is_refused() -> None:
    limits = _limits(FakeFirestore(), rate_limit=10)

    decisions = [limits.check_rate("203.0.113.7") for _ in range(11)]

    assert all(decision.allowed for decision in decisions[:10])
    assert decisions[10].allowed is False
    assert decisions[10].reason == RATE_LIMITED


def test_rate_windows_are_per_ip() -> None:
    limits = _limits(FakeFirestore(), rate_limit=1)

    assert limits.check_rate("203.0.113.1").allowed
    assert limits.check_rate("203.0.113.1").allowed is False
    assert limits.check_rate("203.0.113.2").allowed


def test_a_new_window_resets_the_rate_limit() -> None:
    clock = [datetime(2026, 10, 20, 12, 0, tzinfo=UTC)]
    limits = _limits(FakeFirestore(), rate_limit=1, clock=lambda: clock[0])

    assert limits.check_rate("203.0.113.1").allowed
    assert limits.check_rate("203.0.113.1").allowed is False
    clock[0] = datetime(2026, 10, 20, 12, 10, tzinfo=UTC)
    assert limits.check_rate("203.0.113.1").allowed


def test_exactly_the_quota_is_allowed_under_concurrency() -> None:
    limits = _limits(FakeFirestore(), daily_quota=25)

    with ThreadPoolExecutor(max_workers=20) as pool:
        decisions = list(pool.map(lambda _: limits.consume_quota(), range(100)))

    allowed = [decision for decision in decisions if decision.allowed]
    refused = [decision for decision in decisions if not decision.allowed]
    assert len(allowed) == 25
    assert len(refused) == 75
    assert all(decision.reason == QUOTA_EXCEEDED for decision in refused)


def test_store_error_fails_closed_for_rate() -> None:
    decision = _limits(FakeFirestore(fail=True)).check_rate("203.0.113.7")

    assert decision.allowed is False
    assert decision.reason == STORE_ERROR
    # A store error's recovery time is unknown — the 503 must stay header-free.
    assert decision.retry_after_seconds is None


def test_store_error_fails_closed_for_quota() -> None:
    decision = _limits(FakeFirestore(fail=True)).consume_quota()

    assert decision.allowed is False
    assert decision.reason == STORE_ERROR
    assert decision.retry_after_seconds is None


def test_allowed_and_refused_decisions_without_a_wait_carry_no_retry_after() -> None:
    limits = _limits(FakeFirestore(), rate_limit=1)

    allowed = limits.check_rate("203.0.113.7")
    refused = limits.check_rate("203.0.113.7")

    assert allowed.retry_after_seconds is None
    assert refused.retry_after_seconds is not None


def test_rate_refusal_carries_retry_after_to_the_window_boundary() -> None:
    # 12:00:00 inside the 12:00–12:10 window → the boundary is 12:10:00,
    # exactly 600 s away.
    limits = _limits(FakeFirestore(), rate_limit=1)

    decision = limits.check_rate("203.0.113.7")
    refusal = limits.check_rate("203.0.113.7")

    assert decision.allowed is True
    assert refusal.allowed is False
    assert refusal.reason == RATE_LIMITED
    assert refusal.retry_after_seconds == 600


def test_two_refusals_in_one_window_shrink_the_header() -> None:
    # The boundary acceptance: the second refusal served in the same window
    # must carry a strictly smaller Retry-After than the first.
    clock = [datetime(2026, 10, 20, 12, 0, tzinfo=UTC)]
    limits = _limits(FakeFirestore(), rate_limit=1, clock=lambda: clock[0])

    limits.check_rate("203.0.113.7")  # the allowed Nth request
    first = limits.check_rate("203.0.113.7")
    clock[0] = datetime(2026, 10, 20, 12, 1, 40, tzinfo=UTC)  # +100 s, same window
    second = limits.check_rate("203.0.113.7")

    assert first.retry_after_seconds == 600
    assert second.retry_after_seconds == 500
    assert second.retry_after_seconds < first.retry_after_seconds


def test_rate_retry_after_survives_across_the_boundary_gap() -> None:
    # A refusal 1 s before the boundary must wait 1 s, and a refusal in the
    # fresh window restarts at the full window length.
    clock = [datetime(2026, 10, 20, 12, 9, 59, tzinfo=UTC)]
    limits = _limits(FakeFirestore(), rate_limit=1, clock=lambda: clock[0])

    limits.check_rate("203.0.113.7")
    near_boundary = limits.check_rate("203.0.113.7")
    clock[0] = datetime(2026, 10, 20, 12, 10, 30, tzinfo=UTC)
    fresh_window = limits.check_rate("203.0.113.7")

    assert near_boundary.retry_after_seconds == 1
    assert fresh_window.allowed is True


def test_quota_refusal_carries_retry_after_to_the_next_utc_midnight() -> None:
    limits = _limits(FakeFirestore(), daily_quota=1)
    limits.consume_quota()  # consumes the day's only slot

    refusal = limits.consume_quota()

    assert refusal.allowed is False
    assert refusal.reason == QUOTA_EXCEEDED
    # 2026-10-20 12:00 UTC → next UTC midnight is 12 h later.
    assert refusal.retry_after_seconds == 43_200


def test_quota_retry_after_rounds_up_to_whole_seconds() -> None:
    # Half a second to midnight must not promise 0 s — ceil keeps the header
    # honest (never earlier than the actual rollover).
    clock = [datetime(2026, 10, 20, 23, 59, 59, 500_000, tzinfo=UTC)]
    limits = _limits(FakeFirestore(), daily_quota=1, clock=lambda: clock[0])
    limits.consume_quota()

    refusal = limits.consume_quota()

    assert refusal.retry_after_seconds == 1
