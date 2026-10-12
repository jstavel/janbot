"""Port-level tests for ``POST /chat`` — the epic's tracer bullet.

Tests exercise only the HTTP port (AD-7): each builds its own app through
``create_app`` with the conftest stub embedder and a recording LM factory that
returns a canned-answer ``dspy.utils.DummyLM`` — never a real ``dspy.LM``, no
network. Expectations follow the story's I/O matrix.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from dspy.utils import DummyLM
from fastapi.testclient import TestClient

from janbot.api.contract import ChatResponse
from janbot.api.main import create_app
from janbot.ingest import index_corpus
from janbot.ingest.scope import located_path
from janbot.store import VectorStore

Embedder = Callable[[list[str]], list[list[float]]]

DEFAULT_SNAPSHOT = "openai/gpt-4o-mini-2024-07-18"
OPENROUTER_MODEL = "openrouter/auto"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

CANNED_ANSWER = "I work on search infrastructure."


class StubLMFactory:
    """Callable factory recording build kwargs; yields a canned-answer DummyLM."""

    def __init__(self) -> None:
        self.history: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> DummyLM:
        self.history.append(kwargs)
        return DummyLM([{"answer": CANNED_ANSWER}])


class SourcelessChunk:
    """Chunk-shaped stand-in whose ``source_path`` was never recorded."""

    id = "unattributed::0::Heading"
    text = "Search infrastructure engineer."
    source_path: Any = None
    breadcrumb = "Heading"


@pytest.fixture
def indexed_corpus(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> tuple[Path, Path]:
    """Write a small public corpus, index it with the stub embedder, return (corpus, index)."""
    corpus = tmp_path / "public_profile_org"
    write_org(corpus / "profile.org", heading="About", body="Search infrastructure engineer.")
    write_org(
        corpus / "projects.org",
        heading="Projects",
        body="Built JanBot, a RAG assistant over an org corpus.",
    )
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)
    return corpus, index_path


def _client(index_path: Path, embedder: Embedder) -> TestClient:
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(index_path)},
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )
    return TestClient(app)


def test_chat_happy_path_returns_answer_and_citations(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    corpus, index_path = indexed_corpus
    factory = StubLMFactory()
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(index_path)},
        embedder=embedder,
        lm_factory=factory,
    )

    response = TestClient(app).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 200
    data = response.json()
    assert ChatResponse.model_validate(data).citations
    assert data["answer"] == CANNED_ANSWER
    sources = [citation["source"] for citation in data["citations"]]
    assert sources == [
        str(located_path(corpus / "profile.org")),
        str(located_path(corpus / "projects.org")),
    ]
    assert factory.history == [{"model": DEFAULT_SNAPSHOT, "temperature": 0.0}]


def test_chat_missing_mistyped_or_blank_question_is_rejected_with_422(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    client = _client(indexed_corpus[1], embedder)

    for body in ({}, {"question": 123}, {"question": "   "}):
        response = client.post("/chat", json=body)
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize(
    "key_env",
    [{}, {"OPENROUTER_API_KEY": "   "}],
    ids=["absent", "blank"],
)
def test_chat_production_without_api_key_fails_fast_at_startup(
    tmp_path: Path,
    embedder: Embedder,
    key_env: dict[str, str],
) -> None:
    factory = StubLMFactory()

    with pytest.raises(ValueError) as excinfo:
        create_app(
            env={
                "JANBOT_MODEL_MODE": "production",
                "JANBOT_INDEX_PATH": str(tmp_path / "index"),
                **key_env,
            },
            embedder=embedder,
            lm_factory=factory,
        )

    assert factory.history == []
    message = str(excinfo.value)
    assert "OPENROUTER_API_KEY" in message
    assert "production" in message


def test_chat_model_routing_changes_with_environment_only(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    _, index_path = indexed_corpus
    factory = StubLMFactory()
    index_env = {"JANBOT_INDEX_PATH": str(index_path)}

    eval_app = create_app(env=index_env, embedder=embedder, lm_factory=factory)
    production_app = create_app(
        env={
            **index_env,
            "JANBOT_MODEL_MODE": "production",
            "OPENROUTER_API_KEY": "sk-test",
        },
        embedder=embedder,
        lm_factory=factory,
    )

    question = {"question": "What search infrastructure have you built?"}
    eval_response = TestClient(eval_app).post("/chat", json=question)
    production_response = TestClient(production_app).post("/chat", json=question)

    assert eval_response.status_code == 200
    assert production_response.status_code == 200
    assert eval_response.json()["answer"] == CANNED_ANSWER
    assert production_response.json()["answer"] == CANNED_ANSWER
    assert factory.history == [
        {"model": DEFAULT_SNAPSHOT, "temperature": 0.0},
        {
            "model": OPENROUTER_MODEL,
            "temperature": 0.0,
            "api_base": OPENROUTER_API_BASE,
            "api_key": "sk-test",
        },
    ]


def test_chat_empty_index_returns_503_with_detail_envelope(
    tmp_path: Path,
    embedder: Embedder,
) -> None:
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(tmp_path / "empty")},
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )
    assert VectorStore(tmp_path / "empty", embedder).ids() == set()

    response = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"question": "anything"}
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "0 chunks" in detail
    assert "corpus" in detail


def test_chat_sourceless_chunk_returns_500_with_detail_envelope(
    tmp_path: Path,
    embedder: Embedder,
) -> None:
    index_path = tmp_path / "index"
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(index_path)},
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )
    VectorStore(index_path, embedder).upsert([SourcelessChunk()])

    response = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"question": "anything"}
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "source_path" in detail
