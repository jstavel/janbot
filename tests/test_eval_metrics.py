"""Unit tests for the retrieval-accuracy, retrieval-MRR and citation-correctness metrics.

They prove each story's matrix. Retrieval: an item whose expected sources were
all retrieved passes and counts in the aggregate; an item whose expected source
was missed fails and the miss is named per item; a declined item still resolves
against what was retrieved; and an item with no expected sources (or no observed
retrieval) is excluded from the aggregate. MRR is the mean reciprocal rank of the
first expected source in the retrieved list over the same eligible items: rank 1
scores 1.0, rank 4 scores 0.25, an unretrieved expected source scores 0.0, and
items without a retrieval claim are excluded. Citation: containment (expected
subset of cited) passes, a missed expected source fails and is named, a
retrieved-but-unexpected citation still passes and only lowers precision, and the
claim-quality population is fixed — an in-corpus decline or hard error stays in it
and fails. Faithfulness is likewise failure-inclusive over every in-corpus item;
a missing verdict fails. Refusal metrics use one denominator each: every
should-refuse item for a pass, every in-corpus item for a spurious refusal (an
error is not a decline). No model, no network, no MLflow.
"""

from __future__ import annotations

import pytest

from janbot.api.contract import INSUFFICIENT_ANSWER, ChatResponse, Citation
from janbot.eval.dataset import GoldenItem
from janbot.eval.judge import FAITHFUL, HALLUCINATED, Verdict
from janbot.eval.metrics import (
    ItemOutcome,
    citation_correctness,
    citation_misses,
    citation_precision,
    faithfulness,
    metric_counts,
    metric_spec,
    reason_counts,
    refusal_pass_rate,
    register_metric,
    registered_metrics,
    retrieval_accuracy,
    retrieval_mrr,
    retrieval_misses,
    spurious_refusal_rate,
    stub_metric,
)


def _item(
    expected_sources: list[str], question: str = "q", *, should_refuse: bool = False
) -> GoldenItem:
    return GoldenItem(
        question=question,
        expected_answer="a",
        expected_sources=expected_sources,
        should_refuse=should_refuse,
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


def test_a_hard_error_before_retrieval_is_out_of_scope_for_retrieval() -> None:
    errored = ItemOutcome(
        item=_item(["a.org"]),
        response=None,
        error="ValueError: boom before retrieval",
        retrieved_sources=None,
    )

    assert retrieval_accuracy([errored]) == 0.0
    assert retrieval_mrr([errored]) == 0.0
    assert retrieval_misses([errored]) == []
    assert metric_counts([errored])["retrieval_accuracy__n"] == 0
    assert metric_counts([errored])["retrieval_mrr__n"] == 0
    # The claim-quality metrics keep the fixed population and fail the item.
    assert metric_counts([errored])["citation_correctness__n"] == 1
    assert metric_counts([errored])["faithfulness__n"] == 1


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
    question: str = "q",
) -> ItemOutcome:
    response = ChatResponse(
        answer="a", citations=[Citation(source=s) for s in cited_sources]
    )
    return ItemOutcome(
        item=_item(expected_sources, question),
        response=response,
        error=None,
        retrieved_sources=None,
    )


