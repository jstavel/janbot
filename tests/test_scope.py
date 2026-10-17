"""Fail-closed, symlink-aware scope filter (CAP-4 / AD-3).

Containment is decided by where a file is *located*: a symlinked public file is
indexed, a file physically outside the root is refused, ``..`` escapes and
unresolvable paths are refused, symlinked directories are not descended, and a
symlinked root is resolved once.

These tests inject the deterministic stub embedder from ``conftest``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from janbot.ingest import index_corpus, iter_org_files, within
from janbot.store import VectorStore

Embedder = Callable[[list[str]], list[list[float]]]


def test_symlinked_public_file_is_in_scope_and_indexed(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "real.org"
    write_org(target, "Real")

    root = tmp_path / "root"
    root.mkdir()
    (root / "pub.org").symlink_to(target)

    assert within(root, root / "pub.org") is True
    assert [path.name for path in iter_org_files(root)] == ["pub.org"]

    index_path = tmp_path / "index"
    assert index_corpus(root, index_path, embedder) == 1

    rows = VectorStore(index_path, embedder).query("Real")
    assert rows
    stored = Path(rows[0]["source_path"])
    assert stored == root / "pub.org"
    assert stored.is_relative_to(root)


def test_outside_file_is_refused(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    write_org(root / "public.org", "Public")

    index_path = tmp_path / "index"
    assert index_corpus(root, index_path, embedder) == 1

    private = tmp_path / "elsewhere" / "priv.org"
    private.parent.mkdir()
    write_org(private, "Private")

    assert within(root, private) is False
    assert [path.name for path in iter_org_files(root)] == ["public.org"]
    assert index_corpus(root, index_path, embedder) == 1

    rows = VectorStore(index_path, embedder).query("Private")
    assert rows
    assert all(row["source_path"] == str(root / "public.org") for row in rows)


def test_directory_escape_is_refused(
    tmp_path: Path, write_org: Callable[..., None]
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    write_org(tmp_path / "priv.org", "Private")

    assert within(root, root / ".." / "priv.org") is False


def test_escape_through_symlinked_directory_is_refused(
    tmp_path: Path, write_org: Callable[..., None]
) -> None:
    outside = tmp_path / "outside"
    (outside / "sub").mkdir(parents=True)
    write_org(outside / "secret.org", "Secret")

    root = tmp_path / "root"
    root.mkdir()
    (root / "mid").symlink_to(outside / "sub", target_is_directory=True)

    assert within(root, root / "mid" / ".." / "secret.org") is False


def test_symlinked_directory_is_not_descended(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    write_org(outside / "secret.org", "Secret")

    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)

    assert list(iter_org_files(root)) == []
    assert index_corpus(root, tmp_path / "index", embedder) == 0


def test_symlinked_root_is_resolved_once(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    write_org(real / "a.org", "A")

    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    assert [path.name for path in iter_org_files(link)] == ["a.org"]
    assert within(link, link / "a.org") is True
    assert index_corpus(link, tmp_path / "index", embedder) == 1


def test_symlinked_root_with_symlinked_parent_is_in_scope(
    tmp_path: Path, write_org: Callable[..., None]
) -> None:
    real_parent = tmp_path / "real_parent"
    real_parent.mkdir()
    parent_link = tmp_path / "parent_link"
    parent_link.symlink_to(real_parent, target_is_directory=True)

    target = tmp_path / "target"
    target.mkdir()
    write_org(target / "a.org", "A")

    root = parent_link / "root"
    root.symlink_to(target, target_is_directory=True)

    assert within(root, root) is True
    assert within(root, root / "a.org") is True


def test_unresolvable_path_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    loop = tmp_path / "loop"
    loop.symlink_to(loop)

    assert within(root, loop / "x.org") is False
    assert list(iter_org_files(loop)) == []


def test_index_corpus_refuses_out_of_scope_path_handed_directly(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Done-when 3 (isolated): ``index_corpus``' own guard refuses an out-of-scope path.

    ``iter_org_files`` is patched to bypass its filter, so the only thing that can
    keep the outside file out of the index is ``index_corpus``' ``within`` guard.
    Removing that guard alone makes this test fail (the file would be indexed).
    """
    root = tmp_path / "root"
    root.mkdir()
    write_org(root / "public.org", "Public")
    outside = tmp_path / "elsewhere" / "secret.org"
    write_org(outside, "Secret")

    monkeypatch.setattr("janbot.ingest.iter_org_files", lambda _root: iter([outside]))

    index_path = tmp_path / "index"
    assert index_corpus(root, index_path, embedder) == 0
    assert VectorStore(index_path, embedder).ids() == set()


def test_iter_org_files_refuses_out_of_scope_path_from_its_own_filter(
    tmp_path: Path,
    write_org: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Done-when 3 (isolated): ``iter_org_files``' own ``within`` filter drops an out-of-scope path.

    ``rglob`` is patched to yield both an in-root and an out-of-root file, so the
    only thing that can drop the outside file is ``iter_org_files``' ``within``
    check. Removing that filter alone makes this test fail.
    """
    root = tmp_path / "root"
    root.mkdir()
    inside = root / "in.org"
    write_org(inside, "In")
    outside = tmp_path / "outside" / "out.org"
    write_org(outside, "Out")

    monkeypatch.setattr(Path, "rglob", lambda self, pattern: iter([inside, outside]))

    assert [path.name for path in iter_org_files(root)] == ["in.org"]


def test_private_note_changes_no_ranked_retrieval(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Done-when 3: offering a private note to the indexer leaves the *ranked* retrieval identical.

    The private file sits outside the root; it is offered to ``index_corpus`` by
    patching ``iter_org_files`` so the scope guard is the only thing keeping it
    out. A regression that let it in would add a matching chunk and change the
    ranking, so the before/after lists would differ.
    """
    corpus = tmp_path / "public_profile_org"
    corpus.mkdir()
    public = corpus / "public.org"
    write_org(public, "Shared topic", body="Public shared content.")

    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)
    before = VectorStore(index_path, embedder).query("shared", k=5)
    assert before
    assert all(Path(row["source_path"]).is_relative_to(corpus) for row in before)

    private = tmp_path / "elsewhere" / "priv.org"
    write_org(private, "Shared topic", body="Private shared content.")
    monkeypatch.setattr("janbot.ingest.iter_org_files", lambda _root: iter([public, private]))

    index_corpus(corpus, index_path, embedder)
    after = VectorStore(index_path, embedder).query("shared", k=5)

    assert after == before
    assert all("Private shared content." not in (row["text"] or "") for row in after)


def test_thesis_map_is_a_markdown_meta_document_not_an_org_object() -> None:
    """The extract is a manual step, so pin the artifact, not only the mechanism."""
    corpus = Path(__file__).resolve().parents[1] / "public_profile_org"

    assert (corpus / "thesis-map.md").is_file()
    assert not (corpus / "thesis-map.org").exists()


