"""Request-layer guardrail tests: cache hit, rate, quota, bounds, fail-closed, off."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from dspy.utils import DummyLM
from fastapi.testclient import TestClient

from janbot.api.contract import ChatResponse
from janbot.api.main import create_app
from janbot.guardrails.limits import GuardDecision, QUOTA_EXCEEDED, RATE_LIMITED, STORE_ERROR
from janbot.ingest import index_corpus

Embedder = Callable[[list[str]], list[list[float]]]

ANSWER = "Search infrastructure."
CACHE_PATH = "profile.org"


class CountingLMFactory:
    def __call__(self, **kwargs: object) -> DummyLM:
        return DummyLM([{"answer": ANSWER, "citations": [CACHE_PATH]}] * 8)


class RecordingLimiter:
    def __init__(self, *, rate_allowed: bool = True, quota_allowed: bool = True) -> None:
        self.rate_allowed = rate_allowed
        self.quota_allowed = quota_allowed
        self.rate_calls: list[str] = []
        self.quota_calls = 0

    def check_rate(self, client_ip: str) -> GuardDecision:
        self.rate_calls.append(client_ip)
        if not self.rate_allowed:
            return GuardDecision.deny(RATE_LIMITED)
        return GuardDecision.allow()

    def consume_quota(self) -> GuardDecision:
        self.quota_calls += 1
        if not self.quota_allowed:
            return GuardDecision.deny(QUOTA_EXCEEDED)
        return GuardDecision.allow()


class StoreErrorLimiter(RecordingLimiter):
    def check_rate(self, client_ip: str) -> GuardDecision:
        return GuardDecision.deny(STORE_ERROR)


@pytest.fixture
def indexed_corpus(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> tuple[Path, Path]:
    corpus = tmp_path / "public_profile_org"
    write_org(corpus / "profile.org", heading="About", body="Search infrastructure engineer.")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)
    return corpus, index_path


def _env(corpus: Path, index_path: Path, **extra: str) -> dict[str, str]:
    return {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        **extra,
    }


def _app(
    corpus: Path,
    index_path: Path,
    embedder: Embedder,
    *,
    limiter=None,
    cache_path: Path | None = None,
    guardrails: str | None = None,
):
    extra: dict[str, str] = {}
    if cache_path is not None:
        extra["JANBOT_CACHE_PATH"] = str(cache_path)
    if guardrails is not None:
        extra["JANBOT_GUARDRAILS"] = guardrails
    app = create_app(
        env=_env(corpus, index_path, **extra),
        embedder=embedder,
        lm_factory=CountingLMFactory(),
        limiter=limiter,
    )
    calls = {"model": 0}

    def program(*, question: str) -> ChatResponse:
        calls["model"] += 1
        return ChatResponse(
            status="answered",
            answer=ANSWER,
            citations=[{"source": CACHE_PATH}],
        )

    app.state.program = program
    app.state.model_calls = calls
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
                            "citations": [{"source": CACHE_PATH}],
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


def test_cache_hit_makes_zero_model_calls_and_is_contract_shaped(
    indexed_corpus, embedder, tmp_path
) -> None:
    corpus, index_path = indexed_corpus
    limiter = RecordingLimiter()
    cache_path = _cache_file(tmp_path, "What is your search experience?")
    app = _app(corpus, index_path, embedder, limiter=limiter, cache_path=cache_path)

    response = TestClient(app).post(
        "/chat", json={"question": "  WHAT is your   search experience? "}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Cached answer."
    assert ChatResponse.model_validate(body).citations
    assert app.state.model_calls["model"] == 0
    assert limiter.rate_calls == ["testclient"]
    assert limiter.quota_calls == 0


def test_rate_n_plus_one_is_refused(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    limiter = RecordingLimiter()
    app = _app(corpus, index_path, embedder, limiter=limiter)

    first = TestClient(app).post("/chat", json={"question": "First question?"})
    limiter.rate_allowed = False
    second = TestClient(app).post("/chat", json={"question": "Second question?"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert app.state.model_calls["model"] == 1


def test_quota_exhaustion_refuses_before_the_model(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    limiter = RecordingLimiter(quota_allowed=False)
    app = _app(corpus, index_path, embedder, limiter=limiter)

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 429
    assert "quota" in response.json()["detail"]
    assert app.state.model_calls["model"] == 0


def test_store_error_fails_closed(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder, limiter=StoreErrorLimiter())

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 503
    assert app.state.model_calls["model"] == 0


def test_over_long_question_is_rejected_before_rate_and_model(
    indexed_corpus, embedder
) -> None:
    corpus, index_path = indexed_corpus
    limiter = RecordingLimiter()
    app = _app(corpus, index_path, embedder, limiter=limiter)

    response = TestClient(app).post("/chat", json={"question": "x" * 2001})

    assert response.status_code == 422
    assert limiter.rate_calls == []
    assert app.state.model_calls["model"] == 0


def test_oversized_body_is_rejected_before_parsing(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    limiter = RecordingLimiter()
    app = _app(corpus, index_path, embedder, limiter=limiter)

    response = TestClient(app).post(
        "/chat",
        content=json.dumps({"question": "x" * 9000}),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert limiter.rate_calls == []
    assert app.state.model_calls["model"] == 0


def test_guardrail_off_bypasses_cache_rate_and_quota(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    limiter = RecordingLimiter(rate_allowed=False, quota_allowed=False)
    app = _app(
        corpus,
        index_path,
        embedder,
        limiter=limiter,
        guardrails="off",
    )

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 200
    assert app.state.model_calls["model"] == 1
    assert limiter.rate_calls == []
    assert limiter.quota_calls == 0
