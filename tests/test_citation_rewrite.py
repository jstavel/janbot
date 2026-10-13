"""Direct tests for the citation rewriter (``pipeline.chat.corpus_relative``).

Narrow, deliberate deviation from the port-only convention (AD-7): story 3.6's
store scope made the rewriter's out-of-root branch unreachable through the HTTP
port — the scoped store never returns an out-of-root chunk — so the rewriter is
covered directly here. Recorded in the epic-rag-chat retrospective and in
``plan-rewriter-coverage-alignment.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from janbot.pipeline.chat import UnattributableContext, corpus_relative


def test_in_root_source_is_rewritten_corpus_relative(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    root.mkdir()

    assert corpus_relative(root)(str(root / "profile.org")) == "profile.org"


def test_nested_in_root_source_is_rewritten(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    root.mkdir()

    assert corpus_relative(root)(str(root / "sub" / "a.org")) == "sub/a.org"


def test_symlinked_in_root_source_is_rewritten(tmp_path: Path) -> None:
    """Containment is judged by the *located* path, matching the store's scope."""
    real = tmp_path / "real" / "corpus"
    real.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "real", target_is_directory=True)
    root = link / "corpus"

    assert corpus_relative(root)(str(root / "profile.org")) == "profile.org"


def test_out_of_root_source_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    root.mkdir()

    with pytest.raises(UnattributableContext):
        corpus_relative(root)(str(tmp_path / "elsewhere" / "x.org"))


def test_relative_source_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    # A lax guard would resolve this relative to the CWD (now the root) and
    # accept it; the rewriter must refuse it outright.
    monkeypatch.chdir(root)

    with pytest.raises(UnattributableContext):
        corpus_relative(root)("profile.org")
