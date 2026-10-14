"""Unit tests for the retrieval-accuracy metric and its per-item misses.

They prove the story's matrix: an item whose expected sources were all retrieved
passes and counts in the aggregate; an item whose expected source was missed
fails and the miss is named per item; a declined item still resolves against what
was retrieved; and an item with no expected sources (or no observed retrieval) is
excluded from the aggregate. No model, no network, no MLflow.
"""

from __future__ import annotations

from janbot.api.contract import ChatResponse, Citation
from janbot.eval.dataset import GoldenItem
from janbot.eval.metrics import (
    ItemOutcome,
    registered_metrics,
    retrieval_accuracy,
    retrieval_misses,
)


def _item(expected_sources: list[str], question: str = "q") -> GoldenItem:
    return GoldenItem(
        question=question, expected_answer="a", expected_sources=expected_sources
    )


def _answered() -> ChatResponse:
    return ChatResponse(answer="a", citations=[Citation(source="p.org")])


def _outcome(
    expected_sources: list[str],
    retrieved_sources: list[str] | None,
    *,
    declined: bool = False,
    question: str = "q",
) -> ItemOutcome:
    response = None if declined else _answered()
    error = "UncitedAnswer: no sources" if declined else None
    return ItemOutcome(
        item=_item(expected_sources, question),
        response=response,
        error=error,
        retrieved_sources=retrieved_sources,
    )


def test_expected_source_retrieved_passes_and_counts() -> None:
    outcomes = [_outcome(["a.org"], ["a.org", "b.org"])]

    assert retrieval_accuracy(outcomes) == 1.0
    assert retrieval_misses(outcomes) == []


def test_missed_source_fails_and_is_named_per_item() -> None:
    outcomes = [_outcome(["a.org", "b.org"], ["a.org"], question="What?")]

    assert retrieval_accuracy(outcomes) == 0.0
    misses = retrieval_misses(outcomes)
    assert len(misses) == 1
    assert misses[0].startswith("What? — ")
    assert "missing retrieved source(s): b.org" in misses[0]


def test_declined_item_still_reflects_what_was_retrieved() -> None:
    outcomes = [_outcome(["a.org"], ["a.org", "b.org"], declined=True)]

    assert retrieval_accuracy(outcomes) == 1.0
    assert retrieval_misses(outcomes) == []


def test_item_with_no_expected_sources_is_excluded() -> None:
    outcomes = [
        _outcome([], ["a.org"], question="refuse"),
        _outcome(["a.org"], ["a.org"], question="answer"),
    ]

    assert retrieval_accuracy(outcomes) == 1.0
    assert retrieval_misses(outcomes) == []


def test_only_no_expected_items_aggregate_to_zero() -> None:
    outcomes = [_outcome([], ["a.org"])]

    assert retrieval_accuracy(outcomes) == 0.0


def test_unobserved_retrieval_is_excluded() -> None:
    outcomes = [_outcome(["a.org"], None)]

    assert retrieval_accuracy(outcomes) == 0.0
    assert retrieval_misses(outcomes) == []


def test_metric_averages_pass_and_miss() -> None:
    outcomes = [
        _outcome(["a.org"], ["a.org"]),
        _outcome(["b.org"], ["a.org"]),
    ]

    assert retrieval_accuracy(outcomes) == 0.5


def test_empty_outcomes_is_zero() -> None:
    assert retrieval_accuracy([]) == 0.0


def test_retrieval_accuracy_is_registered() -> None:
    assert "retrieval_accuracy" in registered_metrics()
