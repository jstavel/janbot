"""Port-level tests for ``POST /chat`` — the epic's tracer bullet.

Tests exercise only the HTTP port (AD-7): each builds its own app through
``create_app`` with the conftest stub embedder and a recording LM factory that
returns a canned-answer ``dspy.utils.DummyLM`` claiming a fixed set of source
labels — never a real ``dspy.LM``, no network. Expectations follow the story's
I/O matrix.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from dspy.utils import DummyLM
from fastapi.testclient import TestClient

from janbot.api.contract import INSUFFICIENT_ANSWER, ChatResponse
from janbot.api.main import create_app
from janbot.ingest import index_corpus
from janbot.store import VectorStore

Embedder = Callable[[list[str]], list[list[float]]]

DEFAULT_SNAPSHOT = "openrouter/openai/gpt-4o-mini-2024-07-18"
OPENROUTER_MODEL = "openrouter/auto"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

CANNED_ANSWER = "I work on search infrastructure."
DEFAULT_CITATIONS = ["profile.org", "projects.org"]


def _assert_insufficiency(response) -> None:
    """Assert a 200 insufficiency reply: the fixed line, no citations, no answer leak."""
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "insufficient"
    assert body["citations"] == []
    assert body["answer"] == INSUFFICIENT_ANSWER
    assert CANNED_ANSWER not in response.text


class StubLMFactory:
    """Callable factory recording build kwargs; yields a canned-answer DummyLM.

    The DummyLM claims ``citations`` as the source labels it derived the answer
    from — every app under test gets its own instance, so the script never
    crosses requests. One app builds one LM at startup, so the script repeats the
    same canned answer enough times to serve every request the test posts.
    """

    REPEATS = 16

    def __init__(self, citations: list[str] | None = None) -> None:
        self.citations = list(DEFAULT_CITATIONS if citations is None else citations)
        self.history: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> DummyLM:
        self.history.append(kwargs)
        answer = {"answer": CANNED_ANSWER, "citations": list(self.citations)}
        return DummyLM([dict(answer) for _ in range(self.REPEATS)])


class SourcelessChunk:
    """Chunk-shaped stand-in whose ``source_path`` was never recorded."""

    id = "unattributed::0::Heading"
    text = "Search infrastructure engineer."
    source_path: Any = None
    breadcrumb = "Heading"


class ForeignChunk:
    """Chunk-shaped stand-in whose ``source_path`` lies outside the corpus root."""

    id = "foreign::0::Heading"
    text = "Search infrastructure engineer."
    source_path = "/srv/elsewhere/secret.org"
    breadcrumb = "Heading"


class SharedSourceChunk:
    """Chunk-shaped stand-in; several instances share one ``source_path``."""

    def __init__(self, ordinal: int, text: str, source_path: str) -> None:
        self.id = f"{source_path}::{ordinal}::Heading"
        self.text = text
        self.source_path = source_path
        self.breadcrumb = "Heading"


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


def _chat_env(corpus: Path, index_path: Path) -> dict[str, str]:
    """Environment wiring the corpus root and index the fixtures built."""
    return {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
    }


def _client(corpus: Path, index_path: Path, embedder: Embedder) -> TestClient:
    app = create_app(
        env=_chat_env(corpus, index_path),
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
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=factory,
    )

    response = TestClient(app).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered"
    assert ChatResponse.model_validate(data).citations
    assert data["answer"] == CANNED_ANSWER
    sources = [citation["source"] for citation in data["citations"]]
    assert sources == ["profile.org", "projects.org"]
    assert factory.history == [
        {"model": DEFAULT_SNAPSHOT, "temperature": 0.0, "api_base": OPENROUTER_API_BASE, "seed": 0}
    ]


def test_chat_program_exposes_the_retrieved_set_not_the_cited_set(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """The seam mirrors retrieval, not citations: a retrieved-but-uncited source still appears."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=StubLMFactory(citations=["profile.org"]),
    )
    program = app.state.program
    assert program.last_retrieved_sources is None

    response = TestClient(app).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 200
    cited = [citation["source"] for citation in response.json()["citations"]]
    assert cited == ["profile.org"]
    inferred = program.last_retrieved_sources
    assert inferred is not None
    assert "projects.org" not in cited
    assert "projects.org" in inferred


