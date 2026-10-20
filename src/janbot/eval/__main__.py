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
(model mode, snapshot, judge model, temperature, seed, top_k, retrieval mode,
retrieval window, relevance threshold),
keeping model selection configuration-only (AD-5), and the dataset is pinned as
an artifact so runs are comparable. When ``OPENROUTER_API_KEY`` is present the CLI also
builds the LLM-as-a-judge from ``JANBOT_JUDGE_MODEL`` (through the same key) so
the ``faithfulness`` metric is scored; without a key the run stays keyless and
every item is unjudged.

``embedder``, ``lm_factory`` and ``judge`` are optional seams forwarded to
``create_app``/``run_eval``; production leaves them unset (the real adapters),
tests inject stubs so the CLI runs offline and keyless.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from janbot.config import PROJECT_ROOT, Config, load_config
from janbot.eval.dataset import load_golden_dataset, split_manifest
from janbot.eval.judge import Judge, build_judge
from janbot.eval.optimize import program_marker
from janbot.eval.runner import RunResult, run_eval
from janbot.guardrails.cache import corpus_sha256
from janbot.guardrails.limits import GuardDecision

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
        "retrieval_mode": config.retrieval_mode,
        "retrieval_window": config.retrieval_window,
        "relevance_threshold": config.relevance_threshold,
        "output_guard": config.output_guard,
        "program": program_marker(config.program_path),
        "judge_input": "context",
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


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _corpus_commit() -> str:
    """The commit the corpus was pinned at; refuses a dirty corpus tree."""
    dirty = _git("status", "--porcelain", "--", "public_profile_org")
    if dirty:
        raise RuntimeError(
            "public_profile_org has uncommitted changes; commit the corpus "
            "before recording a cache artifact"
        )
    return _git("rev-parse", "HEAD")


class _NoopLimiter:
    """The export run needs the program, not the shared request controls."""

    def check_rate(self, client_ip: str) -> GuardDecision:
        return GuardDecision.allow()

    def consume_quota(self) -> GuardDecision:
        return GuardDecision.allow()


