"""Cache artifact tests: normalization, validation and provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from janbot.api.contract import ChatResponse, Citation
from janbot.guardrails.build_cache import validate_source
from janbot.guardrails.cache import (
    CacheError,
    build_document,
    corpus_sha256,
    load_cache,
    normalize_question,
    parse_cache,
)

QUESTION = "Why did you leave your last job after so many years there?"
ANSWERED = {
    "status": "answered",
    "answer": "Search infrastructure.",
    "citations": [{"source": "profile.org"}],
    "reason": None,
}
DECLINED = {
    "status": "insufficient",
    "answer": "I answer only from my public profile.",
    "citations": [],
    "reason": "out_of_corpus",
}


def _metadata(**overrides) -> dict:
    dataset = Path("eval/golden_dataset.yaml")
    metadata = {
        "run_id": "run-1",
        "date": "2026-10-20",
        "model_mode": "production",
        "requested_model": "openrouter/auto",
        "routed_models": ["openai/gpt-6-luna"],
        "dataset": "eval/golden_dataset.yaml",
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "corpus_commit": "abc123",
        "corpus_sha256": corpus_sha256(Path("public_profile_org")),
        "output_guard": "on",
        "split": "val",
    }
    metadata.update(overrides)
    return metadata


def _document(entries: list[dict] | None = None, metadata: dict | None = None) -> dict:
    return {
        "metadata": {"version": 1, **(metadata or _metadata())},
        "entries": entries
        if entries is not None
        else [{"question": QUESTION, "response": ANSWERED, "routed_model": "m"}],
    }


def test_normalization_collapses_case_and_whitespace() -> None:
    assert normalize_question(
        "  WHY did you leave   your last job after so many years there?  "
    ) == ("why did you leave your last job after so many years there?")


def test_lookup_hits_a_normalized_question() -> None:
    cache = parse_cache(_document())

    response = cache.lookup("  WHY did you leave   your last job after so many years there? ")

    assert response is not None
    assert response == ChatResponse.model_validate(ANSWERED)
    assert cache.lookup("a novel question") is None


def test_insufficient_entry_is_rejected() -> None:
    with pytest.raises(CacheError, match="refusal"):
        parse_cache(_document([{"question": QUESTION, "response": DECLINED}]))


def test_duplicate_normalized_question_is_rejected() -> None:
    entries = [
        {"question": QUESTION, "response": ANSWERED},
        {"question": f"  {QUESTION.upper()}  ", "response": ANSWERED},
    ]
    with pytest.raises(CacheError, match="duplicate"):
        parse_cache(_document(entries))


def test_missing_metadata_field_is_rejected() -> None:
    metadata = _metadata()
    del metadata["corpus_commit"]
    with pytest.raises(CacheError, match="corpus_commit"):
        parse_cache(_document(metadata=metadata))


def test_guard_off_artifact_is_rejected() -> None:
    with pytest.raises(CacheError, match="output guard off"):
        parse_cache(_document(metadata=_metadata(output_guard="off")))


def test_load_cache_round_trips_build_document(tmp_path: Path) -> None:
    baked = build_document(
        {"version": 1, **_metadata()},
        [{"question": QUESTION, "response": ANSWERED, "routed_model": "m"}],
    )
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(baked), encoding="utf-8")

    cache = load_cache(path)

    assert cache.lookup(QUESTION) is not None


def test_validate_source_accepts_the_frozen_dataset(tmp_path: Path) -> None:
    source = tmp_path / "answers-1.json"
    source.write_text(json.dumps(_document()), encoding="utf-8")

    document = validate_source(source)

    assert document["metadata"]["run_id"] == "run-1"


def test_validate_source_rejects_a_dataset_sha_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "answers-1.json"
    source.write_text(
        json.dumps(_document(metadata=_metadata(dataset_sha256="deadbeef"))),
        encoding="utf-8",
    )

    with pytest.raises(CacheError, match="sha256 mismatch"):
        validate_source(source)


def test_validate_source_rejects_a_non_production_run(tmp_path: Path) -> None:
    source = tmp_path / "answers-1.json"
    source.write_text(
        json.dumps(_document(metadata=_metadata(model_mode="eval"))),
        encoding="utf-8",
    )

    with pytest.raises(CacheError, match="production"):
        validate_source(source)


def test_validate_source_rejects_a_question_outside_the_val_set(tmp_path: Path) -> None:
    source = tmp_path / "answers-1.json"
    source.write_text(
        json.dumps(
            _document(
                [{"question": "Not in the dataset?", "response": ANSWERED}],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(CacheError, match="val non-refusal set"):
        validate_source(source)


def test_cache_response_must_be_contract_shaped() -> None:
    broken = {**ANSWERED, "citations": []}

    with pytest.raises(CacheError, match="valid ChatResponse"):
        parse_cache(_document([{"question": QUESTION, "response": broken}]))


def test_cached_response_citations_are_contract_citations() -> None:
    cache = parse_cache(_document())
    response = cache.lookup(QUESTION)

    assert response is not None
    assert response.citations == [Citation(source="profile.org")]
