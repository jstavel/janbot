"""CORS allowance tests (ADR-008): the Pages origin, POST-only, opt-in knob.

The matrix the tests pin (the story's I/O rows):

- a preflight from ``https://jstavel.github.io`` is answered 200 with the
  echoed origin;
- a preflight from any other origin, or for any method other than POST, is a
  real 400 refusal that never reaches the route and carries no
  ``Access-Control-Allow-Origin``;
- a browser POST from the allowed origin gets the origin echoed — including
  on the 429/413/422 refusals, so the widget can read them; a POST from any
  other origin gets no ACAO header and non-browser callers are unaffected;
- with the knob unset the middleware is absent and behavior is today's.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from dspy.utils import DummyLM
from fastapi.testclient import TestClient

from janbot.api.contract import ChatResponse
from janbot.api.main import StrictPreflightCORSMiddleware, create_app
from janbot.guardrails.limits import GuardDecision, RATE_LIMITED
from janbot.ingest import index_corpus

PAGES_ORIGIN = "https://jstavel.github.io"
OTHER_ORIGIN = "https://example.com"
ANSWER = "Search infrastructure."
SOURCE = "profile.org"

Embedder = Callable[[list[str]], list[list[float]]]


class DenyingRateLimiter:
    def __init__(self) -> None:
        self.rate_calls: list[str] = []

    def check_rate(self, client_ip: str) -> GuardDecision:
        self.rate_calls.append(client_ip)
        return GuardDecision.deny(RATE_LIMITED)

    def consume_quota(self) -> GuardDecision:
        return GuardDecision.allow()


class AllowingLimiter:
    def check_rate(self, client_ip: str) -> GuardDecision:
        return GuardDecision.allow()

    def consume_quota(self) -> GuardDecision:
        return GuardDecision.allow()


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


def _app(
    corpus: Path,
    index_path: Path,
    embedder: Embedder,
    *,
    limiter=None,
    cors_origins: str | None = PAGES_ORIGIN,
):
    extra: dict[str, str] = {"JANBOT_GUARDRAILS": "on"}
    if cors_origins is not None:
        extra["JANBOT_CORS_ORIGINS"] = cors_origins
    app = create_app(
        env={
            "JANBOT_CORPUS_PATH": str(corpus),
            "JANBOT_INDEX_PATH": str(index_path),
            **extra,
        },
        embedder=embedder,
        lm_factory=lambda **_: DummyLM([]),
        limiter=limiter,
    )

    def program(*, question: str) -> ChatResponse:
        return ChatResponse(
            status="answered", answer=ANSWER, citations=[{"source": SOURCE}]
        )

    app.state.program = program
    return app


def test_preflight_from_the_pages_origin_is_allowed(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    limiter = DenyingRateLimiter()
    app = _app(corpus, index_path, embedder, limiter=limiter)

    response = TestClient(app).options(
        "/chat",
        headers={
            "Origin": PAGES_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN
    assert response.headers["access-control-allow-methods"] == "POST"
    assert "access-control-allow-credentials" not in response.headers
    # A preflight is answered at the middleware edge: the route never runs.
    assert limiter.rate_calls == []


def test_preflight_from_another_origin_is_refused_without_acao(
    indexed_corpus, embedder
) -> None:
    corpus, index_path = indexed_corpus
    limiter = DenyingRateLimiter()
    app = _app(corpus, index_path, embedder, limiter=limiter)

    response = TestClient(app).options(
        "/chat",
        headers={"Origin": OTHER_ORIGIN, "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 400
    assert "Disallowed CORS origin" in response.text
    assert "access-control-allow-origin" not in response.headers
    assert limiter.rate_calls == []


def test_preflight_for_a_non_post_method_is_refused_without_acao(
    indexed_corpus, embedder
) -> None:
    corpus, index_path = indexed_corpus
    limiter = DenyingRateLimiter()
    app = _app(corpus, index_path, embedder, limiter=limiter)

    response = TestClient(app).options(
        "/chat",
        headers={"Origin": PAGES_ORIGIN, "Access-Control-Request-Method": "DELETE"},
    )

    assert response.status_code == 400
    assert "Disallowed CORS method" in response.text
    assert "access-control-allow-origin" not in response.headers
    assert limiter.rate_calls == []


def test_browser_post_from_the_pages_origin_is_served_with_acao(
    indexed_corpus, embedder
) -> None:
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder)

    response = TestClient(app).post(
        "/chat", json={"question": "A question?"}, headers={"Origin": PAGES_ORIGIN}
    )

    assert response.status_code == 200
    assert response.json()["answer"] == ANSWER
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN


def test_acao_is_echoed_on_the_429_refusal(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder, limiter=DenyingRateLimiter())

    response = TestClient(app).post(
        "/chat", json={"question": "A question?"}, headers={"Origin": PAGES_ORIGIN}
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "too many requests"
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN


def test_acao_is_echoed_on_the_422_refusal(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder)

    response = TestClient(app).post(
        "/chat", json={"question": "x" * 2001}, headers={"Origin": PAGES_ORIGIN}
    )

    assert response.status_code == 422
    assert "maximum length" in response.json()["detail"]
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN


def test_acao_is_echoed_on_the_413_refusal(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder)

    response = TestClient(app).post(
        "/chat",
        content=json.dumps({"question": "x" * 9000}),
        headers={"content-type": "application/json", "Origin": PAGES_ORIGIN},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "request body too large"
    assert response.headers["access-control-allow-origin"] == PAGES_ORIGIN


def test_browser_post_from_another_origin_carries_no_acao(
    indexed_corpus, embedder
) -> None:
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder)

    response = TestClient(app).post(
        "/chat", json={"question": "A question?"}, headers={"Origin": OTHER_ORIGIN}
    )

    # The server answers normally; it is the browser that blocks the read.
    assert response.status_code == 200
    assert response.json()["answer"] == ANSWER
    assert "access-control-allow-origin" not in response.headers


def test_non_browser_callers_are_unaffected(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder)
    client = TestClient(app)

    post = client.post("/chat", json={"question": "A question?"})

    # Same status, body and no allow header; the stock middleware adds only
    # the `Vary: Origin` cache hint, which is invisible to the caller.
    assert post.status_code == 200
    assert post.json()["answer"] == ANSWER
    assert "access-control-allow-origin" not in post.headers


def test_production_mode_exposes_no_interactive_docs(indexed_corpus, embedder) -> None:
    """With allUsers ingress, /docs, /redoc and /openapi.json would be public."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env={
            "JANBOT_CORPUS_PATH": str(corpus),
            "JANBOT_INDEX_PATH": str(index_path),
            "JANBOT_MODEL_MODE": "production",
            "OPENROUTER_API_KEY": "test-key",
        },
        embedder=embedder,
        lm_factory=lambda **_: DummyLM([]),
        limiter=AllowingLimiter(),
        require_cache=False,
    )
    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/health").status_code == 200


