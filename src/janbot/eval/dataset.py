"""Golden-dataset contract for the eval harness.

The golden dataset is the fixed recruiter Q&A set the evaluation runs against
(CAP-8, Milestone 2). It is a YAML list of items, each carrying a ``question``,
an ``expected_answer``, the corpus-relative ``expected_sources`` a correct
response should cite, and a ``split`` marker (``train`` or ``val``) so compile
and evaluation can run over disjoint items. ``load_golden_dataset`` is the only
reader: it validates every item and fails closed, so a broken dataset never
yields a silently short run — a missing file names the path and a malformed item
names its index.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

VALID_SPLITS = frozenset({"train", "val"})


@dataclass(frozen=True)
class GoldenItem:
    """One golden question with its expected answer, sources and dataset split.

    ``split`` and ``should_refuse`` are defaulted so the many direct
    ``GoldenItem(...)`` constructions stay unchanged; the loader is fail-closed
    over the raw ``split`` marker.
    """

    question: str
    expected_answer: str
    expected_sources: list[str]
    split: str = "train"
    should_refuse: bool = False


def _parse_sources(
    item: dict[str, Any], index: int, *, should_refuse: bool
) -> list[str]:
    """Return the item's ``expected_sources`` list, or fail naming the index.

    A refusal item makes no retrieval claim, so it may omit ``expected_sources``
    entirely or carry an empty list; a non-refuse item keeps the non-empty
    requirement unchanged.
    """
    sources = item.get("expected_sources")
    if sources is None:
        if should_refuse:
            return []
        raise ValueError(
            f"golden dataset item at index {index} is missing a non-empty "
            "'expected_sources' list"
        )
    if not isinstance(sources, list):
        raise ValueError(
            f"golden dataset item at index {index} is missing a non-empty "
            "'expected_sources' list"
        )
    if not sources:
        if should_refuse:
            return []
        raise ValueError(
            f"golden dataset item at index {index} is missing a non-empty "
            "'expected_sources' list"
        )
    cleaned: list[str] = []
    for source in sources:
        if not isinstance(source, str) or not source.strip():
            raise ValueError(
                f"golden dataset item at index {index} has a blank or non-string "
                "entry in 'expected_sources'"
            )
        cleaned.append(source.strip())
    return cleaned


def _parse_split(entry: dict[str, Any], index: int) -> str:
    """Return the item's ``split`` marker, or fail naming the index (missing/unknown)."""
    split = entry.get("split")
    if not isinstance(split, str) or split not in VALID_SPLITS:
        raise ValueError(
            f"golden dataset item at index {index} is missing a valid 'split' "
            f"marker {split!r}; expected one of {sorted(VALID_SPLITS)}"
        )
    return split


def _parse_should_refuse(entry: dict[str, Any], index: int) -> bool:
    """Return the item's ``should_refuse`` flag (default ``False``), or fail naming the index."""
    value = entry.get("should_refuse", False)
    if not isinstance(value, bool):
        raise ValueError(
            f"golden dataset item at index {index} has a non-boolean "
            f"'should_refuse' {value!r}"
        )
    return value


def _parse_item(entry: Any, index: int) -> GoldenItem:
    """Validate one raw YAML entry into a :class:`GoldenItem`, failing naming the index.

    ``should_refuse`` is parsed before ``expected_sources`` because it selects the
    source rule: a refusal item may omit ``expected_sources``. The ``split``
    marker is checked last — after ``question`` and ``expected_sources`` — so a
    malformed item keeps naming its structural error rather than a missing split,
    while a missing or unknown split still fails closed.
    """
    if not isinstance(entry, dict):
        raise ValueError(
            f"golden dataset item at index {index} is not a mapping: {entry!r}"
        )

    question = entry.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError(
            f"golden dataset item at index {index} is missing a non-empty 'question'"
        )

    expected_answer = entry.get("expected_answer", "")
    if not isinstance(expected_answer, str):
        raise ValueError(
            f"golden dataset item at index {index} has a non-string 'expected_answer'"
        )

    should_refuse = _parse_should_refuse(entry, index)
    sources = _parse_sources(entry, index, should_refuse=should_refuse)

    return GoldenItem(
        question=question.strip(),
        expected_answer=expected_answer,
        expected_sources=sources,
        split=_parse_split(entry, index),
        should_refuse=should_refuse,
    )


def load_golden_dataset(
    path: str | Path, split: str | None = None
) -> list[GoldenItem]:
    """Load and validate the golden dataset at ``path``, optionally one ``split``.

    ``split=None`` returns every item (backward compatible); ``split="train"`` or
    ``split="val"`` returns only that split's items, in dataset order.

    Raises:
        FileNotFoundError: if ``path`` does not exist, naming the path.
        ValueError: if ``split`` is not ``None`` and not a valid split, or the
            document is empty / not a YAML list / an item is malformed, naming
            the offending split, path or item index.
    """
    if split is not None and (not isinstance(split, str) or split not in VALID_SPLITS):
        raise ValueError(
            f"unknown golden dataset split {split!r}; expected None or one of "
            f"{sorted(VALID_SPLITS)}"
        )
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"golden dataset not found: {dataset_path}")

    document = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    if document is None:
        raise ValueError(
            f"golden dataset {dataset_path} is empty; expected a YAML list of items"
        )
    if not isinstance(document, list):
        raise ValueError(
            f"golden dataset {dataset_path} must be a YAML list of items, "
            f"got {type(document).__name__}"
        )
    items = [_parse_item(entry, index) for index, entry in enumerate(document)]
    if split is None:
        return items
    return [item for item in items if item.split == split]


def split_manifest(items: Iterable[GoldenItem]) -> dict[str, list[int]]:
    """Map each split present in ``items`` to its item indices, in ``items`` order.

    Indices are positions in the passed iterable, so a filtered ``items`` yields
    compacted 0-based positions within that iterable; a caller that needs
    positions in the full dataset must pass the full dataset. The manifest records
    which positions belong to which split, so a run's held-out set is auditable
    from the run alone (beside the dataset artifact).
    """
    manifest: dict[str, list[int]] = {}
    for index, item in enumerate(items):
        manifest.setdefault(item.split, []).append(index)
    return manifest
