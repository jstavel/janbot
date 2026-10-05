"""Tracer-bullet tests: index one public org file and retrieve it.

These tests never load the real embedding model. They always inject a
deterministic, offline stub embedder through the store's seam.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from janbot.ingest import Chunk, index_corpus, iter_org_files, read_org_file, within
from janbot.store import VectorStore

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "public_profile_org"
FIXTURE_FILE = FIXTURE_DIR / "example.org"

_STUB_DIM = 64


def _stub_embedder(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder; no model, stable across runs."""
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * _STUB_DIM
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % _STUB_DIM
            vector[index] += 1.0
        vectors.append(vector)
    return vectors


def test_read_org_file_chunks_every_subtree() -> None:
    chunks = read_org_file(FIXTURE_FILE)

    assert len(chunks) == 4
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    assert all(chunk.source_path == str(FIXTURE_FILE) for chunk in chunks)

    about = next(chunk for chunk in chunks if chunk.breadcrumb == "About")
    assert about.id == f"{FIXTURE_FILE}::0::About"
    assert "Background" in about.text
    assert "biography" in about.text

    background = next(chunk for chunk in chunks if chunk.breadcrumb == "About > Background")
    assert background.id == f"{FIXTURE_FILE}::1::About > Background"
    assert "search infrastructure" in background.text

    projects = next(chunk for chunk in chunks if chunk.breadcrumb == "Projects")
    assert ":work:" in projects.text
    assert "CUSTOM_ID" in projects.text
    assert "projects" in projects.text

    janbot = next(chunk for chunk in chunks if chunk.breadcrumb == "Projects > JanBot")
    assert "RAG assistant" in janbot.text


def test_duplicate_headings_get_unique_ids(tmp_path: Path) -> None:
    source = tmp_path / "dupes.org"
    source.write_text("* Same\nBody one.\n* Same\nBody two.\n")

    chunks = read_org_file(source)

    assert len(chunks) == 2
    assert {chunk.breadcrumb for chunk in chunks} == {"Same"}
    assert len({chunk.id for chunk in chunks}) == 2


def test_source_path_is_absolute(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "relative.org"
    source.write_text("* Heading\nBody.\n")
    monkeypatch.chdir(tmp_path)

    chunks = read_org_file("relative.org")

    assert chunks
    assert Path(chunks[0].source_path).is_absolute()
    assert chunks[0].source_path == str(source.resolve())


def test_index_one_file_and_retrieve(tmp_path: Path) -> None:
    index_path = tmp_path / "index"

    count = index_corpus(FIXTURE_DIR, index_path, _stub_embedder)
    assert count == 4

    store = VectorStore(index_path, _stub_embedder)
    results = store.query("About")

    assert results
    top = results[0]
    assert top["source_path"] == str(FIXTURE_FILE)
    assert top["breadcrumb"] == "About"


def test_empty_corpus_indexes_zero(tmp_path: Path) -> None:
    corpus = tmp_path / "empty"
    corpus.mkdir()
    index_path = tmp_path / "index"

    assert list(iter_org_files(corpus)) == []
    assert index_corpus(corpus, index_path, _stub_embedder) == 0


def test_non_org_files_ignored(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "notes.txt").write_text("not an org file")
    (corpus / "example.org").write_text(FIXTURE_FILE.read_text())
    index_path = tmp_path / "index"

    assert [path.name for path in iter_org_files(corpus)] == ["example.org"]
    assert index_corpus(corpus, index_path, _stub_embedder) == 4


def test_within_is_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    root.mkdir()

    assert within(root, root / "a.org") is True
    assert within(root, root) is True
    assert within(root, tmp_path / "elsewhere" / "b.org") is False
