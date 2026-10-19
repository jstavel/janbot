"""Metric-registration interface for the eval harness.

A metric is a pure callable over the list of per-item outcomes, returning one
float for the whole run. Metrics self-register by name, and the runner logs every
registered metric into the MLflow run — so entries 3-5 (retrieval accuracy,
citation correctness, faithfulness detection) add their metrics here without
touching the runner or the recorder.

This package ships a single stub metric so the tracer bullet records a real
MLflow metric before the real metrics exist.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass

from janbot.api.contract import ChatResponse
from janbot.eval.dataset import GoldenItem
from janbot.eval.judge import FAITHFUL, Verdict
from janbot.eval.public_urls import (
    extract_urls,
    is_public_reference,
    load_public_urls,
    missing_references,
)


@dataclass(frozen=True)
class ItemOutcome:
    """One golden item's outcome: the program's response, or the failure that prevented one.

    ``retrieved_sources`` is the corpus-relative set the program retrieved for the
    item, or ``None`` when the run exposed no retrieval claim (a stub program).
    It is read from the retrieval step, never from the answer's citations.

    ``judge_verdict`` is the LLM-as-a-judge's verdict for the item, or ``None``
    when the item was unjudged — no judge was configured, the program produced no
    answer, or the judge call failed. Only judged items count in the
    ``faithfulness`` aggregate.

    ``retrieved_context`` is the exact context the model was given (the window the
    judge checks the answer against), or ``None`` when the run exposed none.

    ``raw_answer`` and ``raw_citations`` are the guard's additive observation seam: the
    prediction and labels before the guard. ``guard_action`` is ``none``/``repaired``/
    ``declined``/``disabled`` plus the rule. They are observability only and never enter a
    metric.
    """

    item: GoldenItem
    response: ChatResponse | None
    error: str | None
    retrieved_sources: list[str] | None = None
    retrieved_context: str | None = None
    judge_verdict: Verdict | None = None
    raw_answer: str | None = None
    raw_citations: list[str] | None = None
    guard_action: str | None = None


Metric = Callable[[list[ItemOutcome]], float]
Eligibility = Callable[[ItemOutcome], bool]


@dataclass(frozen=True)
class MetricSpec:
    """A registered metric with its declared population predicate and polarity."""

    metric: Metric
    denominator: Eligibility
    higher_is_better: bool


_METRICS: dict[str, MetricSpec] = {}


def register_metric(
    name: str,
    metric: Metric,
    *,
    denominator: Eligibility,
    higher_is_better: bool = True,
) -> Metric:
    """Register ``metric`` under ``name`` with its population and polarity, and return it.

    ``denominator`` is the eligibility predicate that selects the metric's
    population — the very predicate the metric aggregates over, so the recorded
    ``<name>__n`` can never drift from the metric's actual population. It is
    keyword-only and required, so a metric that declares no denominator fails
    fast at registration.

    ``higher_is_better`` declares the metric's polarity (default ``True``) so a
    direction is explicit rather than implied.

    Raises:
        TypeError: if ``denominator`` is omitted (it is keyword-only and required).
        ValueError: if ``name`` is blank or already registered, so a metric can
            never be silently overwritten.
    """
    if not name:
        raise ValueError("a metric name must be non-empty")
    if name in _METRICS:
        raise ValueError(f"a metric is already registered as {name!r}")
    _METRICS[name] = MetricSpec(
        metric=metric, denominator=denominator, higher_is_better=higher_is_better
    )
    return metric


def registered_metrics() -> Mapping[str, Metric]:
    """Return a snapshot of the registered metrics keyed by name."""
    return {name: registration.metric for name, registration in _METRICS.items()}


def registered_metric_specs() -> Mapping[str, MetricSpec]:
    """Return a snapshot of the registered specs keyed by name."""
    return dict(_METRICS)


def metric_spec(name: str) -> MetricSpec:
    """Return the registered spec for ``name``.

    Raises:
        KeyError: if no metric is registered under ``name``.
    """
    return _METRICS[name]


def metric_counts(outcomes: list[ItemOutcome]) -> dict[str, int]:
    """Return ``{f"{name}__n": population}`` for every registered metric.

    ``population`` is the number of ``outcomes`` the metric's declared
    denominator selects — the same eligibility its value aggregates over — so
    each ``n`` matches that metric's own population (e.g. faithfulness over
    judged-and-answered items only).
    """
    return {
        f"{name}__n": sum(1 for outcome in outcomes if registration.denominator(outcome))
        for name, registration in _METRICS.items()
    }


def _responded(outcome: ItemOutcome) -> bool:
    """Whether the run returned an ordinary answer: a response observed and not a decline.

    A declined response (``status="insufficient"``) is not an ordinary answer, so
    it is excluded from every claim-making population — a refusal is never scored
    as an uncited or unfaithful answer.
    """
    return outcome.response is not None and outcome.response.status != "insufficient"


def _observed(outcome: ItemOutcome) -> bool:
    """Whether the run returned any response at all — an ordinary answer or a decline.

    The refusal metrics score how the program *behaved* (answered vs declined), so
    their population is observed responses; an errored item (``response is None``)
    is unobserved and excluded.
    """
    return outcome.response is not None


def _declined(outcome: ItemOutcome) -> bool:
    """Whether the run returned a decline: the contract's ``insufficient`` response."""
    return outcome.response is not None and outcome.response.status == "insufficient"