def test_openapi_exposes_status_from_the_contract(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """The OpenAPI derives the decline shape from Pydantic — no hand-written schema."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )

    schema = app.openapi()["components"]["schemas"]["ChatResponse"]

    assert set(schema["properties"]["status"]["enum"]) == {"answered", "insufficient"}
    assert schema["properties"]["status"]["default"] == "answered"


def test_chat_missing_mistyped_or_blank_question_is_rejected_with_422(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    client = _client(*indexed_corpus, embedder)

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
    corpus, index_path = indexed_corpus
    factory = StubLMFactory()
    index_env = _chat_env(corpus, index_path)

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
    eval_kwargs, production_kwargs = factory.history
    assert eval_kwargs["seed"] == 0
    assert "seed" not in production_kwargs
    assert factory.history == [
        {"model": DEFAULT_SNAPSHOT, "temperature": 0.0, "api_base": OPENROUTER_API_BASE, "seed": 0},
        {
            "model": OPENROUTER_MODEL,
            "temperature": 0.0,
            "api_base": OPENROUTER_API_BASE,
            "api_key": "sk-test",
        },
    ]


def test_chat_same_question_twice_returns_byte_identical_json(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """Determinism at the port: one app, two identical questions, identical bodies."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )
    client = TestClient(app)
    question = {"question": "What search infrastructure have you built?"}

    first = client.post("/chat", json=question)
    second = client.post("/chat", json=question)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.text == second.text


def test_chat_two_identical_env_apps_return_identical_json(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """Two apps from identical env build identical LM kwargs and answer identically."""
    corpus, index_path = indexed_corpus
    env = _chat_env(corpus, index_path)
    first_factory = StubLMFactory()
    second_factory = StubLMFactory()
    first_app = create_app(env=env, embedder=embedder, lm_factory=first_factory)
    second_app = create_app(env=env, embedder=embedder, lm_factory=second_factory)
    question = {"question": "What search infrastructure have you built?"}

    first = TestClient(first_app).post("/chat", json=question)
    second = TestClient(second_app).post("/chat", json=question)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first_factory.history == second_factory.history
    assert first_factory.history == [
        {"model": DEFAULT_SNAPSHOT, "temperature": 0.0, "api_base": OPENROUTER_API_BASE, "seed": 0}
    ]


def test_chat_empty_index_declines_with_200_insufficiency(
    tmp_path: Path,
    embedder: Embedder,
) -> None:
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(tmp_path / "empty")},
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )
    assert VectorStore(tmp_path / "empty", embedder).ids() == set()

    response = TestClient(app).post("/chat", json={"question": "anything"})

    _assert_insufficiency(response)


def test_chat_sourceless_chunk_is_excluded_from_retrieval_with_200_insufficiency(
    tmp_path: Path,
    embedder: Embedder,
) -> None:
    """The store scope excludes a chunk with no ``source_path``: retrieval is empty, a decline."""
    index_path = tmp_path / "index"
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(index_path)},
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )
    VectorStore(index_path, embedder).upsert([SourcelessChunk()])

    response = TestClient(app).post("/chat", json={"question": "anything"})

    _assert_insufficiency(response)


