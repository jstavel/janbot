"""Run the golden dataset through the pipeline and record one MLflow run.

``run_eval`` is the thinnest dataset -> pipeline -> MLflow path (CAP-8 tracer
bullet). It calls ``program`` once per item, capturing a per-item failure as an
outcome rather than aborting the run, computes every registered metric over the
outcomes, then records exactly one MLflow run carrying the run parameters and
the metrics. It never builds the pipeline itself: the CLI injects the
``ChatProgram`` produced by ``create_app`` and tests inject a stub program, so
the core is keyless and offline. MLflow logging happens after every program call
— off the request path — and a failing tracking backend raises naming the URI
rather than reporting a partial success.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import mlflow

from janbot.api.contract import ChatResponse
from janbot.eval.dataset import GoldenItem
from janbot.eval.judge import Judge, Verdict
from janbot.eval.metrics import (
    ItemOutcome,
    citation_misses,
    registered_metrics,
    registered_public_reference_failures,
    retrieval_misses,
)


@dataclass(frozen=True)
class RunResult:
    """The recorded run: per-item outcomes, aggregate metrics, MLflow run id, reference flags."""

    outcomes: list[ItemOutcome]
    metrics: dict[str, float]
    run_id: str
    reference_failures: list[str]
    retrieval_misses: list[str]
    citation_misses: list[str]
    judge_failures: list[str]


def _retrieved_sources(program: Callable[..., ChatResponse]) -> list[str] | None:
    """The corpus-relative sources the program last retrieved, or ``None`` if it exposes none.

    The ``ChatProgram`` records what it retrieved on ``last_retrieved_sources``
    (an additive attribute); a stub program without it makes no retrieval claim,
    so its items are excluded from the retrieval-accuracy aggregate.
    """
    retrieved = getattr(program, "last_retrieved_sources", None)
    return None if retrieved is None else list(retrieved)


def _evaluate(
    items: list[GoldenItem],
    program: Callable[..., ChatResponse],
    judge: Judge | None,
) -> tuple[list[ItemOutcome], list[str]]:
    """Call ``program`` for every item, recording a per-item failure as an outcome.

    When a ``judge`` is supplied it is called per answered item and its verdict
    stored; a judge that raises marks that item unjudged (a ``judge_failures``
    line) without aborting the run. An item the program failed to answer has no
    text to judge, so it is unjudged too.
    """
    outcomes: list[ItemOutcome] = []
    judge_failures: list[str] = []
    for item in items:
        try:
            response = program(question=item.question)
        except Exception as exc:
            outcomes.append(
                ItemOutcome(
                    item=item,
                    response=None,
                    error=f"{type(exc).__name__}: {exc}",
                    retrieved_sources=_retrieved_sources(program),
                    judge_verdict=None,
                )
            )
            continue

        verdict: Verdict | None = None
        if judge is not None:
            try:
                verdict = judge(item.expected_answer, response.answer)
            except Exception as exc:
                judge_failures.append(
                    f"{item.question} — judge failed: {type(exc).__name__}: {exc}"
                )
        outcomes.append(
            ItemOutcome(
                item=item,
                response=response,
                error=None,
                retrieved_sources=_retrieved_sources(program),
                judge_verdict=verdict,
            )
        )
    return outcomes, judge_failures


def _record(
    tracking_uri: str,
    experiment: str,
    params: Mapping[str, Any],
    metrics: Mapping[str, float],
) -> str:
    """Write one MLflow run holding ``params`` and ``metrics``; return its run id."""
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)
    with mlflow.start_run() as run:
        if params:
            mlflow.log_params(dict(params))
        if metrics:
            mlflow.log_metrics(dict(metrics))
        return run.info.run_id


def run_eval(
    items: Iterable[GoldenItem],
    program: Callable[..., ChatResponse],
    *,
    tracking_uri: str,
    experiment: str,
    params: Mapping[str, Any] | None = None,
    judge: Judge | None = None,
) -> RunResult:
    """Run every item through ``program`` and record one MLflow run.

    ``params`` carries the configuration that produced the run (model mode,
    snapshot, temperature, seed); the metrics are every registered metric
    computed over the outcomes. ``judge`` is the optional LLM-as-a-judge: when
    supplied it is run once per answered item and its verdict recorded, so the
    ``hallucination`` metric has something to aggregate; when omitted every item
    stays unjudged and the run remains keyless.

    Raises:
        RuntimeError: if the MLflow run cannot be written, naming the tracking
            URI and chaining the underlying error (no partial silent success).
    """
    item_list = list(items)
    outcomes, judge_failures = _evaluate(item_list, program, judge)
    metrics = {
        name: float(metric(outcomes)) for name, metric in registered_metrics().items()
    }
    try:
        run_id = _record(tracking_uri, experiment, params or {}, metrics)
    except Exception as exc:
        raise RuntimeError(
            f"MLflow logging to tracking URI {tracking_uri!r} failed: {exc}"
        ) from exc
    return RunResult(
        outcomes=outcomes,
        metrics=metrics,
        run_id=run_id,
        reference_failures=registered_public_reference_failures(outcomes),
        retrieval_misses=retrieval_misses(outcomes),
        citation_misses=citation_misses(outcomes),
        judge_failures=judge_failures,
    )