def _refusal_eligible(outcome: ItemOutcome) -> bool:
    """Whether the item should be refused and the run observed a response.

    The population :func:`refusal_pass_rate` aggregates over: a should-refuse item
    whose run produced a response (a clean decline passes; an answer fails). An
    errored item is unobserved, so it is excluded.
    """
    return outcome.item.should_refuse and _observed(outcome)


def _in_corpus_eligible(outcome: ItemOutcome) -> bool:
    """Whether the item is in-corpus and the run observed a response.

    The population :func:`spurious_refusal_rate` aggregates over: an in-corpus item
    whose run produced a response (a decline is a false refusal). An errored item
    is unobserved, so it is excluded.
    """
    return not outcome.item.should_refuse and _observed(outcome)


def _non_refusal_eligible(outcome: ItemOutcome) -> bool:
    """Whether the item is not a should-refuse item.

    The shared eligibility ``answer_coverage``/``public_references`` switch to
    (the entry-16 principle applied), so a correctly-declined refusal item is out
    of their populations entirely and neither value nor denominator is diluted. It
    is intentionally independent of whether a response was observed — those
    metrics already treat an unobserved response as a miss over the item.
    """
    return not outcome.item.should_refuse


def stub_metric(outcomes: list[ItemOutcome]) -> float:
    """Answer coverage: the fraction of in-corpus items the program answered.

    A placeholder for program-level metrics, it counts an in-corpus item as
    covered when a non-decline response was observed. Its population excludes
    should-refuse items (they are scored by the refusal metrics), so the
    denominator matches the recorded ``answer_coverage__n``.
    """
    eligible = [outcome for outcome in outcomes if _non_refusal_eligible(outcome)]
    if not eligible:
        return 0.0
    answered = sum(1 for outcome in eligible if _responded(outcome))
    return answered / len(eligible)


def _item_reference_failures(
    outcome: ItemOutcome, allow_list: Collection[str]
) -> list[str]:
    """Return the human-readable public-reference failures for one item (empty = pass).

    The owner's asymmetry: an answer URL off the allow-list is unverifiable, and an
    expected URL the answer does not surface is incomplete. A missing response
    surfaces nothing, so any expected URL counts as incomplete.
    """
    answer = outcome.response.answer if outcome.response is not None else ""
    answer_urls = extract_urls(answer, allow_list)
    unverifiable = [url for url in answer_urls if not is_public_reference(url, allow_list)]
    expected_urls = extract_urls(outcome.item.expected_answer, allow_list)
    missing = missing_references(expected_urls, answer_urls)

    failures: list[str] = []
    if unverifiable:
        failures.append(
            f"{outcome.item.question} — unverifiable reference(s): {', '.join(unverifiable)}"
        )
    if missing:
        failures.append(
            f"{outcome.item.question} — missing expected reference(s): {', '.join(missing)}"
        )
    return failures


