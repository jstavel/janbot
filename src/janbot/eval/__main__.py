"""CLI: ``python -m janbot.eval [--dataset PATH] [--experiment NAME]``.

Builds the app with ``create_app`` (config -> store -> LM -> ``ChatProgram``),
loads the golden dataset, runs every question through the pipeline and records
one MLflow run at ``MLFLOW_TRACKING_URI`` (default ``sqlite:///mlflow.db``, the
epic's SQLite backend; MLflow 3.x refuses the filesystem backend by default).
Eval mode needs no key, so the CLI starts without ``OPENROUTER_API_KEY`` rather
than failing on one. The run parameters are read from the resolved ``Config``
(model mode, snapshot, temperature, seed), keeping model selection
configuration-only (AD-5).

``embedder`` and ``lm_factory`` are optional seams forwarded to ``create_app``;
production leaves them unset (the real adapters), tests inject stubs so the CLI
runs offline and keyless.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from typing import Any

from janbot.config import PROJECT_ROOT, Config, load_config
from janbot.eval.dataset import load_golden_dataset
from janbot.eval.runner import RunResult, run_eval

DEFAULT_DATASET = PROJECT_ROOT / "eval" / "golden_dataset.yaml"
DEFAULT_EXPERIMENT = "janbot-eval"
TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"


def run_params(config: Config) -> dict[str, Any]:
    """The configuration that produced a run, as MLflow run parameters (AD-5)."""
    return {
        "model_mode": config.model_mode,
        "model_snapshot": config.model_snapshot,
        "temperature": config.temperature,
        "seed": config.seed,
    }


def _app_kwargs(embedder: Any, lm_factory: Any) -> dict[str, Any]:
    """Forward the injectable seams to ``create_app`` only when supplied."""
    kwargs: dict[str, Any] = {}
    if embedder is not None:
        kwargs["embedder"] = embedder
    if lm_factory is not None:
        kwargs["lm_factory"] = lm_factory
    return kwargs


def main(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    *,
    embedder: Any = None,
    lm_factory: Any = None,
) -> int:
    """Run the eval end to end and print the tracking URI, run id and metrics."""
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
    args = parser.parse_args(argv)

    source = os.environ if env is None else env
    tracking_uri = source.get(TRACKING_URI_ENV) or DEFAULT_TRACKING_URI

    config = load_config(source)
    app = create_app(env=source, **_app_kwargs(embedder, lm_factory))
    items = load_golden_dataset(args.dataset)
    result: RunResult = run_eval(
        items,
        app.state.program,
        tracking_uri=tracking_uri,
        experiment=args.experiment,
        params=run_params(config),
    )

    print(f"MLflow tracking URI: {tracking_uri}")
    print(f"MLflow run: {result.run_id}")
    print(f"items: {len(result.outcomes)}")
    for name, value in result.metrics.items():
        print(f"{name}: {value:.4f}")

    failures = [outcome for outcome in result.outcomes if outcome.response is None]
    for outcome in failures:
        print(f"failed: {outcome.item.question} — {outcome.error}")

    if failures and len(failures) == len(result.outcomes):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
