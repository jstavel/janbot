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

import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
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
    *,
    dataset_path: str | Path | None = None,
) -> str:
    """Write one MLflow run holding ``params`` and ``metrics``; return its run id.

    When ``dataset_path`` is given its sha256 joins the params and the file is
    attached as an artifact, so a run pins the exact dataset that produced its
    metrics and two runs are comparable.
    """
    logged_params = dict(params)
    dataset_file = Path(dataset_path) if dataset_path is not None else None
    if dataset_file is not None:
        logged_params["dataset_sha256"] = hashlib.sha256(
            dataset_file.read_bytes()
        ).hexdigest()
    run_name = f"{logged_params.get('model_mode', 'eval')}-{str(logged_params.get('dataset_sha256', 'nodataset'))[:8]}"

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name) as run:
        if logged_params:
            mlflow.log_params(logged_params)
        if dataset_file is not None:
            mlflow.log_artifact(str(dataset_file))
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
    dataset_path: str | Path | None = None,
) -> RunResult:
    """Run every item through ``program`` and record one MLflow run.

    ``params`` carries the configuration that produced the run (model mode,
    snapshot, judge model, temperature, seed, top_k); the metrics are every
    registered metric computed over the outcomes. ``dataset_path`` pins the exact
    dataset (its sha256 as a param, the file as an artifact) so runs are
    comparable. ``judge`` is the optional LLM-as-a-judge: when supplied it is run
    once per answered item and its verdict recorded, so the ``hallucination``
    metric has something to aggregate; when omitted every item stays unjudged and
    the run remains keyless.

    Raises:
        FileNotFoundError: if ``dataset_path`` is given but does not exist.
        RuntimeError: if the MLflow run cannot be written, naming the tracking
            URI and chaining the underlying error (no partial silent success).
    """
    item_list = list(items)
    if dataset_path is not None and not Path(dataset_path).is_file():
        raise FileNotFoundError(f"golden dataset not found: {Path(dataset_path)}")
    outcomes, judge_failures = _evaluate(item_list, program, judge)
    metrics = {
        name: float(metric(outcomes)) for name, metric in registered_metrics().items()
    }
    try:
        run_id = _record(
            tracking_uri, experiment, params or {}, metrics, dataset_path=dataset_path
        )
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
