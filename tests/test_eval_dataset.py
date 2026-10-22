"""Unit tests for the golden-dataset contract.

These prove the loader's I/O matrix rows: a missing file names the path, a
malformed item names its index, and the seed dataset parses to one item per
entry. No model, no network, no MLflow — the loader is pure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from janbot.eval.dataset import GoldenItem, load_golden_dataset, split_manifest
from janbot.ingest.scope import iter_org_files

SEED_DATASET = Path(__file__).resolve().parents[1] / "eval" / "golden_dataset.yaml"
CORPUS_ROOT = Path(__file__).resolve().parents[1] / "public_profile_org"


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
        if item.should_refuse:
            assert item.expected_sources == []
        else:
            assert item.expected_sources
            assert all(source.strip() for source in item.expected_sources)


def test_every_expected_source_resolves_to_an_indexed_org_file() -> None:
    items = load_golden_dataset(SEED_DATASET)
    indexed = {
        path.relative_to(CORPUS_ROOT.resolve()).as_posix()
        for path in iter_org_files(CORPUS_ROOT)
    }

    unresolved = sorted(
        {
            source
            for item in items
            for source in item.expected_sources
            if source not in indexed
        }
    )

    assert not unresolved, (
        "expected_sources must each name an indexed .org file under "
        f"public_profile_org/: unresolved {unresolved}"
    )


def test_missing_dataset_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.yaml"

    with pytest.raises(FileNotFoundError) as excinfo:
        load_golden_dataset(missing)

    assert str(missing) in str(excinfo.value)


def test_item_missing_question_names_its_index(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "ok?",
                "expected_answer": "a",
                "expected_sources": ["a.org"],
                "split": "train",
            },
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


def test_golden_dataset_is_a_51_train_69_val_stratified_split() -> None:
    everything = load_golden_dataset(SEED_DATASET)
    train = load_golden_dataset(SEED_DATASET, split="train")
    val = load_golden_dataset(SEED_DATASET, split="val")

    assert len(everything) == 120
    assert {item.split for item in everything} == {"train", "val"}
    assert len(train) == 51
    assert len(val) == 69
    assert train == [item for item in everything if item.split == "train"]
    assert val == [item for item in everything if item.split == "val"]


def test_split_manifest_maps_each_split_to_its_indices() -> None:
    manifest = split_manifest(load_golden_dataset(SEED_DATASET))

    val = [1, 4, 6, 9, 12, 14, 17, 19, 20, 22, 23, 25, 29, 32, 36, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 52, 53, 54, 55, 56, 57, 58, 59, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 82, 83, 84, 85, 86, 87, 88, 97, 98, 99, 102, 103, 106, 107, 108, 109, 112, 113, 114, 115, 117, 119]
    assert manifest["val"] == val
    assert manifest["train"] == [i for i in range(120) if i not in set(val)]


def test_split_filter_none_is_all_and_unknown_split_is_empty(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "q1",
                "expected_answer": "a",
                "expected_sources": ["a.org"],
                "split": "val",
            },
            {
                "question": "q2",
                "expected_answer": "a",
                "expected_sources": ["b.org"],
                "split": "train",
            },
        ],
    )

    assert len(load_golden_dataset(path)) == 2
    assert [item.question for item in load_golden_dataset(path, split="val")] == ["q1"]
    assert [item.question for item in load_golden_dataset(path, split="train")] == ["q2"]


def test_unknown_split_filter_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "q1",
                "expected_answer": "a",
                "expected_sources": ["a.org"],
                "split": "val",
            }
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path, split="validation")

    assert "validation" in str(excinfo.value)
    assert "split" in str(excinfo.value)


def test_item_fields_are_split_and_should_refuse_aware(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "q1",
                "expected_answer": "a",
                "expected_sources": ["a.org"],
                "split": "val",
                "should_refuse": True,
            },
            {
                "question": "q2",
                "expected_answer": "a",
                "expected_sources": ["b.org"],
                "split": "train",
            },
        ],
    )

    items = load_golden_dataset(path)

    assert items[0].split == "val"
    assert items[0].should_refuse is True
    assert items[1].split == "train"
    assert items[1].should_refuse is False


def test_missing_split_marker_names_its_index(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [{"question": "ok?", "expected_answer": "a", "expected_sources": ["a.org"]}],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "index 0" in str(excinfo.value)
    assert "split" in str(excinfo.value)


def test_unknown_split_marker_names_its_index(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "ok?",
                "expected_answer": "a",
                "expected_sources": ["a.org"],
                "split": "test",
            }
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "index 0" in str(excinfo.value)
    assert "split" in str(excinfo.value)


def test_non_boolean_should_refuse_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "ok?",
                "expected_answer": "a",
                "expected_sources": ["a.org"],
                "split": "train",
                "should_refuse": "yes",
            }
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "index 0" in str(excinfo.value)
    assert "should_refuse" in str(excinfo.value)


def test_should_refuse_item_loads_without_expected_sources(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "What is your salary expectation?",
                "split": "val",
                "should_refuse": True,
            }
        ],
    )

    items = load_golden_dataset(path)

    assert items[0].should_refuse is True
    assert items[0].expected_sources == []


def test_should_refuse_item_allows_an_empty_expected_sources_list(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "What is your notice period?",
                "expected_sources": [],
                "split": "val",
                "should_refuse": True,
            }
        ],
    )

    items = load_golden_dataset(path)

    assert items[0].should_refuse is True
    assert items[0].expected_sources == []


def test_non_refuse_item_without_sources_still_fails(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "What is your notice period?",
                "split": "val",
                "should_refuse": False,
            }
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        load_golden_dataset(path)

    assert "index 0" in str(excinfo.value)
    assert "expected_sources" in str(excinfo.value)


def test_should_refuse_defaults_to_false(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "dataset.yaml",
        [
            {
                "question": "ok?",
                "expected_answer": "a",
                "expected_sources": ["a.org"],
                "split": "train",
            }
        ],
    )

    assert load_golden_dataset(path)[0].should_refuse is False
