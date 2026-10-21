"""Tracer-bullet tests: index one public org file and retrieve it.

These tests never load the real embedding model; they inject the deterministic
stub embedder from ``conftest`` through the store's seam.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from janbot.ingest import Chunk, index_corpus, iter_org_files, read_org_file
from janbot.store import VectorStore

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "public_profile_org"
FIXTURE_FILE = FIXTURE_DIR / "example.org"


def test_read_org_file_chunks_every_subtree(
    chunk_id: Callable[..., str],
) -> None:
    chunks = read_org_file(FIXTURE_FILE, FIXTURE_DIR)

    assert len(chunks) == 4
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    assert all(chunk.source_path == str(FIXTURE_FILE) for chunk in chunks)

    about = next(chunk for chunk in chunks if chunk.breadcrumb == "About")
    assert about.id == chunk_id(FIXTURE_FILE, "About", FIXTURE_DIR)
    assert "Background" in about.text
    assert "biography" in about.text

    background = next(chunk for chunk in chunks if chunk.breadcrumb == "About > Background")
    assert background.id == chunk_id(FIXTURE_FILE, "About > Background", FIXTURE_DIR)
    assert "search infrastructure" in background.text

    projects = next(chunk for chunk in chunks if chunk.breadcrumb == "Projects")
    assert ":work:" in projects.text
    assert "CUSTOM_ID" in projects.text
    assert "projects" in projects.text

    janbot = next(chunk for chunk in chunks if chunk.breadcrumb == "Projects > JanBot")
    assert "RAG assistant" in janbot.text


def test_chunk_id_is_corpus_root_relative() -> None:
    chunks = read_org_file(FIXTURE_FILE, FIXTURE_DIR)

    assert all(chunk.id.startswith("example.org::") for chunk in chunks)
    assert all(str(FIXTURE_DIR) not in chunk.id for chunk in chunks)


def test_duplicate_headings_get_unique_ids(tmp_path: Path) -> None:
    source = tmp_path / "dupes.org"
    source.write_text("* Same\nBody one.\n* Same\nBody two.\n")

    chunks = read_org_file(source, tmp_path)

    assert len(chunks) == 2
    assert {chunk.breadcrumb for chunk in chunks} == {"Same"}
    assert len({chunk.id for chunk in chunks}) == 2


def test_source_path_is_absolute(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "relative.org"
    source.write_text("* Heading\nBody.\n")
    monkeypatch.chdir(tmp_path)

    chunks = read_org_file("relative.org", tmp_path)

    assert chunks
    assert Path(chunks[0].source_path).is_absolute()
    assert chunks[0].source_path == str(source.resolve())


def test_read_org_file_refuses_a_file_outside_the_corpus_root(tmp_path: Path) -> None:
    source = tmp_path / "elsewhere.org"
    source.write_text("* Heading\nBody.\n")

    with pytest.raises(ValueError):
        read_org_file(source, tmp_path / "corpus")


def test_index_one_file_and_retrieve(
    tmp_path: Path, embedder: Callable[[list[str]], list[list[float]]]
) -> None:
    index_path = tmp_path / "index"

    count = index_corpus(FIXTURE_DIR, index_path, embedder)
    assert count == 4

    store = VectorStore(index_path, embedder)
    results = store.query("About")

    assert results
    top = results[0]
    assert top["source_path"] == str(FIXTURE_FILE)
    assert top["breadcrumb"] == "About"


def test_empty_corpus_indexes_zero(
    tmp_path: Path, embedder: Callable[[list[str]], list[list[float]]]
) -> None:
    corpus = tmp_path / "empty"
    corpus.mkdir()
    index_path = tmp_path / "index"

    assert list(iter_org_files(corpus)) == []
    assert index_corpus(corpus, index_path, embedder) == 0


def test_non_org_files_ignored(
    tmp_path: Path, embedder: Callable[[list[str]], list[list[float]]]
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "notes.txt").write_text("not an org file")
    (corpus / "example.org").write_text(FIXTURE_FILE.read_text())
    index_path = tmp_path / "index"

    assert [path.name for path in iter_org_files(corpus)] == ["example.org"]
    assert index_corpus(corpus, index_path, embedder) == 4


def test_markdown_meta_document_contributes_zero_chunks(
    tmp_path: Path, embedder: Callable[[list[str]], list[list[float]]]
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "thesis-map.md").write_text(
        "# Thesis map\n\n## A thesis\n- Claim: a restatement of other files.\n"
    )
    (corpus / "example.org").write_text(FIXTURE_FILE.read_text())
    index_path = tmp_path / "index"

    assert [path.name for path in iter_org_files(corpus)] == ["example.org"]
    assert index_corpus(corpus, index_path, embedder) == 4

