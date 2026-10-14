"""CLI: ``python -m janbot.eval [--dataset PATH] [--experiment NAME] [--split all|train|val]``.

Builds the app with ``create_app`` (config -> store -> LM -> ``ChatProgram``),
loads the golden dataset, runs every item in the selected split (``all`` by
default) through the pipeline and records one MLflow run at
``MLFLOW_TRACKING_URI`` (default ``sqlite:///mlflow.db``, the epic's SQLite
backend; MLflow 3.x refuses the filesystem backend by default). The run records
the selected ``split`` plus a ``split_manifest.json`` artifact mapping each split
to its dataset indices, so the held-out val set stays auditable. Eval mode needs
no key, so the CLI starts without ``OPENROUTER_API_KEY`` rather than failing on
one. The run parameters are read from the resolved ``Config``
(model mode, snapshot, judge model, temperature, seed, top_k), keeping model
selection configuration-only (AD-5), and the dataset is pinned as an artifact so
runs are comparable. When ``OPENROUTER_API_KEY`` is present the CLI also
builds the LLM-as-a-judge from ``JANBOT_JUDGE_MODEL`` (through the same key) so
the ``faithfulness`` metric is scored; without a key the run stays keyless and
every item is unjudged.

``embedder``, ``lm_factory`` and ``judge`` are optional seams forwarded to
``create_app``/``run_eval``; production leaves them unset (the real adapters),
tests inject stubs so the CLI runs offline and keyless.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from typing import Any

from janbot.config import PROJECT_ROOT, Config, load_config
from janbot.eval.dataset import load_golden_dataset, split_manifest
from janbot.eval.judge import Judge, build_judge
from janbot.eval.optimize import program_marker
from janbot.eval.runner import RunResult, run_eval

DEFAULT_DATASET = PROJECT_ROOT / "eval" / "golden_dataset.yaml"
DEFAULT_EXPERIMENT = "janbot-eval"
TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"


def run_params(config: Config) -> dict[str, Any]:
    """The configuration that produced a run, as MLflow run parameters (AD-5)."""
    return {
        "model_mode": config.model_mode,
        "model_snapshot": config.model_snapshot,
        "judge_model": config.judge_model,
        "temperature": config.temperature,
        "seed": config.seed,
        "top_k": config.top_k,
        "program": program_marker(config.program_path),
    }


def _app_kwargs(embedder: Any, lm_factory: Any) -> dict[str, Any]:
    """Forward the injectable seams to ``create_app`` only when supplied."""
    kwargs: dict[str, Any] = {}
    if embedder is not None:
        kwargs["embedder"] = embedder
    if lm_factory is not None:
        kwargs["lm_factory"] = lm_factory
    return kwargs


def _resolve_judge(
    config: Config, api_key: str | None, lm_factory: Any, judge: Judge | None
) -> Judge | None:
    """Return the injected judge, or build one from config when a key is present.

    A keyless run has no judge (every item stays unjudged). The ``lm_factory``
    seam is forwarded only when supplied, so its own default is not overridden
    with ``None``.
    """
    if judge is not None or not api_key:
        return judge

    from janbot.llm import build_judge_lm

    kwargs = {} if lm_factory is None else {"lm_factory": lm_factory}
    return build_judge(build_judge_lm(config, api_key=api_key, **kwargs))


def main(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    *,
    embedder: Any = None,
    lm_factory: Any = None,
    judge: Judge | None = None,
) -> int:
    """Run the eval end to end and print the tracking URI, run id and metrics.

    ``judge`` is the injectable LLM-as-a-judge seam. When omitted, a real judge is
    built from configuration (``JANBOT_JUDGE_MODEL``) only if
    ``OPENROUTER_API_KEY`` is present: a keyless eval run has no judge, so every
    item is unjudged and the ``faithfulness`` metric stays at ``0`` over no
    eligible items rather than calling an unauthenticated model.
    """
    from janbot.api.main import create_app

    parser = argparse.ArgumentParser(prog="python -m janbot.eval")
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET),
        help=f"golden dataset path (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--experiment",
        default=DEFAULT_EXPERIMENT,
        help=f"MLflow experiment name (default: {DEFAULT_EXPERIMENT})",
    )
    parser.add_argument(
        "--split",
        choices=("all", "train", "val"),
        default="all",
        help="dataset split to evaluate: all, train or val (default: all)",
    )
    args = parser.parse_args(argv)

    source = os.environ if env is None else env
    tracking_uri = source.get(TRACKING_URI_ENV) or DEFAULT_TRACKING_URI

    config = load_config(source)
    api_key = (source.get(OPENROUTER_API_KEY_ENV) or "").strip() or None
    judge = _resolve_judge(config, api_key, lm_factory, judge)

    all_items = load_golden_dataset(args.dataset)
    items = (
        all_items
        if args.split == "all"
        else [item for item in all_items if item.split == args.split]
    )
    if not items:
        print(
            f"no golden items for split {args.split!r} in {args.dataset}",
            file=sys.stderr,
        )
        return 2

    app = create_app(env=source, **_app_kwargs(embedder, lm_factory))
    params = run_params(config)
    params["split"] = args.split
    result: RunResult = run_eval(
        items,
        app.state.program,
        tracking_uri=tracking_uri,
        experiment=args.experiment,
        params=params,
        judge=judge,
        dataset_path=args.dataset,
        split_manifest=split_manifest(all_items),
    )

    print(f"MLflow tracking URI: {tracking_uri}")
    print(f"MLflow run: {result.run_id}")
    print(f"items: {len(result.outcomes)}")
    for name, value in result.metrics.items():
        count = result.counts.get(f"{name}__n", 0)
        print(f"{name}: {value:.4f} (n={count})")

    for failure in result.reference_failures:
        print(f"reference: {failure}")

    for miss in result.retrieval_misses:
        print(f"retrieval: {miss}")

    for miss in result.citation_misses:
        print(f"citation: {miss}")

    judged = [outcome for outcome in result.outcomes if outcome.judge_verdict is not None]
    print(f"judged: {len(judged)}/{len(result.outcomes)}")
    for outcome in judged:
        verdict = outcome.judge_verdict
        if verdict is None:
            continue
        print(f"judge: {outcome.item.question} — {verdict.label}")

    for failure in result.judge_failures:
        print(f"judge: {failure}")

    failures = [outcome for outcome in result.outcomes if outcome.response is None]
    for outcome in failures:
        print(f"failed: {outcome.item.question} — {outcome.error}")

    if failures and len(failures) == len(result.outcomes):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
