"""End-to-end ingestion suite: the epic's Done-when in one hermetic run.

Builds a representative org corpus in a temp dir, indexes it with the
deterministic stub embedder, and proves end to end that subtree chunks
(breadcrumbs, PROPERTIES, tags, child content) land in a populated, queryable
index; that a private file outside the root is refused and changes nothing; and
that a re-run is idempotent. It fails if the chunker or the scope filter
regresses.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from janbot.ingest import index_corpus, iter_org_files, read_org_file, within
from janbot.ingest.scope import located_path
from janbot.store import VectorStore

Embedder = Callable[[list[str]], list[list[float]]]

PROFILE = """\
* About :public:
:PROPERTIES:
:ROLE: engineer
:END:
:LOGBOOK:
- Note taken on [2026-01-01]
:END:
Biography body.
** Background
Search infrastructure work.
* Projects
Selected public projects.
** JanBot
A RAG assistant grounded in an org corpus.
"""


def _corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "public_profile_org"
    corpus.mkdir()
    (corpus / "profile.org").write_text(PROFILE)
    return corpus


def test_e2e_index_and_query(tmp_path: Path, embedder: Embedder) -> None:
    corpus = _corpus(tmp_path)
    source = str(located_path(corpus / "profile.org"))
    index_path = tmp_path / "index"

    count = index_corpus(corpus, index_path, embedder)
    assert count == 4

    chunks = {chunk.breadcrumb: chunk for chunk in read_org_file(corpus / "profile.org")}
    assert "About > Background" in chunks
    assert "engineer" in chunks["About"].text
    assert ":public:" in chunks["About"].text
    assert "Note taken on [2026-01-01]" in chunks["About"].text
    assert "Search infrastructure work." in chunks["About"].text
    assert "Search infrastructure work." in chunks["About > Background"].text
    assert all(chunk.source_path == source for chunk in chunks.values())

    rows = VectorStore(index_path, embedder).query("Background")
    assert rows
    assert rows[0]["source_path"] == source
    assert "Search infrastructure work." in rows[0]["text"]


def test_e2e_outside_private_file_is_refused_and_changes_nothing(
    tmp_path: Path, embedder: Embedder
) -> None:
    corpus = _corpus(tmp_path)
    index_path = tmp_path / "index"
    assert index_corpus(corpus, index_path, embedder) == 4
    before = VectorStore(index_path, embedder).ids()

    private = tmp_path / "elsewhere" / "priv.org"
    private.parent.mkdir()
    private.write_text("* Secret\nPrivate note.\n")

    assert within(corpus, private) is False
    assert [p.name for p in iter_org_files(corpus)] == ["profile.org"]

    assert index_corpus(corpus, index_path, embedder) == 4
    assert VectorStore(index_path, embedder).ids() == before

    rows = VectorStore(index_path, embedder).query("Secret")
    assert rows
    assert all(Path(row["source_path"]).is_relative_to(corpus) for row in rows)
    assert all("Private note." not in (row["text"] or "") for row in rows)
    assert all("Secret" not in (row["text"] or "") for row in rows)


def test_e2e_rerun_is_idempotent(tmp_path: Path, embedder: Embedder) -> None:
    corpus = _corpus(tmp_path)
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, embedder) == 4
    first = VectorStore(index_path, embedder).ids()

    assert index_corpus(corpus, index_path, embedder) == 4
    second = VectorStore(index_path, embedder).ids()

    assert first == second
    assert len(first) == 4
