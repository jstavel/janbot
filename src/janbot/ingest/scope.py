"""Fail-closed, symlink-aware corpus scope for ingestion.

Containment is judged by a file's *located* path -- where the file sits -- not
by where a symlink target lives. A symlink in the final path component is
therefore not followed (placing a link inside the public folder is the
whitelist decision), while ``..`` segments are collapsed before the check. The
root itself is resolved once, so a symlinked root folder still works, and
symlinked directories are never descended.

The check is fail-closed: any path that cannot be normalized, or that escapes
the root, is refused. Refusals never raise.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

__all__ = ["iter_org_files", "located_path", "within"]


def located_path(path: str | Path) -> Path:
    """Return ``path`` made absolute with ``..`` collapsed, final link intact.

    The containing directory is resolved (following any symlinks along it) but
    the final component is deliberately left unresolved, so a symlinked file is
    judged by where it is *located* rather than by where its target lives.
    """
    absolute = Path(os.path.abspath(path))
    return absolute.parent.resolve() / absolute.name


def within(root: str | Path, path: str | Path) -> bool:
    """Return ``True`` only when ``path`` is *located* inside ``root``.

    The root is resolved once; the candidate keeps its final component. A path
    equal to the root itself (real or through a symlink, including a symlinked
    parent) is in scope. Fail-closed: a path containing a ``..`` component, or
    an unresolvable path (``resolve`` raises), returns ``False``.
    """
    if ".." in Path(path).parts:
        return False
    try:
        root_resolved = Path(root).resolve()
        located = located_path(path)
    except (OSError, RuntimeError):
        return False
    if located == root_resolved or located.is_relative_to(root_resolved):
        return True
    return Path(os.path.abspath(path)) == Path(os.path.abspath(root))


def iter_org_files(root: str | Path) -> Iterator[Path]:
    """Yield every ``.org`` file located under ``root`` in deterministic order.

    The root is resolved once (so a symlinked root works). A missing,
    non-directory or unresolvable root yields nothing (never raises). Symlinked
    files inside the root are yielded; symlinked directories are not descended.
    Non-``.org`` files are ignored.
    """
    try:
        root_resolved = Path(root).resolve()
    except (OSError, RuntimeError):
        return
    if not root_resolved.is_dir():
        return
    for path in sorted(root_resolved.rglob("*.org")):
        if path.is_file() and within(root_resolved, path):
            yield path
