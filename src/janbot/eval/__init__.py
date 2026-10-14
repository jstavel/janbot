"""Evaluation harness for JanBot (Milestone 2, CAP-8).

Exposes the golden-dataset contract, the metric-registration interface, and the
``run_eval`` recorder. The pipeline is never imported here: the CLI injects the
``ChatProgram`` built by ``create_app`` and tests inject a stub, so the harness
is usable without a model key.
"""

from janbot.eval.dataset import GoldenItem, load_golden_dataset
from janbot.eval.metrics import ItemOutcome, Metric, register_metric, registered_metrics
from janbot.eval.runner import RunResult, run_eval

__all__ = [
    "GoldenItem",
    "ItemOutcome",
    "Metric",
    "RunResult",
    "load_golden_dataset",
    "register_metric",
    "registered_metrics",
    "run_eval",
]
