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
