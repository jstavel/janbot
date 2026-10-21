"""Decline attribution: logs name the component and cause, never the text."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from dspy.utils import DummyLM
from fastapi.testclient import TestClient

from janbot.api.main import create_app
from janbot.guardrails.limits import GuardDecision, RATE_LIMITED
from janbot.ingest import index_corpus
from janbot.pipeline.chat import LowRelevance, UncitedAnswer

Embedder = Callable[[list[str]], list[list[float]]]

SECRET_QUESTION = "What is the confidential launch date for project Bluebird?"
SECRET_TOKEN = "sk-never-log-this"


class AllowingLimiter:
    def check_rate(self, client_ip: str) -> GuardDecision:
        return GuardDecision.allow()

    def consume_quota(self) -> GuardDecision:
        return GuardDecision.allow()


class DenyingRateLimiter(AllowingLimiter):
    def check_rate(self, client_ip: str) -> GuardDecision:
        return GuardDecision.deny(RATE_LIMITED)


class RaisingProgram:
    def __init__(self, exc: Exception, action: str | None = None) -> None:
        self.exc = exc
        self.last_guard_action = action

    def __call__(self, *, question: str):
        raise self.exc


@pytest.fixture
def app_factory(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
):
    corpus = tmp_path / "corpus"
    write_org(corpus / "profile.org", "About", "Search infrastructure engineer.")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)

    def build(limiter=None):
        app = create_app(
            env={
                "JANBOT_CORPUS_PATH": str(corpus),
                "JANBOT_INDEX_PATH": str(index_path),
                "JANBOT_GUARDRAILS": "on",
            },
            embedder=embedder,
            lm_factory=lambda **_: DummyLM([]),
            limiter=limiter or AllowingLimiter(),
        )
        return app

    return build


def _records(caplog: pytest.LogCaptureFixture) -> list[dict]:
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "janbot.decline"
    ]


def test_theta_decline_records_component_and_cause_without_text(app_factory, caplog) -> None:
    app = app_factory()
    app.state.program = RaisingProgram(LowRelevance("low"))

    with caplog.at_level(logging.WARNING, logger="janbot.decline"):
        response = TestClient(app).post(
            "/chat", json={"question": SECRET_QUESTION, "extra": SECRET_TOKEN}
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "insufficient"
    records = _records(caplog)
    assert {"event": "decline", "component": "program", "cause": "low-relevance"} in records
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert SECRET_QUESTION not in logged
    assert SECRET_TOKEN not in logged


def test_guard_decline_records_the_guard_rule_without_text(app_factory, caplog) -> None:
    app = app_factory()
    app.state.program = RaisingProgram(
        UncitedAnswer("guard declined"), action="declined: commitment-claim"
    )

    with caplog.at_level(logging.WARNING, logger="janbot.decline"):
        response = TestClient(app).post("/chat", json={"question": SECRET_QUESTION})

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "insufficient"
    assert set(body) == {"status", "answer", "citations", "reason"}
    records = _records(caplog)
    assert {"event": "decline", "component": "program", "cause": "commitment-claim"} in records
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert SECRET_QUESTION not in logged


def test_guardrail_rate_denial_is_attributed_without_text(app_factory, caplog) -> None:
    app = app_factory(limiter=DenyingRateLimiter())

    with caplog.at_level(logging.WARNING, logger="janbot.decline"):
        response = TestClient(app).post("/chat", json={"question": SECRET_QUESTION})

    assert response.status_code == 429
    records = _records(caplog)
    assert {"event": "decline", "component": "guardrail", "cause": "rate_limited"} in records
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert SECRET_QUESTION not in logged
