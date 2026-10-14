"""Unit tests for the retrieval-accuracy and citation-correctness metrics.

They prove each story's matrix. Retrieval: an item whose expected sources were
all retrieved passes and counts in the aggregate; an item whose expected source
was missed fails and the miss is named per item; a declined item still resolves
against what was retrieved; and an item with no expected sources (or no observed
retrieval) is excluded from the aggregate. Citation: containment (expected
subset of cited) passes, a missed expected source fails and is named, a
retrieved-but-unexpected citation still passes and only lowers precision, and a
decline fails containment. No model, no network, no MLflow.
"""

from __future__ import annotations

from janbot.api.contract import INSUFFICIENT_ANSWER, ChatResponse, Citation
from janbot.eval.dataset import GoldenItem
from janbot.eval.judge import FAITHFUL, HALLUCINATED, Verdict
from janbot.eval.metrics import (
    ItemOutcome,
    citation_correctness,
    citation_misses,
    citation_precision,
    faithfulness,
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


def _citation_outcome(
    expected_sources: list[str],
    cited_sources: list[str],
    *,
    declined: bool = False,
    question: str = "q",
) -> ItemOutcome:
    if declined:
        response: ChatResponse | None = ChatResponse(
            status="insufficient", answer=INSUFFICIENT_ANSWER
        )
    else:
        response = ChatResponse(
            answer="a", citations=[Citation(source=s) for s in cited_sources]
        )
    return ItemOutcome(
        item=_item(expected_sources, question),
        response=response,
        error=None,
        retrieved_sources=None,
    )


def test_cited_expected_sources_pass_and_count() -> None:
    outcomes = [_citation_outcome(["a.org"], ["a.org", "b.org"])]

    assert citation_correctness(outcomes) == 1.0
    assert citation_misses(outcomes) == []


def test_missed_citation_fails_and_is_named_per_item() -> None:
    outcomes = [_citation_outcome(["a.org", "b.org"], ["a.org"], question="What?")]

    assert citation_correctness(outcomes) == 0.0
    misses = citation_misses(outcomes)
    assert len(misses) == 1
    assert misses[0].startswith("What? — ")
    assert "missing cited source(s): b.org" in misses[0]


def test_extra_retrieved_source_still_passes_and_only_lowers_precision() -> None:
    outcomes = [_citation_outcome(["a.org"], ["a.org", "b.org"])]

    assert citation_correctness(outcomes) == 1.0
    assert citation_misses(outcomes) == []
    assert citation_precision(outcomes) == 0.5


def test_declined_item_fails_containment() -> None:
    outcomes = [_citation_outcome(["a.org"], [], declined=True, question="Refuse?")]

    assert citation_correctness(outcomes) == 0.0
    misses = citation_misses(outcomes)
    assert len(misses) == 1
    assert "missing cited source(s): a.org" in misses[0]


def test_crashed_response_is_excluded_and_not_named() -> None:
    crashed = ItemOutcome(
        item=_item(["a.org"], question="Boom?"),
        response=None,
        error="ValueError: boom",
    )
    outcomes = [crashed, _citation_outcome(["a.org"], ["a.org"])]

    assert citation_correctness(outcomes) == 1.0
    assert citation_misses(outcomes) == []
    assert citation_precision(outcomes) == 1.0


def test_only_crashed_items_aggregate_to_zero() -> None:
    crashed = ItemOutcome(
        item=_item(["a.org"]), response=None, error="ValueError: boom"
    )

    assert citation_correctness([crashed]) == 0.0
    assert citation_precision([crashed]) == 0.0


def test_citation_metric_averages_pass_and_miss() -> None:
    outcomes = [
        _citation_outcome(["a.org"], ["a.org"]),
        _citation_outcome(["a.org", "b.org"], ["a.org"]),
    ]

    assert citation_correctness(outcomes) == 0.5
    assert citation_precision(outcomes) == 1.0


def test_citation_precision_is_the_mean_expected_share_of_cited() -> None:
    outcomes = [
        _citation_outcome(["a.org"], ["a.org", "b.org"]),
        _citation_outcome(["a.org"], ["a.org"]),
    ]

    assert citation_correctness(outcomes) == 1.0
    assert citation_precision(outcomes) == 0.75


def test_declined_item_contributes_zero_precision_over_the_same_population() -> None:
    outcomes = [
        _citation_outcome(["a.org"], ["a.org"]),
        _citation_outcome(["b.org"], [], declined=True),
    ]

    assert citation_correctness(outcomes) == 0.5
    assert citation_precision(outcomes) == 0.5


def test_citation_item_with_no_expected_sources_is_excluded() -> None:
    outcomes = [
        _citation_outcome([], ["a.org"], question="refuse"),
        _citation_outcome(["a.org"], ["a.org"], question="answer"),
    ]

    assert citation_correctness(outcomes) == 1.0
    assert citation_misses(outcomes) == []
    assert citation_precision(outcomes) == 1.0


def test_citation_metrics_empty_outcomes_are_zero() -> None:
    assert citation_correctness([]) == 0.0
    assert citation_precision([]) == 0.0


def test_citation_metrics_are_registered() -> None:
    metrics = registered_metrics()
    assert "citation_correctness" in metrics
    assert "citation_precision" in metrics


def _judged(label: str, question: str = "q") -> ItemOutcome:
    return ItemOutcome(
        item=_item(["a.org"], question),
        response=_answered(),
        error=None,
        judge_verdict=Verdict(label=label, rationale="because"),
    )


def test_faithful_verdict_passes_and_counts() -> None:
    assert faithfulness([_judged(FAITHFUL)]) == 1.0


def test_hallucinated_verdict_fails_and_is_recorded() -> None:
    outcomes = [_judged(HALLUCINATED)]

    assert faithfulness(outcomes) == 0.0
    assert outcomes[0].judge_verdict is not None
    assert outcomes[0].judge_verdict.label == HALLUCINATED


def test_faithfulness_averages_faithful_and_hallucinated() -> None:
    outcomes = [_judged(FAITHFUL), _judged(HALLUCINATED)]

    assert faithfulness(outcomes) == 0.5


def test_unjudged_items_are_excluded_from_the_aggregate() -> None:
    unjudged = ItemOutcome(item=_item(["a.org"]), response=_answered(), error=None)
    outcomes = [_judged(FAITHFUL), unjudged]

    assert faithfulness(outcomes) == 1.0


def test_no_judged_items_aggregate_to_zero() -> None:
    unjudged = ItemOutcome(item=_item(["a.org"]), response=_answered(), error=None)

    assert faithfulness([unjudged]) == 0.0
    assert faithfulness([]) == 0.0


def test_faithfulness_is_registered() -> None:
    assert "faithfulness" in registered_metrics()