def _declined(expected_sources: list[str], question: str = "Refuse?") -> ItemOutcome:
    """A hand-built declined response: ``status="insufficient"`` with no citations."""
    return ItemOutcome(
        item=_item(expected_sources, question),
        response=ChatResponse(
            status="insufficient", answer=INSUFFICIENT_ANSWER, citations=[]
        ),
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


def test_declined_response_is_a_citation_failure_in_the_population() -> None:
    outcomes = [_declined(["a.org"], question="Refuse?")]

    assert citation_correctness(outcomes) == 0.0
    assert citation_precision(outcomes) == 0.0
    assert citation_misses(outcomes) == []
    assert metric_counts(outcomes)["citation_correctness__n"] == 1
    assert metric_counts(outcomes)["citation_precision__n"] == 1


def test_crashed_response_is_a_citation_failure_in_the_population() -> None:
    crashed = ItemOutcome(
        item=_item(["a.org"], question="Boom?"),
        response=None,
        error="ValueError: boom",
    )
    outcomes = [crashed, _citation_outcome(["a.org"], ["a.org"])]

    assert citation_correctness(outcomes) == 0.5
    assert citation_misses(outcomes) == []
    assert citation_precision(outcomes) == 0.5
    assert metric_counts(outcomes)["citation_correctness__n"] == 2


def test_only_crashed_items_aggregate_to_zero_over_the_population() -> None:
    crashed = ItemOutcome(
        item=_item(["a.org"]), response=None, error="ValueError: boom"
    )

    assert citation_correctness([crashed]) == 0.0
    assert citation_precision([crashed]) == 0.0
    assert metric_counts([crashed])["citation_correctness__n"] == 1


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


def test_declined_response_stays_in_the_citation_population_and_fails() -> None:
    outcomes = [
        _citation_outcome(["a.org"], ["a.org"]),
        _declined(["b.org"]),
    ]

    assert citation_correctness(outcomes) == 0.5
    assert citation_precision(outcomes) == 0.5
    assert citation_misses(outcomes) == []
    assert metric_counts(outcomes)["citation_correctness__n"] == 2
    assert metric_counts(outcomes)["citation_precision__n"] == 2


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


def test_unjudged_items_fail_within_the_population() -> None:
    unjudged = ItemOutcome(item=_item(["a.org"]), response=_answered(), error=None)
    outcomes = [_judged(FAITHFUL), unjudged]

    assert faithfulness(outcomes) == 0.5
    assert metric_counts(outcomes)["faithfulness__n"] == 2


def test_no_judged_items_aggregate_to_zero_over_the_nominal_population() -> None:
    unjudged = ItemOutcome(item=_item(["a.org"]), response=_answered(), error=None)

    assert faithfulness([unjudged]) == 0.0
    assert faithfulness([]) == 0.0
    assert metric_counts([unjudged])["faithfulness__n"] == 1


def test_declined_response_fails_within_the_faithfulness_population() -> None:
    outcomes = [_judged(FAITHFUL), _declined(["a.org"])]

    assert faithfulness(outcomes) == 0.5
    assert metric_counts(outcomes)["faithfulness__n"] == 2


def test_a_non_answered_item_cannot_pass_through_a_stray_faithful_verdict() -> None:
    declined = _declined(["a.org"])
    judged = ItemOutcome(
        item=declined.item,
        response=declined.response,
        error=None,
        judge_verdict=Verdict(label=FAITHFUL, rationale="because"),
    )

    assert faithfulness([judged]) == 0.0
    assert metric_counts([judged])["faithfulness__n"] == 1


def test_faithfulness_is_registered() -> None:
    assert "faithfulness" in registered_metrics()


def test_register_metric_requires_a_denominator() -> None:
    with pytest.raises(TypeError):
        register_metric("a_metric_without_a_denominator", lambda outcomes: 0.0)  # type: ignore[call-arg]

    assert "a_metric_without_a_denominator" not in registered_metrics()


def test_every_registered_metric_declares_a_count_and_a_direction() -> None:
    names = registered_metrics()

    assert set(metric_counts([])) == {f"{name}__n" for name in names}
    for name in names:
        assert isinstance(metric_spec(name).higher_is_better, bool)
    assert metric_spec("faithfulness").higher_is_better is True


def test_retrieval_mrr_scores_rank_one() -> None:
    assert retrieval_mrr([_outcome(["a.org"], ["a.org", "b.org"])]) == 1.0


def test_retrieval_mrr_scores_rank_four() -> None:
    outcomes = [_outcome(["d.org"], ["a.org", "b.org", "c.org", "d.org"])]

    assert retrieval_mrr(outcomes) == 0.25


def test_retrieval_mrr_is_zero_when_the_expected_source_is_not_retrieved() -> None:
    assert retrieval_mrr([_outcome(["z.org"], ["a.org", "b.org"])]) == 0.0


def test_retrieval_mrr_excludes_items_without_a_retrieval_claim() -> None:
    no_expected = _outcome([], ["a.org"])
    unobserved = _outcome(["a.org"], None)

    assert retrieval_mrr([_outcome(["a.org"], ["a.org"]), no_expected]) == 1.0
    assert retrieval_mrr([unobserved]) == 0.0


def test_retrieval_mrr_averages_over_eligible_items() -> None:
    outcomes = [_outcome(["a.org"], ["a.org"]), _outcome(["a.org"], ["x.org", "a.org"])]

    assert retrieval_mrr(outcomes) == 0.75


def _refusal_outcome(*, declined: bool, question: str = "Refuse?") -> ItemOutcome:
    """A should-refuse item's outcome: a clean decline, or an answered out-of-corpus question."""
    response = (
        ChatResponse(status="insufficient", answer=INSUFFICIENT_ANSWER, citations=[])
        if declined
        else _answered()
    )
    return ItemOutcome(
        item=_item([], question, should_refuse=True),
        response=response,
        error=None,
        retrieved_sources=None,
    )


def test_refusal_pass_rate_counts_a_clean_decline_as_a_pass() -> None:
    outcomes = [_refusal_outcome(declined=True)]

    assert refusal_pass_rate(outcomes) == 1.0
    assert metric_counts(outcomes)["refusal_pass_rate__n"] == 1


def test_refusal_pass_rate_fails_an_answered_out_of_corpus_question() -> None:
    outcomes = [_refusal_outcome(declined=False)]

    assert refusal_pass_rate(outcomes) == 0.0
    assert metric_counts(outcomes)["refusal_pass_rate__n"] == 1


def test_refusal_pass_rate_averages_declined_and_answered() -> None:
    outcomes = [_refusal_outcome(declined=True), _refusal_outcome(declined=False)]

    assert refusal_pass_rate(outcomes) == 0.5


def test_refusal_pass_rate_counts_an_errored_should_refuse_item_as_a_failure() -> None:
    errored = ItemOutcome(
        item=_item([], "boom?", should_refuse=True),
        response=None,
        error="ValueError: boom",
    )

    assert refusal_pass_rate([errored]) == 0.0
    assert metric_counts([errored])["refusal_pass_rate__n"] == 1


def test_refusal_pass_rate_is_zero_with_no_should_refuse_items() -> None:
    assert refusal_pass_rate([_citation_outcome(["a.org"], ["a.org"])]) == 0.0
    assert refusal_pass_rate([]) == 0.0


def test_spurious_refusal_rate_counts_a_declined_in_corpus_item() -> None:
    outcomes = [_declined(["a.org"], question="Should answer")]

    assert spurious_refusal_rate(outcomes) == 1.0
    assert metric_counts(outcomes)["spurious_refusal_rate__n"] == 1


def test_spurious_refusal_rate_ignores_answered_in_corpus_items() -> None:
    outcomes = [_citation_outcome(["a.org"], ["a.org"])]

    assert spurious_refusal_rate(outcomes) == 0.0
    assert metric_counts(outcomes)["spurious_refusal_rate__n"] == 1


def test_spurious_refusal_rate_averages_declined_and_answered() -> None:
    outcomes = [_declined(["a.org"]), _citation_outcome(["b.org"], ["b.org"])]

    assert spurious_refusal_rate(outcomes) == 0.5


def test_spurious_refusal_rate_keeps_an_errored_item_but_does_not_count_it() -> None:
    errored = ItemOutcome(
        item=_item(["a.org"]), response=None, error="ValueError: boom"
    )

    assert spurious_refusal_rate([errored]) == 0.0
    assert metric_counts([errored])["spurious_refusal_rate__n"] == 1


def test_spurious_refusal_rate_is_zero_with_no_in_corpus_items() -> None:
    assert spurious_refusal_rate([_refusal_outcome(declined=True)]) == 0.0
    assert spurious_refusal_rate([]) == 0.0


def test_refusal_metrics_declare_their_polarity() -> None:
    assert metric_spec("refusal_pass_rate").higher_is_better is True
    assert metric_spec("spurious_refusal_rate").higher_is_better is False


def test_should_refuse_items_do_not_dilute_answer_coverage() -> None:
    outcomes = [
        _citation_outcome(["a.org"], ["a.org"]),
        _citation_outcome(["b.org"], ["b.org"]),
        _refusal_outcome(declined=True),
    ]

    assert stub_metric(outcomes) == 1.0
    assert metric_counts(outcomes)["answer_coverage__n"] == 2
    assert metric_counts(outcomes)["public_references__n"] == 2


def test_answer_coverage_still_counts_an_errored_non_refusal_item() -> None:
    errored = ItemOutcome(
        item=_item(["a.org"]), response=None, error="ValueError: boom"
    )
    outcomes = [_citation_outcome(["a.org"], ["a.org"]), errored]

    assert stub_metric(outcomes) == 0.5
    assert metric_counts(outcomes)["answer_coverage__n"] == 2


def test_reason_counts_name_every_non_answered_in_corpus_item() -> None:
    errored = ItemOutcome(
        item=_item(["a.org"], question="Boom?"),
        response=None,
        error="FabricatedCitation: boom",
    )
    outcomes = [
        _citation_outcome(["a.org"], ["a.org"], question="Answered"),
        _declined(["b.org"], question="Declined"),
        errored,
    ]

    assert reason_counts(outcomes) == {
        "hard_error__n": 1,
        "in_corpus_decline__n": 1,
        "judge_failure__n": 1,
        "non_answered__n": 2,
    }


def test_reason_counts_do_not_call_a_judged_answer_a_judge_failure() -> None:
    outcomes = [_judged(FAITHFUL), _declined(["a.org"])]

    assert reason_counts(outcomes) == {
        "hard_error__n": 0,
        "in_corpus_decline__n": 1,
        "judge_failure__n": 0,
        "non_answered__n": 1,
    }


def test_reason_counts_leave_out_of_corpus_declines_with_the_refusal_metrics() -> None:
    outcomes = [_should_refuse_outcome(declined=True)]

    assert reason_counts(outcomes) == {
        "hard_error__n": 0,
        "in_corpus_decline__n": 0,
        "judge_failure__n": 0,
        "non_answered__n": 0,
    }


def _should_refuse_outcome(
    *,
    declined: bool,
    judged: str | None = None,
    expected_sources: list[str] | None = None,
    question: str = "Refuse?",
) -> ItemOutcome:
    """A should-refuse item's outcome, optionally answered-with-sources and judged."""
    response = (
        ChatResponse(status="insufficient", answer=INSUFFICIENT_ANSWER, citations=[])
        if declined
        else _answered()
    )
    return ItemOutcome(
        item=_item(expected_sources or [], question, should_refuse=True),
        response=response,
        error=None,
        retrieved_sources=None,
        judge_verdict=(
            Verdict(label=judged, rationale="because") if judged is not None else None
        ),
    )


def test_answered_should_refuse_item_is_excluded_from_citation_containment() -> None:
    outcomes = [
        _should_refuse_outcome(declined=False, expected_sources=["a.org"]),
        _citation_outcome(["b.org"], ["a.org"], question="In-corpus miss"),
    ]

    assert citation_correctness(outcomes) == 0.0
    assert metric_counts(outcomes)["citation_correctness__n"] == 1
    assert citation_misses(outcomes) == [
        "In-corpus miss — missing cited source(s): b.org"
    ]


def test_answered_should_refuse_item_is_excluded_from_faithfulness() -> None:
    outcomes = [
        _should_refuse_outcome(declined=False, judged=HALLUCINATED),
        _judged(FAITHFUL, question="In-corpus faithful"),
    ]

    assert faithfulness(outcomes) == 1.0
    assert metric_counts(outcomes)["faithfulness__n"] == 1


def test_declined_should_refuse_item_is_excluded_from_gate_metrics() -> None:
    declined = _should_refuse_outcome(declined=True)

    citation_outcomes = [declined, _citation_outcome(["a.org"], ["a.org"])]
    assert citation_correctness(citation_outcomes) == 1.0
    assert metric_counts(citation_outcomes)["citation_correctness__n"] == 1

    faith_outcomes = [declined, _judged(FAITHFUL)]
    assert faithfulness(faith_outcomes) == 1.0
    assert metric_counts(faith_outcomes)["faithfulness__n"] == 1
