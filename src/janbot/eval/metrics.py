"""Metric-registration interface for the eval harness.

A metric is a pure callable over the list of per-item outcomes, returning one
float for the whole run. Metrics self-register by name, and the runner logs every
registered metric into the MLflow run — so entries 3-5 (retrieval accuracy,
citation correctness, hallucination detection) add their metrics here without
touching the runner or the recorder.

This package ships a single stub metric so the tracer bullet records a real
MLflow metric before the real metrics exist.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass

from janbot.api.contract import ChatResponse
from janbot.eval.dataset import GoldenItem
from janbot.eval.public_urls import (
    extract_urls,
    is_public_reference,
    load_public_urls,
    missing_references,
)


@dataclass(frozen=True)
class ItemOutcome:
    """One golden item's outcome: the program's response, or the failure that prevented one."""

    item: GoldenItem
    response: ChatResponse | None
    error: str | None


Metric = Callable[[list[ItemOutcome]], float]

_METRICS: dict[str, Metric] = {}


def register_metric(name: str, metric: Metric) -> Metric:
    """Register ``metric`` under ``name`` and return it.

    Raises:
        ValueError: if ``name`` is blank or already registered, so a metric can
            never be silently overwritten.
    """
    if not name:
        raise ValueError("a metric name must be non-empty")
    if name in _METRICS:
        raise ValueError(f"a metric is already registered as {name!r}")
    _METRICS[name] = metric
    return metric


def registered_metrics() -> Mapping[str, Metric]:
    """Return a snapshot of the registered metrics keyed by name."""
    return dict(_METRICS)


def stub_metric(outcomes: list[ItemOutcome]) -> float:
    """Stub metric: the fraction of items the program answered without raising.

    A placeholder for the real retrieval/citation/hallucination metrics, it lets
    the tracer bullet prove the dataset -> pipeline -> MLflow path end to end
    without a judge or a golden-source comparison.
    """
    if not outcomes:
        return 0.0
    answered = sum(1 for outcome in outcomes if outcome.response is not None)
    return answered / len(outcomes)


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
    return public_references_metric(outcomes, load_public_urls())


def registered_public_reference_failures(outcomes: list[ItemOutcome]) -> list[str]:
    """Public-reference failures for ``outcomes`` against the committed allow-list."""
    return public_reference_failures(outcomes, load_public_urls())


register_metric("answer_coverage", stub_metric)
register_metric("public_references", _public_references)
