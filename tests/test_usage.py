"""Usage counter tests: daily totals, fail-open, no IP or text, the read CLI.

The matrix the tests pin (the story's USAGE rows): an answered reply — live or
cache hit — records ``served``; an insufficient reply and the route-level
guardrail refusals (422/429/503) record ``declined``; a counter error is
logged and never affects the request; pre-route body-limit refusals stay out;
the CLI prints per-date totals and fails clearly without a store or ADC.
"""

from __future__ import annotations

import inspect
import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from dspy.utils import DummyLM
from fastapi.testclient import TestClient
from google.cloud import firestore

from janbot.api.contract import ChatResponse
from janbot.api.main import create_app
from janbot.config import Config, PROJECT_ROOT
from janbot.guardrails.limits import COLLECTION, GuardDecision, RATE_LIMITED, STORE_ERROR
from janbot.guardrails.usage import (
    DECLINED_FIELD,
    SERVED_FIELD,
    USAGE_DOC_PREFIX,
    UsageCounter,
    main,
    read_day,
)
from janbot.ingest import index_corpus
from janbot.pipeline.chat import LowRelevance

# The date the clock and CLI are pinned to in these tests.
TODAY = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


class _Increment:
    def __init__(self, value: int) -> None:
        self.value = value


@pytest.fixture(autouse=True)
def _patch_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(firestore, "Increment", _Increment)
    monkeypatch.setattr(firestore, "SERVER_TIMESTAMP", object())


class _DocRef:
    def __init__(self, store: dict[str, dict], doc_id: str, fail: bool) -> None:
        self.store = store
        self.doc_id = doc_id
        self.fail = fail
        self.lock = threading.RLock()

    def set(self, data: dict, merge: bool = True) -> None:
        if self.fail:
            raise RuntimeError("the store is unreachable")
        with self.lock:
            doc = self.store.setdefault(self.doc_id, {})
            for key, value in data.items():
                if isinstance(value, _Increment):
                    value = int(doc.get(key) or 0) + value.value
                doc[key] = value

    def get(self) -> "_Snapshot":
        with self.lock:
            data = self.store.get(self.doc_id)
            return _Snapshot(dict(data) if data else None)


class _Snapshot:
    def __init__(self, data: dict | None) -> None:
        self._data = data
        self.exists = data is not None

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default) if self._data else default


class _Collection:
    def __init__(self, store: dict[str, dict], fail: bool) -> None:
        self.store = store
        self.fail = fail

    def document(self, doc_id: str) -> _DocRef:
        return _DocRef(self.store, doc_id, self.fail)


class FakeUsageStore:
    """A set-merge counter store; ``fail`` simulates an unreachable Firestore."""

    def __init__(self, *, fail: bool = False) -> None:
        self.store: dict[str, dict] = {}
        self.fail = fail

    def collection(self, name: str) -> _Collection:
        assert name == COLLECTION
        return _Collection(self.store, self.fail)


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return TODAY


class RecordingUsage:
    def __init__(self) -> None:
        self.served = 0
        self.declined = 0

    def record_served(self) -> None:
        self.served += 1

    def record_declined(self) -> None:
        self.declined += 1


class AllowingLimiter:
    def check_rate(self, client_ip: str) -> GuardDecision:
        return GuardDecision.allow()

    def consume_quota(self) -> GuardDecision:
        return GuardDecision.allow()


class DenyingRateLimiter(AllowingLimiter):
    def check_rate(self, client_ip: str) -> GuardDecision:
        return GuardDecision.deny(RATE_LIMITED)


def _counter(store: FakeUsageStore, *, clock: Any = None) -> UsageCounter:
    return UsageCounter(store, clock=clock or (lambda: TODAY))


# --- the counter itself ---


def test_record_served_increments_the_utc_daily_doc() -> None:
    store = FakeUsageStore()
    counter = _counter(store)

    counter.record_served()

    assert store.store[f"{USAGE_DOC_PREFIX}2026-10-22"][SERVED_FIELD] == 1
    assert store.store[f"{USAGE_DOC_PREFIX}2026-10-22"].get(DECLINED_FIELD, 0) == 0


