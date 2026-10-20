"""Run the golden dataset through the pipeline and record one MLflow run.

``run_eval`` is the thinnest dataset -> pipeline -> MLflow path (CAP-8 tracer
bullet). It calls ``program`` once per item, capturing a per-item failure as an
outcome rather than aborting the run, maps a program decline to the contract's
``insufficient`` response (a defined outcome, not a failure), computes every
registered metric over the outcomes, then records exactly one MLflow run carrying
the run parameters and the metrics. It never builds the pipeline itself: the CLI
injects the ``ChatProgram`` produced by ``create_app`` and tests inject a stub
program, so the core is keyless and offline. MLflow logging happens after every
program call — off the request path — and a failing tracking backend raises naming
the URI rather than reporting a partial success.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlflow

from janbot.api.contract import ChatResponse, decline
from janbot.eval.dataset import GoldenItem
from janbot.eval.judge import Judge, Verdict
from janbot.eval.metrics import (
    ItemOutcome,
    citation_misses,
    metric_counts,
    reason_counts,
    registered_metrics,
    registered_public_reference_failures,
    retrieval_misses,
)
from janbot.pipeline.chat import EmptyRetrieval, LowRelevance, UncitedAnswer

SPLIT_MANIFEST_FILENAME = "split_manifest.json"


@dataclass(frozen=True)
class RunResult:
    """The recorded run: per-item outcomes, aggregate metrics, counts, MLflow run id, reference flags."""

    outcomes: list[ItemOutcome]
    metrics: dict[str, float]
    counts: dict[str, int]
    reason_counts: dict[str, int]
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


def _retrieved_context(program: Callable[..., ChatResponse]) -> str | None:
    """The exact context the program last gave the model, or ``None`` if it exposes none.

    The ``ChatProgram`` records it on ``last_retrieved_context`` (an additive
    attribute); it is the window the judge checks an answer against.
    """
    context = getattr(program, "last_retrieved_context", None)
    return None if context is None else str(context)


def _raw_answer(program: Callable[..., ChatResponse]) -> str | None:
    """The prediction before the output guard, from the additive seam."""
    answer = getattr(program, "last_raw_answer", None)
    return None if answer is None else str(answer)


def _raw_citations(program: Callable[..., ChatResponse]) -> list[str] | None:
    """The labels the model cited before D1, from the additive seam."""
    citations = getattr(program, "last_raw_citations", None)
    return None if citations is None else list(citations)


def _guard_action(program: Callable[..., ChatResponse]) -> str | None:
    """The guard action (closed set: none/repaired/declined/disabled)."""
    action = getattr(program, "last_guard_action", None)
    return None if action is None else str(action)


def _normalized_citations(program: Callable[..., ChatResponse]) -> int | None:
    """How many alias labels the guard resolved before D1, from the additive seam."""
    count = getattr(program, "last_normalized_citations", None)
    return None if count is None else int(count)


def _evaluate(
    items: list[GoldenItem],
    program: Callable[..., ChatResponse],
    judge: Judge | None,
) -> tuple[list[ItemOutcome], list[str]]:
    """Call ``program`` for every item, recording a per-item failure as an outcome.

    A decline is a defined outcome, not an error: the program's decline signal
    (:class:`EmptyRetrieval`/:class:`LowRelevance`/:class:`UncitedAnswer`) is mapped to the exact
    production shape the API returns — the contract's ``insufficient``
    ``ChatResponse`` — so the eval observes what production returns. A declined
    item is unjudged (there is no answer text to judge) and is not a failure. Every
    other exception, including the fabricated/unattributable refusals the API maps
    to 500, is recorded as an error outcome.

    When a ``judge`` is supplied it is called per answered in-corpus item and its
    verdict stored; a judge that raises marks that item unjudged (a
    ``judge_failures`` line) without aborting the run. An item the program failed
    to answer has no text to judge, so it is unjudged too, and a should-refuse item
    is never judged — it belongs to the refusal metrics' population, not the judged
    one, whether it was declined or answered.
    """
    outcomes: list[ItemOutcome] = []
    judge_failures: list[str] = []
    for item in items:
        try:
            response = program(question=item.question)
        except (EmptyRetrieval, LowRelevance, UncitedAnswer):
            outcomes.append(
                ItemOutcome(
                    item=item,
                    response=decline(item.question),
                    error=None,
                    retrieved_sources=_retrieved_sources(program),
                    retrieved_context=_retrieved_context(program),
                    raw_answer=_raw_answer(program),
                    raw_citations=_raw_citations(program),
                    guard_action=_guard_action(program),
                    normalized_citations=_normalized_citations(program),
                    judge_verdict=None,
                )
            )
            continue
        except Exception as exc:
            outcomes.append(
                ItemOutcome(
                    item=item,
                    response=None,
                    error=f"{type(exc).__name__}: {exc}",
                    retrieved_sources=_retrieved_sources(program),
                    retrieved_context=_retrieved_context(program),
                    raw_answer=_raw_answer(program),
                    raw_citations=_raw_citations(program),
                    guard_action=_guard_action(program),
                    normalized_citations=_normalized_citations(program),
                    judge_verdict=None,
                )
            )
            continue

        verdict: Verdict | None = None
        if judge is not None and not item.should_refuse:
            try:
                verdict = judge(_retrieved_context(program) or "", response.answer)
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
                retrieved_context=_retrieved_context(program),
                raw_answer=_raw_answer(program),
                raw_citations=_raw_citations(program),
                guard_action=_guard_action(program),
                normalized_citations=_normalized_citations(program),
                judge_verdict=verdict,
            )
        )
    return outcomes, judge_failures


def _record(
    tracking_uri: str,
    experiment: str,
    params: Mapping[str, Any],
    metrics: Mapping[str, float],
    counts: Mapping[str, int],
    *,
    dataset_path: str | Path | None = None,
    split_manifest: Mapping[str, Any] | None = None,
) -> str:
    """Write one MLflow run holding ``params``, ``metrics`` and their ``counts``; return its run id.

    Each metric's population count is logged beside its score as the numeric
    ``<metric>__n``, so it charts with the score. When ``dataset_path`` is given
    its sha256 joins the params and the file is attached as an artifact, so a run
    pins the exact dataset that produced its metrics and two runs are comparable.
    When ``split_manifest`` is given it is logged as ``split_manifest.json``
    beside the dataset artifact, pinning which dataset indices were held out.
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
        if split_manifest is not None:
            mlflow.log_dict(dict(split_manifest), SPLIT_MANIFEST_FILENAME)
        logged_metrics = {**metrics, **counts}
        if logged_metrics:
            mlflow.log_metrics({name: float(value) for name, value in logged_metrics.items()})
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
    split_manifest: Mapping[str, Any] | None = None,
) -> RunResult:
    """Run every item through ``program`` and record one MLflow run.

    ``params`` carries the configuration that produced the run (model mode,
    snapshot, judge model, temperature, seed, top_k, retrieval mode, retrieval
    window, relevance threshold); the metrics are every
    registered metric computed over the outcomes. ``dataset_path`` pins the exact
    dataset (its sha256 as a param, the file as an artifact) so runs are
    comparable. ``split_manifest`` is logged as ``split_manifest.json`` beside
    the dataset artifact, so the run records which indices were held out.
    ``judge`` is the optional LLM-as-a-judge: when supplied it is run
    once per answered item and its verdict recorded, so the ``faithfulness``
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
    counts = metric_counts(outcomes)
    reasons = reason_counts(outcomes)
    try:
        run_id = _record(
            tracking_uri,
            experiment,
            params or {},
            metrics,
            {**counts, **reasons},
            dataset_path=dataset_path,
            split_manifest=split_manifest,
        )
    except Exception as exc:
        raise RuntimeError(
            f"MLflow logging to tracking URI {tracking_uri!r} failed: {exc}"
        ) from exc
    return RunResult(
        outcomes=outcomes,
        metrics=metrics,
        counts=counts,
        reason_counts=reasons,
        run_id=run_id,
        reference_failures=registered_public_reference_failures(
            [outcome for outcome in outcomes if not outcome.item.should_refuse]
        ),
        retrieval_misses=retrieval_misses(outcomes),
        citation_misses=citation_misses(outcomes),
        judge_failures=judge_failures,
    )
