"""Golden-dataset contract for the eval harness.

The golden dataset is the fixed recruiter Q&A set the evaluation runs against
(CAP-8, Milestone 2). It is a YAML list of items, each carrying a ``question``,
an ``expected_answer`` and the corpus-relative ``expected_sources`` a correct
response should cite. ``load_golden_dataset`` is the only reader: it validates
every item and fails closed, so a broken dataset never yields a silently short
run — a missing file names the path and a malformed item names its index.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class GoldenItem:
    """One golden question with its expected answer and expected sources."""

    question: str
    expected_answer: str
    expected_sources: list[str]


def _parse_sources(item: dict[str, Any], index: int) -> list[str]:
    """Return the item's non-empty ``expected_sources`` list, or fail naming the index."""
    sources = item.get("expected_sources")
    if not isinstance(sources, list) or not sources:
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


def _parse_item(entry: Any, index: int) -> GoldenItem:
    """Validate one raw YAML entry into a :class:`GoldenItem`, failing naming the index."""
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

    return GoldenItem(
        question=question.strip(),
        expected_answer=expected_answer,
        expected_sources=_parse_sources(entry, index),
    )


def load_golden_dataset(path: str | Path) -> list[GoldenItem]:
    """Load and validate the golden dataset at ``path``.

    Raises:
        FileNotFoundError: if ``path`` does not exist, naming the path.
        ValueError: if the document is empty or not a YAML list, or an item is
            not a mapping or lacks a non-empty ``question``/``expected_sources``,
            naming the offending path or item index.
    """
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
    return [_parse_item(entry, index) for index, entry in enumerate(document)]