def test_repeated_increments_accumulate_per_field() -> None:
    store = FakeUsageStore()
    counter = _counter(store)

    counter.record_served()
    counter.record_served()
    counter.record_declined()
    counter.record_declined()
    counter.record_declined()

    doc = store.store[f"{USAGE_DOC_PREFIX}2026-10-22"]
    assert doc[SERVED_FIELD] == 2
    assert doc[DECLINED_FIELD] == 3


def test_the_daily_doc_rolls_over_at_utc_midnight() -> None:
    store = FakeUsageStore()
    clock = [TODAY]
    counter = _counter(store, clock=lambda: clock[0])

    counter.record_served()
    clock[0] = datetime(2026, 10, 23, 0, 0, 1, tzinfo=UTC)
    counter.record_served()

    assert store.store[f"{USAGE_DOC_PREFIX}2026-10-22"][SERVED_FIELD] == 1
    assert store.store[f"{USAGE_DOC_PREFIX}2026-10-23"][SERVED_FIELD] == 1


def test_counter_error_is_fail_open_and_logged_without_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    counter = _counter(FakeUsageStore(fail=True))

    with caplog.at_level(logging.WARNING, logger="janbot.usage"):
        counter.record_served()
        counter.record_declined()

    records = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "janbot.usage"
    ]
    assert {"event": "usage-counter-error", "counter": "served"} in records
    assert {"event": "usage-counter-error", "counter": "declined"} in records


def test_record_methods_take_no_ip_or_text() -> None:
    """The counter API has no parameter to record an IP or any text."""
    for method in (UsageCounter.record_served, UsageCounter.record_declined):
        assert list(inspect.signature(method).parameters) == ["self"]


# --- the read side ---


def test_read_day_returns_the_totals() -> None:
    store = FakeUsageStore()
    _counter(store).record_served()
    _counter(store).record_declined()
    _counter(store).record_declined()

    assert read_day(store, "2026-10-22") == (1, 2)


def test_read_day_of_a_missing_doc_is_zero_zero() -> None:
    assert read_day(FakeUsageStore(), "2026-10-22") == (0, 0)