def public_reference_failures(
    outcomes: list[ItemOutcome], allow_list: Collection[str]
) -> list[str]:
    """Return every public-reference failure across ``outcomes``, one line per failure."""
    return [
        failure
        for outcome in outcomes
        for failure in _item_reference_failures(outcome, allow_list)
    ]


def public_references_metric(
    outcomes: list[ItemOutcome], allow_list: Collection[str]
) -> float:
    """Fraction of items whose public references are sound.

    An item passes when its answer carries no off-list URL and surfaces every URL
    its expected answer carries; an item with no URLs on either side passes.
    """
    if not outcomes:
        return 0.0
    passed = sum(1 for outcome in outcomes if not _item_reference_failures(outcome, allow_list))
    return passed / len(outcomes)


def _public_references(outcomes: list[ItemOutcome]) -> float:
    """Public-reference soundness over the non-refusal population (see ``_non_refusal_eligible``)."""
    eligible = [outcome for outcome in outcomes if _non_refusal_eligible(outcome)]
    return public_references_metric(eligible, load_public_urls())


def registered_public_reference_failures(outcomes: list[ItemOutcome]) -> list[str]:
    """Public-reference failures for ``outcomes`` against the committed allow-list."""
    return public_reference_failures(outcomes, load_public_urls())


def _item_retrieval_misses(outcome: ItemOutcome) -> list[str]:
    """Return the human-readable retrieval misses for one item (empty = pass).

    An item makes a retrieval claim only when it names expected sources and the
    run recorded what was retrieved. The golden ``expected_sources`` must be a
    subset of the retrieved set; every expected source the retriever never
    returned is named. The miss is read from the retrieved set, not the citations,
    so a declined answer still resolves against what was retrieved.
    """
    expected = outcome.item.expected_sources
    if not expected or outcome.retrieved_sources is None:
        return []
    retrieved = set(outcome.retrieved_sources)
    missing = [source for source in expected if source not in retrieved]
    if not missing:
        return []
    return [
        f"{outcome.item.question} — missing retrieved source(s): {', '.join(missing)}"
    ]


def retrieval_misses(outcomes: list[ItemOutcome]) -> list[str]:
    """Return every retrieval miss across ``outcomes``, one line per failure."""
    return [
        miss
        for outcome in outcomes
        for miss in _item_retrieval_misses(outcome)
    ]


def _retrieval_eligible(outcome: ItemOutcome) -> bool:
    """Whether the item makes a retrieval claim: it names expected sources and retrieval was observed.

    An item with no expected sources is excluded (no retrieval claim), as is an
    item whose retrieval was never observed. This is the population both the
    ``retrieval_accuracy`` value and its recorded ``__n`` aggregate over.
    """
    return bool(outcome.item.expected_sources) and outcome.retrieved_sources is not None


def retrieval_accuracy(outcomes: list[ItemOutcome]) -> float:
    """Fraction of claim-making items whose expected sources were all retrieved.

    An item counts only when it names expected sources and the run recorded the
    retrieved set; an item with no expected sources is excluded (no retrieval
    claim), as is an item whose retrieval was never observed. The item passes when
    its expected sources are a subset of the retrieved set.
    """
    eligible = [outcome for outcome in outcomes if _retrieval_eligible(outcome)]
    if not eligible:
        return 0.0
    passed = sum(1 for outcome in eligible if not _item_retrieval_misses(outcome))
    return passed / len(eligible)