def test_chat_cites_only_the_retrieved_source(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """Derived-from pin: with one chunk retrieved, only that chunk's source is cited."""
    corpus, index_path = indexed_corpus
    factory = StubLMFactory(citations=["profile.org"])
    app = create_app(
        env={**_chat_env(corpus, index_path), "JANBOT_TOP_K": "1"},
        embedder=embedder,
        lm_factory=factory,
    )

    response = TestClient(app).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 200
    sources = [citation["source"] for citation in response.json()["citations"]]
    assert sources == ["profile.org"]


def test_chat_indexed_but_unretrieved_source_can_never_be_cited(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """Fail-closed: a source that was indexed but not retrieved is never a valid claim."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env={**_chat_env(corpus, index_path), "JANBOT_TOP_K": "1"},
        embedder=embedder,
        lm_factory=StubLMFactory(citations=["projects.org"]),
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 500
    assert isinstance(response.json()["detail"], str)
    assert CANNED_ANSWER not in response.text


def test_chat_bracketed_claim_label_is_normalized(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """A model echoing the displayed ``[source]`` form still matches the retrieved source."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=StubLMFactory(citations=["[profile.org]", " [projects.org] "]),
    )

    response = TestClient(app).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 200
    sources = [citation["source"] for citation in response.json()["citations"]]
    assert sources == ["profile.org", "projects.org"]


def test_chat_uncited_answer_declines_with_200_insufficiency(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """The model claims no sources: the pipeline declines, so the port answers insufficient."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=StubLMFactory(citations=[]),
    )

    response = TestClient(app).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    _assert_insufficiency(response)


def test_chat_unknown_source_claim_is_rejected_with_500_envelope(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """A claim naming a source outside the retrieved set is unverifiable: reject, do not drop."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=StubLMFactory(citations=["elsewhere.md"]),
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "unverifiable source claim" in detail
    assert "outside the retrieved chunks" in detail
    assert "elsewhere.md" not in response.text
    assert CANNED_ANSWER not in response.text


def test_chat_foreign_only_index_declines_with_200_insufficiency(
    tmp_path: Path,
    embedder: Embedder,
) -> None:
    """The store scope excludes the out-of-root chunk, so retrieval is empty: a decline."""
    index_path = tmp_path / "index"
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(index_path)},
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )
    VectorStore(index_path, embedder).upsert([ForeignChunk()])

    response = TestClient(app).post("/chat", json={"question": "anything"})

    _assert_insufficiency(response)
    assert "/srv/elsewhere" not in response.text


def test_chat_foreign_and_public_index_cites_only_public_source(
    tmp_path: Path,
    embedder: Embedder,
) -> None:
    """Port row: a foreign chunk never enters retrieval, so only the public source can be cited."""
    corpus = tmp_path / "public_profile_org"
    index_path = tmp_path / "index"
    public_source = str(corpus / "profile.org")
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(index_path), "JANBOT_CORPUS_PATH": str(corpus)},
        embedder=embedder,
        lm_factory=StubLMFactory(citations=["profile.org"]),
    )
    VectorStore(index_path, embedder).upsert(
        [
            SharedSourceChunk(0, "Search infrastructure engineer.", public_source),
            ForeignChunk(),
        ]
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"question": "anything"}
    )

    assert response.status_code == 200
    sources = [citation["source"] for citation in response.json()["citations"]]
    assert sources == ["profile.org"]
    assert "/srv/elsewhere" not in response.text


def test_chat_shared_source_is_deduped_to_one_citation(
    tmp_path: Path,
    embedder: Embedder,
) -> None:
    """Multiple chunks sharing one source cite it once: one entry per distinct source."""
    corpus = tmp_path / "corpus"
    index_path = tmp_path / "index"
    shared_source = str(corpus / "shared.org")
    app = create_app(
        env={"JANBOT_INDEX_PATH": str(index_path), "JANBOT_CORPUS_PATH": str(corpus)},
        embedder=embedder,
        lm_factory=StubLMFactory(citations=["shared.org"]),
    )
    VectorStore(index_path, embedder).upsert(
        [
            SharedSourceChunk(0, "Search infrastructure engineer.", shared_source),
            SharedSourceChunk(1, "Built JanBot, a retrieval assistant.", shared_source),
        ]
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"question": "What have you built?"}
    )

    assert response.status_code == 200
    sources = [citation["source"] for citation in response.json()["citations"]]
    assert sources == ["shared.org"]