def write_cache_artifact(path: str | Path, result: RunResult, config: Config) -> int:
    """Write the pinned production answer cache; return its entry count.

    Only a non-refusal, answered item enters the cache: a should-refuse item and
    an ``insufficient`` reply stay live, because the θ gate declines them before
    the LM and caching them would freeze the item-3 reason heuristic.
    """
    entries: list[dict[str, Any]] = []
    routed: set[str] = set()
    for outcome in result.outcomes:
        if outcome.item.should_refuse or outcome.response is None:
            continue
        if outcome.response.status != "answered":
            continue
        if outcome.routed_model:
            routed.add(outcome.routed_model)
        entries.append(
            {
                "question": outcome.item.question,
                "response": outcome.response.model_dump(mode="json"),
                "routed_model": outcome.routed_model,
            }
        )
    if not entries:
        raise RuntimeError("the run produced no non-refusal answers to cache")

    dataset = PROJECT_ROOT / "eval" / "golden_dataset.yaml"
    if not dataset.is_file():
        raise RuntimeError(f"golden dataset not found: {dataset}")
    document = {
        "metadata": {
            "run_id": result.run_id,
            "date": datetime.now(UTC).date().isoformat(),
            "model_mode": config.model_mode,
            "requested_model": "openrouter/auto",
            "routed_models": sorted(routed),
            "dataset": "eval/golden_dataset.yaml",
            "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            "corpus_commit": _corpus_commit(),
            "corpus_sha256": corpus_sha256(PROJECT_ROOT / "public_profile_org"),
            "output_guard": config.output_guard,
            "split": "val",
        },
        "entries": entries,
    }
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return len(entries)


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
    parser.add_argument(
        "--answers",
        action="store_true",
        help="print each item's answer text (to diagnose judge verdicts)",
    )
    parser.add_argument(
        "--cache-out",
        default=None,
        help=(
            "write the pinned production answer-cache artifact (non-refusal "
            "val answers) to this path; requires JANBOT_MODEL_MODE=production"
        ),
    )
    args = parser.parse_args(argv)

    source = os.environ if env is None else env
    tracking_uri = source.get(TRACKING_URI_ENV) or DEFAULT_TRACKING_URI

    config = load_config(source)
    if args.cache_out is not None:
        if args.split != "val":
            print(
                "--cache-out requires --split val; the cache covers the val "
                "non-refusal set",
                file=sys.stderr,
            )
            return 2
        if config.model_mode != "production":
            print(
                "--cache-out requires JANBOT_MODEL_MODE=production; the cache "
                "must be a snapshot of what the service actually does",
                file=sys.stderr,
            )
            return 2
        if config.output_guard != "on":
            print(
                "--cache-out requires JANBOT_OUTPUT_GUARD=on; an unguarded "
                "snapshot would be rejected by the image build",
                file=sys.stderr,
            )
            return 2
    api_key = (source.get(OPENROUTER_API_KEY_ENV) or "").strip() or None
    judge = None if args.cache_out else _resolve_judge(config, api_key, lm_factory, judge)

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

    app = create_app(
        env=source,
        limiter=_NoopLimiter() if args.cache_out is not None else None,
        require_cache=args.cache_out is None,
        **_app_kwargs(embedder, lm_factory),
    )
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

    if args.cache_out is not None:
        cached = write_cache_artifact(args.cache_out, result, config)
        print(f"cache: {cached} non-refusal answers -> {args.cache_out}")
    for name, value in result.metrics.items():
        count = result.counts.get(f"{name}__n", 0)
        print(f"{name}: {value:.4f} (n={count})")

    for name, count in result.reason_counts.items():
        print(f"{name}: {count}")

    for failure in result.reference_failures:
        print(f"reference: {failure}")

    for miss in result.retrieval_misses:
        print(f"retrieval: {miss}")

    for miss in result.citation_misses:
        print(f"citation: {miss}")

    for outcome in result.outcomes:
        response = outcome.response
        if response is None:
            continue
        if response.status == "insufficient":
            print(f"decline: {outcome.item.question} — {response.reason}")
        if outcome.item.should_refuse and response.status != "insufficient":
            print(f"refusal: {outcome.item.question} — answered a should-refuse item")
        elif not outcome.item.should_refuse and response.status == "insufficient":
            print(f"refusal: {outcome.item.question} — declined an in-corpus item")

    judged = [outcome for outcome in result.outcomes if outcome.judge_verdict is not None]
    print(f"judged: {len(judged)}/{len(result.outcomes)}")
    for outcome in judged:
        verdict = outcome.judge_verdict
        if verdict is None:
            continue
        print(f"judge: {outcome.item.question} — {verdict.label}")

    for failure in result.judge_failures:
        print(f"judge: {failure}")

    for outcome in result.outcomes:
        question = outcome.item.question
        retrieved = ", ".join(outcome.retrieved_sources or []) or "<none>"
        raw_answer = "<none>" if outcome.raw_answer is None else outcome.raw_answer
        raw_citations = ", ".join(outcome.raw_citations or []) or "<none>"
        guard_action = outcome.guard_action or "<none>"
        normalized = "<none>" if outcome.normalized_citations is None else str(outcome.normalized_citations)
        print(f"retrieved: {question} — {retrieved}")
        print(f"raw-answer: {question} — {raw_answer}")
        print(f"raw-citations: {question} — {raw_citations}")
        print(f"normalized: {question} — {normalized}")
        print(f"guard: {question} — {guard_action}")

    if args.answers:
        for outcome in result.outcomes:
            if outcome.response is None:
                continue
            print(f"answer: {outcome.item.question} — {outcome.response.answer}")

    failures = [outcome for outcome in result.outcomes if outcome.response is None]
    for outcome in failures:
        print(f"failed: {outcome.item.question} — {outcome.error}")

    if failures and len(failures) == len(result.outcomes):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