def test_eval_mode_still_exposes_the_docs(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    app = create_app(
        env={
            "JANBOT_CORPUS_PATH": str(corpus),
            "JANBOT_INDEX_PATH": str(index_path),
        },
        embedder=embedder,
        lm_factory=lambda **_: DummyLM([]),
    )

    assert TestClient(app).get("/docs").status_code == 200


def test_unset_knob_adds_no_cors_middleware(indexed_corpus, embedder) -> None:
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder, cors_origins=None)
    client = TestClient(app)

    cors_middlewares = [
        middleware
        for middleware in app.user_middleware
        if issubclass(middleware.cls, StrictPreflightCORSMiddleware)
    ]
    options = client.options(
        "/chat",
        headers={"Origin": PAGES_ORIGIN, "Access-Control-Request-Method": "POST"},
    )
    post = client.post("/chat", json={"question": "A question?"})

    assert cors_middlewares == []
    # Today's behavior: no CORS answer for the preflight, no headers anywhere.
    assert options.status_code == 405
    assert "access-control-allow-origin" not in options.headers
    assert post.status_code == 200
    assert "access-control-allow-origin" not in post.headers


def test_unset_knob_leaves_the_full_suite_path_untouched(
    indexed_corpus, embedder
) -> None:
    """The unset knob is byte-identical to today: a plain POST works as before."""
    corpus, index_path = indexed_corpus
    app = _app(corpus, index_path, embedder, cors_origins=None)

    response = TestClient(app).post("/chat", json={"question": "A question?"})

    assert response.status_code == 200
    assert set(response.json()) == {"status", "answer", "citations", "reason"}
    assert set(response.headers) & {
        "access-control-allow-origin",
        "access-control-allow-methods",
        "access-control-max-age",
    } == set()