def test_chat_citations_leak_no_absolute_paths(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """No 200 body may carry an absolute filesystem path: citations are corpus-relative."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )

    response = TestClient(app).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 200
    body = response.text
    assert str(corpus.parent) not in body
    assert str(corpus) not in body
    assert str(Path.home()) not in body
    for citation in response.json()["citations"]:
        assert not citation["source"].startswith("/")


def test_chat_dspy_parse_failure_is_mapped_to_500_envelope(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """A real adapter parse failure (a ``DSPyError``, not a ``ValueError``) maps to the envelope.

    The LM is injected through the sanctioned ``lm_factory`` seam and returns an
    unparseable completion, so ``dspy`` raises a genuine parse error on the real
    adapter path; it must surface as 500 with the standard ``{detail}`` body.
    """
    corpus, index_path = indexed_corpus

    def unparseable(**kwargs: object) -> DummyLM:
        return DummyLM(["<unparseable raw completion>"])

    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=unparseable,
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "the model response could not be processed"


def test_chat_unexpected_processing_error_is_mapped_to_500_envelope(
    indexed_corpus: tuple[Path, Path],
) -> None:
    """A non-dspy failure while processing yields a non-leaking ``{detail}`` envelope.

    The failure is injected through the sanctioned ``embedder`` seam (raised during
    retrieval), so the port sees an unexpected ``RuntimeError``.
    """
    corpus, index_path = indexed_corpus

    def exploding_embedder(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("/secret/internal/path")

    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=exploding_embedder,
        lm_factory=StubLMFactory(),
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"question": "anything"}
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "the service failed to process the request"
    assert "/secret/internal/path" not in response.text


def test_chat_citation_order_follows_retrieval_not_claim_order_or_sort(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    """Citations follow retrieval order — not claim order, and not label sort order.

    The corpus is built so retrieval rank ("zulu.org" first) differs from
    lexicographic order ("alpha.org" first); two apps claim the sources in
    opposite orders and must still emit identical bodies.
    """
    corpus = tmp_path / "public_profile_org"
    corpus.mkdir()
    write_org(corpus / "alpha.org", "Topic", body="alpha")
    write_org(corpus / "zulu.org", "Topic", body="zulu zulu zulu zulu")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)
    env = _chat_env(corpus, index_path)
    question = {"question": "zulu zulu zulu"}

    forward = create_app(
        env=env, embedder=embedder, lm_factory=StubLMFactory(citations=["zulu.org", "alpha.org"])
    )
    reverse = create_app(
        env=env, embedder=embedder, lm_factory=StubLMFactory(citations=["alpha.org", "zulu.org"])
    )

    first = TestClient(forward).post("/chat", json=question)
    second = TestClient(reverse).post("/chat", json=question)

    assert first.status_code == 200 and second.status_code == 200
    sources = [citation["source"] for citation in first.json()["citations"]]
    assert sources == ["zulu.org", "alpha.org"]  # retrieval rank, not sorted
    assert first.text == second.text


def test_chat_repeated_claim_yields_one_citation(
    indexed_corpus: tuple[Path, Path],
    embedder: Embedder,
) -> None:
    """A repeated claim still yields one citation per distinct source."""
    corpus, index_path = indexed_corpus
    app = create_app(
        env=_chat_env(corpus, index_path),
        embedder=embedder,
        lm_factory=StubLMFactory(citations=["profile.org", "profile.org", "projects.org"]),
    )

    response = TestClient(app).post(
        "/chat", json={"question": "What search infrastructure have you built?"}
    )

    assert response.status_code == 200
    sources = [citation["source"] for citation in response.json()["citations"]]
    assert sources == ["profile.org", "projects.org"]


def test_create_app_fails_fast_when_index_has_out_of_scope_chunks(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    """A serve corpus root that excludes indexed chunks fails fast, not silently.

    Guards the ingest↔serve alignment: an index built from a different (broader or
    foreign) root must not start serving with a shifted citation boundary.
    """
    corpus = tmp_path / "public_profile_org"
    corpus.mkdir()
    write_org(corpus / "profile.org", "About", body="Public profile body.")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)
    VectorStore(index_path, embedder).upsert([ForeignChunk()])

    with pytest.raises(ValueError) as excinfo:
        create_app(
            env={"JANBOT_INDEX_PATH": str(index_path), "JANBOT_CORPUS_PATH": str(corpus)},
            embedder=embedder,
            lm_factory=StubLMFactory(),
        )

    assert "outside" in str(excinfo.value)
