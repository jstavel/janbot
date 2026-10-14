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

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from janbot.api.contract import ChatResponse
from janbot.eval.dataset import GoldenItem


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


register_metric("answer_coverage", stub_metric)
