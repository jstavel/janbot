"""Fail-closed corpus scope for ingestion (minimal tracer version).

Only files physically under the configured corpus root are ever yielded. The
check is fail-closed: anything that cannot be proven to be within the root --
a different tree, a path that cannot be resolved -- is refused. The full scope
policy (symlink handling, whitelist semantics) lands in a later story.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

__all__ = ["iter_org_files", "within"]


def within(root: str | Path, path: str | Path) -> bool:
    """Return ``True`` only when ``path`` resolves inside ``root``.

    Fail-closed: unresolvable paths return ``False``.
    """
    try:
        root_resolved = Path(root).resolve()
        path_resolved = Path(path).resolve()
    except (OSError, RuntimeError):
        return False
    return path_resolved == root_resolved or path_resolved.is_relative_to(
        root_resolved
    )


def iter_org_files(root: str | Path) -> Iterator[Path]:
    """Yield every ``.org`` file under ``root`` in deterministic order.

    A missing or non-directory root yields nothing (never raises), so an empty
    corpus is a no-op. Non-``.org`` files are ignored.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return
    for path in sorted(root_path.rglob("*.org")):
        if path.is_file() and within(root_path, path):
            yield path
