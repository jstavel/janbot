"""Unit tests for the golden-dataset contract.

These prove the loader's I/O matrix rows: a missing file names the path, a
malformed item names its index, and the seed dataset parses to one item per
entry. No model, no network, no MLflow — the loader is pure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from janbot.eval.dataset import GoldenItem, load_golden_dataset

SEED_DATASET = Path(__file__).resolve().parents[1] / "eval" / "golden_dataset.yaml"


def _write(path: Path, entries: object) -> Path:
    path.write_text(yaml.safe_dump(entries), encoding="utf-8")
    return path


def test_seed_dataset_returns_one_item_per_entry() -> None:
    raw = yaml.safe_load(SEED_DATASET.read_text(encoding="utf-8"))

    items = load_golden_dataset(SEED_DATASET)

    assert len(items) == len(raw)
    assert items
    for item in items:
        assert isinstance(item, GoldenItem)
        assert item.question.strip()
        assert item.expected_sources
        assert all(source.strip() for source in item.expected_sources)


def test_missing_dataset_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.yaml"

    with pytest.raises(FileNotFoundError) as excinfo:
        load_golden_dataset(missing)

    assert str(missing) in str(excinfo.value)


def test_item_missing_question_names_its_index(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {"question": "ok?", "expected_answer": "a", "expected_sources": ["a.org"]},
            {"expected_answer": "a", "expected_sources": ["b.org"]},
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "index 1" in str(excinfo.value)
    assert "question" in str(excinfo.value)


def test_item_missing_expected_sources_names_its_index(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [{"question": "ok?", "expected_answer": "a"}],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "index 0" in str(excinfo.value)
    assert "expected_sources" in str(excinfo.value)


def test_blank_question_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [{"question": "   ", "expected_answer": "a", "expected_sources": ["a.org"]}],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "index 0" in str(excinfo.value)


def test_blank_expected_source_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [{"question": "ok?", "expected_answer": "a", "expected_sources": ["  "]}],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "index 0" in str(excinfo.value)


def test_non_list_document_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path / "dataset.yaml", {"question": "not a list"})

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "list" in str(excinfo.value)


def test_empty_document_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dataset.yaml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert str(path) in str(excinfo.value)