def retrieval_mrr(outcomes: list[ItemOutcome]) -> float:
    """Mean reciprocal rank of the first expected source in the retrieved list.

    Over the same eligible items as :func:`retrieval_accuracy`, each item scores
    ``1 / rank`` of the first expected source found in the retrieved list (rank is
    1-based, in retrieval order), or ``0.0`` when none is retrieved. Data-level
    and judge-free, it distinguishes a source at rank 1 from one at rank 4 — which
    the binary :func:`retrieval_accuracy` cannot.
    """
    eligible = [outcome for outcome in outcomes if _retrieval_eligible(outcome)]
    if not eligible:
        return 0.0
    total = 0.0
    for outcome in eligible:
        retrieved = outcome.retrieved_sources or []
        expected = set(outcome.item.expected_sources)
        rank = next(
            (
                index
                for index, source in enumerate(retrieved, start=1)
                if source in expected
            ),
            None,
        )
        if rank is not None:
            total += 1.0 / rank
    return total / len(eligible)


def _cited_sources(outcome: ItemOutcome) -> set[str]:
    """The corpus sources the answer cited, or the empty set when there is no response."""
    if outcome.response is None:
        return set()
    return {citation.source for citation in outcome.response.citations}


def _citation_eligible(outcome: ItemOutcome) -> bool:
    """Whether the item makes a citation claim: it names expected sources and the run answered.

    A missing response is unobserved (mirrors ``retrieved_sources is None`` for
    retrieval), so it is excluded. A declined response (``status="insufficient"``)
    is excluded too, so a refusal is never scored as an uncited answer. A
    should-refuse item is the refusal metrics' population whether it was declined
    or answered, so it is excluded from this claim-making population entirely.
    This is the population both the ``citation_correctness``/``citation_precision``
    values and their recorded ``__n`` aggregate over.
    """
    return (
        not outcome.item.should_refuse
        and bool(outcome.item.expected_sources)
        and _responded(outcome)
    )


def _item_citation_misses(outcome: ItemOutcome) -> list[str]:
    """Return the human-readable citation misses for one item (empty = pass).

    The golden ``expected_sources`` must be a subset of the sources the answer
    actually cites — containment, never exact-set equality, so a legitimately
    retrieved related source is not an error. Every expected source the answer
    never cites is named. A declined response is excluded from the population and
    names no miss; a missing response is unobserved and names no miss. The extra,
    retrieved-but-unexpected citations are not misses:
    :func:`citation_precision` carries that signal.
    """
    if not _citation_eligible(outcome):
        return []
    expected = outcome.item.expected_sources
    cited = _cited_sources(outcome)
    missing = [source for source in expected if source not in cited]
    if not missing:
        return []
    return [
        f"{outcome.item.question} — missing cited source(s): {', '.join(missing)}"
    ]


def citation_misses(outcomes: list[ItemOutcome]) -> list[str]:
    """Return every citation miss across ``outcomes``, one line per failure."""
    return [
        miss
        for outcome in outcomes
        for miss in _item_citation_misses(outcome)
    ]


def citation_correctness(outcomes: list[ItemOutcome]) -> float:
    """Fraction of claim-making items whose expected sources were all cited.

    An item counts only when it names expected sources and the run answered it; an
    item with no expected sources, no observed response, or a declined response is
    excluded. The item passes when its expected sources are a subset of the
    sources its answer cites — never exact-set equality, so a related retrieved
    source the answer also cites is not an error.
    """
    eligible = [outcome for outcome in outcomes if _citation_eligible(outcome)]
    if not eligible:
        return 0.0
    passed = sum(1 for outcome in eligible if not _item_citation_misses(outcome))
    return passed / len(eligible)


def citation_precision(outcomes: list[ItemOutcome]) -> float:
    """Informational aggregate: the expected share of the sources items cite.

    Over the same eligible items as :func:`citation_correctness` (expected
    sources named and the run answered — a declined response is excluded), per
    item precision is the fraction of the cited sources that the golden
    ``expected_sources`` also names. The aggregate is their mean, so a
    retrieved-but-unexpected citation lowers this metric without ever failing
    containment.
    """
    precisions: list[float] = []
    for outcome in outcomes:
        if not _citation_eligible(outcome):
            continue
        cited = _cited_sources(outcome)
        if not cited:
            precisions.append(0.0)
            continue
        expected = set(outcome.item.expected_sources)
        precisions.append(len(expected & cited) / len(cited))
    if not precisions:
        return 0.0
    return sum(precisions) / len(precisions)