def test_cli_prints_per_date_totals(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    store = FakeUsageStore()
    store.store[f"{USAGE_DOC_PREFIX}2026-10-22"] = {"served": 12, "declined": 3}
    monkeypatch.setattr(
        firestore, "Client", lambda *, project, database: store
    )

    code = main(["--date", "2026-10-22"], config=_config(project="p"))

    out = capsys.readouterr().out
    assert code == 0
    assert "date" in out and "served" in out and "declined" in out
    assert f"2026-10-22  {12:>6}  {3:>8}" in out


def test_cli_days_reads_a_range_ending_today(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr("janbot.guardrails.usage.datetime", _FixedDatetime)
    store = FakeUsageStore()
    store.store[f"{USAGE_DOC_PREFIX}2026-10-21"] = {"served": 2, "declined": 0}
    monkeypatch.setattr(firestore, "Client", lambda *, project, database: store)

    code = main(["--days", "3"], config=_config(project="p"))

    out = capsys.readouterr().out
    assert code == 0
    assert "2026-10-20" in out and "2026-10-21" in out and "2026-10-22" in out
    assert out.index("2026-10-20") < out.index("2026-10-21") < out.index("2026-10-22")


def test_cli_without_a_project_fails_clearly(capsys) -> None:
    code = main(["--date", "2026-10-22"], config=_config(project=None))

    err = capsys.readouterr().err
    assert code == 2
    assert "JANBOT_FIRESTORE_PROJECT" in err


def test_cli_without_adc_fails_clearly(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def no_adc(*, project, database):
        raise RuntimeError("Your default credentials were not found")

    monkeypatch.setattr(firestore, "Client", no_adc)

    code = main(["--date", "2026-10-22"], config=_config(project="p"))

    err = capsys.readouterr().err
    assert code == 1
    assert "could not be read" in err
    assert "credentials" in err


def test_cli_rejects_a_bad_date(capsys) -> None:
    code = main(["--date", "not-a-date"], config=_config(project="p"))

    err = capsys.readouterr().err
    assert code == 2
    assert "not-a-date" in err


def test_cli_requires_exactly_one_selector(capsys) -> None:
    with pytest.raises(SystemExit):
        main([], config=_config(project="p"))
    with pytest.raises(SystemExit):
        main(["--date", "2026-10-22", "--days", "2"], config=_config(project="p"))


# --- the seam through the app ---


class CountingProgram:
    def __init__(self, response: ChatResponse | None = None) -> None:
        self.calls = 0
        self.response = response

    def __call__(self, *, question: str):
        self.calls += 1
        if self.response is not None:
            return self.response
        raise LowRelevance("low")


class ErrorProgram:
    def __call__(self, *, question: str):
        raise ValueError("boom")


def _config(project: str | None) -> Config:
    return Config(
        model_mode="eval",
        model_snapshot="m",
        judge_model="m",
        corpus_path=PROJECT_ROOT / "public_profile_org",
        index_path=PROJECT_ROOT / "chroma_db",
        program_path=None,
        temperature=0.0,
        seed=0,
        top_k=4,
        retrieval_mode="hybrid",
        retrieval_window="chunks",
        relevance_threshold=0.26,
        output_guard="on",
        guardrails="on",
        cache_path=None,
        rate_limit=10,
        rate_window_seconds=600,
        daily_quota=500,
        max_question_chars=2000,
        max_body_bytes=8192,
        cors_origins=None,
        firestore_project=project,
        firestore_database="(default)",
    )


@pytest.fixture
def indexed_corpus(
    tmp_path: Path,
    embedder,
    write_org,
) -> tuple[Path, Path]:
    corpus = tmp_path / "public_profile_org"
    write_org(corpus / "profile.org", heading="About", body="Search infrastructure engineer.")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)
    return corpus, index_path


def _app(
    corpus: Path,
    index_path: Path,
    embedder,
    *,
    usage: Any = None,
    limiter: Any = None,
    cache_path: Path | None = None,
    program: Any = None,
):
    env: dict[str, str] = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "JANBOT_GUARDRAILS": "on",
    }
    if cache_path is not None:
        env["JANBOT_CACHE_PATH"] = str(cache_path)
    app = create_app(
        env=env,
        embedder=embedder,
        lm_factory=lambda **_: DummyLM([]),
        limiter=limiter,
        usage=usage,
    )
    app.state.program = program
    return app


def _cache_file(tmp_path: Path, question: str) -> Path:
    path = tmp_path / "cache" / "answers.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "metadata": {
                    "version": 1,
                    "run_id": "run-1",
                    "date": "2026-10-20",
                    "model_mode": "production",
                    "requested_model": "openrouter/auto",
                    "routed_models": ["m"],
                    "dataset_sha256": "x",
                    "corpus_commit": "abc",
                    "corpus_sha256": "x",
                    "output_guard": "on",
                },
                "entries": [
                    {
                        "question": question,
                        "response": {
                            "status": "answered",
                            "answer": "Cached answer.",
                            "citations": [{"source": "profile.org"}],
                            "reason": None,
                        },
                        "routed_model": "m",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_answered_reply_records_served(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    usage = RecordingUsage()
    program = CountingProgram(
        ChatResponse(status="answered", answer="A.", citations=[{"source": "profile.org"}])
    )
    app = _app(corpus, index_path, embedder, usage=usage, limiter=AllowingLimiter(), program=program)

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert (usage.served, usage.declined) == (1, 0)


def test_cache_hit_records_served_without_a_model_call(
    indexed_corpus, embedder, tmp_path
) -> None:
    corpus, index_path = indexed_corpus
    usage = RecordingUsage()
    program = CountingProgram(
        ChatResponse(status="answered", answer="A.", citations=[{"source": "profile.org"}])
    )
    cache_path = _cache_file(tmp_path, "What is your search experience?")
    app = _app(
        corpus,
        index_path,
        embedder,
        usage=usage,
        limiter=AllowingLimiter(),
        cache_path=cache_path,
        program=program,
    )

    response = TestClient(app).post(
        "/chat", json={"question": "  WHAT is your   search experience? "}
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Cached answer."
    assert program.calls == 0
    assert (usage.served, usage.declined) == (1, 0)


def test_insufficient_reply_records_declined(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    usage = RecordingUsage()
    app = _app(
        corpus,
        index_path,
        embedder,
        usage=usage,
        limiter=AllowingLimiter(),
        program=CountingProgram(),
    )

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 200
    assert response.json()["status"] == "insufficient"
    assert (usage.served, usage.declined) == (0, 1)


def test_rate_refusal_records_declined(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    usage = RecordingUsage()
    program = CountingProgram(
        ChatResponse(status="answered", answer="A.", citations=[{"source": "profile.org"}])
    )
    app = _app(corpus, index_path, embedder, usage=usage, limiter=DenyingRateLimiter(), program=program)

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 429
    assert (usage.served, usage.declined) == (0, 1)


def test_store_error_records_declined(indexed_corpus, embedder) -> None:
    """A 503 store-error refusal is a route-level guardrail refusal: declined."""
    corpus, index_path = indexed_corpus
    usage = RecordingUsage()
    program = CountingProgram(
        ChatResponse(status="answered", answer="A.", citations=[{"source": "profile.org"}])
    )

    class StoreErrorLimiter(AllowingLimiter):
        def check_rate(self, client_ip: str) -> GuardDecision:
            return GuardDecision.deny(STORE_ERROR)

    app = _app(corpus, index_path, embedder, usage=usage, limiter=StoreErrorLimiter(), program=program)

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 503
    assert (usage.served, usage.declined) == (0, 1)


def test_over_long_question_records_declined(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    usage = RecordingUsage()
    program = CountingProgram(
        ChatResponse(status="answered", answer="A.", citations=[{"source": "profile.org"}])
    )
    app = _app(corpus, index_path, embedder, usage=usage, limiter=AllowingLimiter(), program=program)

    response = TestClient(app).post("/chat", json={"question": "x" * 2001})

    assert response.status_code == 422
    assert (usage.served, usage.declined) == (0, 1)


def test_body_limit_refusal_is_not_counted(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    usage = RecordingUsage()
    program = CountingProgram(
        ChatResponse(status="answered", answer="A.", citations=[{"source": "profile.org"}])
    )
    app = _app(corpus, index_path, embedder, usage=usage, limiter=AllowingLimiter(), program=program)

    response = TestClient(app).post(
        "/chat",
        content=json.dumps({"question": "x" * 9000}),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert (usage.served, usage.declined) == (0, 0)


def test_a_500_is_neither_served_nor_declined(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    usage = RecordingUsage()
    app = _app(
        corpus, index_path, embedder, usage=usage, limiter=AllowingLimiter(), program=ErrorProgram()
    )

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 500
    assert (usage.served, usage.declined) == (0, 0)


def test_a_failing_counter_never_denies_the_request(
    indexed_corpus, embedder, caplog
) -> None:
    corpus, index_path = indexed_corpus
    usage = UsageCounter(FakeUsageStore(fail=True), clock=lambda: TODAY)
    program = CountingProgram(
        ChatResponse(status="answered", answer="A.", citations=[{"source": "profile.org"}])
    )
    app = _app(corpus, index_path, embedder, usage=usage, limiter=AllowingLimiter(), program=program)

    with caplog.at_level(logging.WARNING, logger="janbot.usage"):
        response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert program.calls == 1
    records = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "janbot.usage"
    ]
    assert {"event": "usage-counter-error", "counter": "served"} in records


def test_no_counter_is_built_without_a_firestore_project(
    indexed_corpus, embedder
) -> None:
    corpus, index_path = indexed_corpus
    program = CountingProgram(
        ChatResponse(status="answered", answer="A.", citations=[{"source": "profile.org"}])
    )
    app = _app(corpus, index_path, embedder, limiter=AllowingLimiter(), program=program)

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 200
    assert app.state.usage is None