def _faithfulness_eligible(outcome: ItemOutcome) -> bool:
    """Whether the item was answered and judged: the population faithfulness aggregates over.

    An unjudged item — no judge configured, no answer to judge, or a failed judge
    call — is excluded, as is a declined response. A should-refuse item is the
    refusal metrics' population whether it was declined or answered, so it is
    excluded here. This is the population both the ``faithfulness`` value and its
    recorded ``__n`` aggregate over.
    """
    return (
        not outcome.item.should_refuse
        and _responded(outcome)
        and outcome.judge_verdict is not None
    )


def faithfulness(outcomes: list[ItemOutcome]) -> float:
    """Fraction of judged items the judge found faithful to the golden expected answer.

    An item counts only when it carries a judge verdict and was answered; an
    unjudged item — no judge configured, no answer to judge, or a failed judge
    call — is excluded, as is a declined response. The metric is pure: it never
    calls the judge (the runner runs it per item and stores the verdict). With no
    judged items the aggregate is ``0.0``.
    """
    eligible = [outcome for outcome in outcomes if _faithfulness_eligible(outcome)]
    judged: list[Verdict] = [
        outcome.judge_verdict
        for outcome in eligible
        if outcome.judge_verdict is not None
    ]
    if not judged:
        return 0.0
    faithful = sum(1 for verdict in judged if verdict.label == FAITHFUL)
    return faithful / len(judged)


def refusal_pass_rate(outcomes: list[ItemOutcome]) -> float:
    """Fraction of should-refuse items the program cleanly declined.

    Over the should-refuse items whose run produced a response, an item passes
    when the response is the contract's ``insufficient`` decline; an answered
    out-of-corpus question fails. An errored item is unobserved and excluded. With
    no should-refuse items the aggregate is ``0.0`` (like ``faithfulness`` before
    a judge exists).
    """
    eligible = [outcome for outcome in outcomes if _refusal_eligible(outcome)]
    if not eligible:
        return 0.0
    declined = sum(1 for outcome in eligible if _declined(outcome))
    return declined / len(eligible)


def spurious_refusal_rate(outcomes: list[ItemOutcome]) -> float:
    """Fraction of in-corpus items the program spuriously declined (a false refusal).

    Over the in-corpus items whose run produced a response, an item counts when
    the response is a decline — a question the program should have answered. An
    errored item is unobserved and excluded. Polarity is ``higher_is_better=False``;
    with no in-corpus observed items the aggregate is ``0.0``.
    """
    eligible = [outcome for outcome in outcomes if _in_corpus_eligible(outcome)]
    if not eligible:
        return 0.0
    declined = sum(1 for outcome in eligible if _declined(outcome))
    return declined / len(eligible)


register_metric("answer_coverage", stub_metric, denominator=_non_refusal_eligible)
register_metric(
    "public_references", _public_references, denominator=_non_refusal_eligible
)
register_metric(
    "retrieval_accuracy", retrieval_accuracy, denominator=_retrieval_eligible
)
register_metric("retrieval_mrr", retrieval_mrr, denominator=_retrieval_eligible)
register_metric(
    "citation_correctness", citation_correctness, denominator=_citation_eligible
)
register_metric(
    "citation_precision", citation_precision, denominator=_citation_eligible
)
register_metric(
    "faithfulness",
    faithfulness,
    denominator=_faithfulness_eligible,
    higher_is_better=True,
)
register_metric(
    "refusal_pass_rate",
    refusal_pass_rate,
    denominator=_refusal_eligible,
    higher_is_better=True,
)
register_metric(
    "spurious_refusal_rate",
    spurious_refusal_rate,
    denominator=_in_corpus_eligible,
    higher_is_better=False,
)
