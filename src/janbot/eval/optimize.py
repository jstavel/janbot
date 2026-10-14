"""Compile the ``/chat`` program with BootstrapFewShot (epic-evaluation, entry 8).

Entry 7 recorded the baseline (retrieval 0.78, citation 0.77, faithfulness 0.66)
and ruled ``BootstrapFewShot`` *needed*; this module is the stage that produces
the durable asset: a **compiled program** persisted as a DSPy JSON state file and
logged as an MLflow artifact. The compiled program is pinned by configuration
(``JANBOT_PROGRAM_PATH``), so production and eval load it without recompiling.

The compile metric is deterministic — "the answer is non-empty and cites every
golden source" — so bootstrapping costs no judge call. The teacher is the locked
snapshot (the LM the student already runs under in ``eval`` mode), passed through
``teacher_settings`` so a bootstrapped round runs without touching the student's
own predictor state.

``dspy`` is imported lazily inside :func:`trainset_from` and
:func:`compile_fewshot`, never at module import: the eval CLI must keep the
documented store-before-``dspy`` import order (``dspy`` installs a lazy numpy
proxy that breaks numpy when it lands before ``chromadb``). ``save_program`` and
``load_program`` operate on an already-built program and need no ``dspy`` import.

This stage never changes ``/chat`` behavior or ingestion: the compiled program is
the same architecture, only carrying bootstrapped demonstrations.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import mlflow

from janbot.config import PROJECT_ROOT, load_config
from janbot.eval.dataset import GoldenItem, load_golden_dataset, split_manifest
from janbot.eval.runner import SPLIT_MANIFEST_FILENAME

DEFAULT_DATASET = PROJECT_ROOT / "eval" / "golden_dataset.yaml"
DEFAULT_OUT = PROJECT_ROOT / "eval" / "compiled_fewshot.json"
DEFAULT_EXPERIMENT = "janbot-eval"
TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"

MAX_BOOTSTRAPPED_DEMOS = 4
MAX_LABELED_DEMOS = 0
PROGRAM_MARKER_PREFIX = "fewshot"
BASELINE_MARKER = "baseline"
_MARKER_SHA_LENGTH = 12


def trainset_from(items: Iterable[GoldenItem]) -> list[Any]:
    """Build the DSPy trainset from golden items.

    Each item becomes a :class:`dspy.Example` carrying the question, the golden
    answer and the golden sources; only ``question`` is an input (the pipeline
    retrieves its own context), so the metric compares the program's answer and
    citations against the remaining fields.
    """
    import dspy

    return [
        dspy.Example(
            question=item.question,
            expected_answer=item.expected_answer,
            expected_sources=list(item.expected_sources),
        ).with_inputs("question")
        for item in items
    ]


def _cited_sources(prediction: Any) -> set[str]:
    """The sources a prediction cites, tolerant of ``Citation`` objects or bare strings."""
    citations = getattr(prediction, "citations", None) or []
    sources: set[str] = set()
    for citation in citations:
        sources.add(str(getattr(citation, "source", citation)))
    return sources


def compile_metric(example: Any, prediction: Any, trace: Any = None) -> bool:
    """Deterministic BootstrapFewShot metric: answers and cites all expected sources.

    Returns ``True`` when the prediction carries a non-empty answer and its cited
    sources are a superset of the example's golden ``expected_sources``; a
    prediction that raises never reaches the metric (the optimizer counts it as a
    failed bootstrap). No judge and no LM call happen here, so the compile is
    deterministic and near-free.
    """
    answer = str(getattr(prediction, "answer", "") or "").strip()
    expected = set(getattr(example, "expected_sources", None) or [])
    return bool(answer) and expected.issubset(_cited_sources(prediction))


def _program_lm(program: Any) -> Any:
    """The first language model set on ``program``'s predictors, or ``None``.

    Used as the default teacher: the program built by ``create_app`` already runs
    the locked snapshot in ``eval`` mode, so it serves as its own teacher.
    """
    predictors = getattr(program, "predictors", None)
    if predictors is None:
        return None
    for predictor in predictors():
        lm = getattr(predictor, "lm", None)
        if lm is not None:
            return lm
    return None


def compile_fewshot(
    program: Any,
    trainset: Iterable[Any],
    metric: Any,
    *,
    max_bootstrapped_demos: int = MAX_BOOTSTRAPPED_DEMOS,
    max_labeled_demos: int = MAX_LABELED_DEMOS,
) -> Any:
    """Compile ``program`` over ``trainset`` with ``dspy.BootstrapFewShot``.

    The teacher is the program's own configured LM (the locked snapshot in
    ``eval`` mode), re-established as ``teacher_settings["lm"]`` because the
    optimizer resets its teacher copy's predictor LMs whenever labeled demos are
    enabled. With the default ``max_labeled_demos=0`` a metric that bootstraps
    nothing yields a baseline-equivalent program (no demos), and only genuine
    bootstrap successes add demos. The returned student carries those demos; the
    caller sets an LM on it after load, since the compiled state is saved with no
    predictor LM.
    """
    import dspy

    teacher_lm = _program_lm(program)
    teacher_settings = {} if teacher_lm is None else {"lm": teacher_lm}
    optimizer = dspy.BootstrapFewShot(
        metric=metric,
        teacher_settings=teacher_settings,
        max_bootstrapped_demos=max_bootstrapped_demos,
        max_labeled_demos=max_labeled_demos,
    )
    return optimizer.compile(program, trainset=list(trainset))


def save_program(program: Any, path: str | Path) -> Path:
    """Persist ``program`` as a DSPy JSON state file at ``path``; return the path."""
    program_path = Path(path)
    program_path.parent.mkdir(parents=True, exist_ok=True)
    program.save(str(program_path))
    return program_path


def load_program(program: Any, path: str | Path) -> Any:
    """Load a DSPy JSON state file into ``program`` in place; return ``program``.

    The saved state includes each predictor's serialized LM state; the student a
    compile produces is saved with no predictor LM, so a loaded program comes back
    without one and the caller must set the runtime LM on it afterwards
    (``program.set_lm(lm)``).
    """
    program.load(str(Path(path)))
    return program


def program_marker(path: str | Path | None) -> str:
    """The ``program`` run marker: ``baseline``, or ``fewshot:<sha256[:12]>``.

    An unset path is the baseline program (the run is unchanged). A path that is
    set but does not name a file fails fast naming it, so a missing
    ``JANBOT_PROGRAM_PATH`` can never be recorded as a silent baseline. A present
    file is the compiled program, marked by the short sha256 of its bytes so two
    runs' programs are distinguishable in the MLflow UI.
    """
    if path is None:
        return BASELINE_MARKER
    program_path = Path(path)
    if not program_path.is_file():
        raise ValueError(
            f"compiled program not found: {program_path}; "
            "point JANBOT_PROGRAM_PATH at an existing file or unset it"
        )
    digest = hashlib.sha256(program_path.read_bytes()).hexdigest()
    return f"{PROGRAM_MARKER_PREFIX}:{digest[:_MARKER_SHA_LENGTH]}"


def _demo_count(program: Any) -> int:
    """The number of demonstrations across ``program``'s predictors."""
    predictors = getattr(program, "predictors", None)
    if predictors is None:
        return 0
    return sum(len(getattr(predictor, "demos", None) or []) for predictor in predictors())


def _program_artifacts(
    program_path: Path, dataset_path: str | Path | None
) -> tuple[Path, ...]:
    """The artifacts a compile run logs: the compiled program, then the dataset."""
    artifacts = [program_path]
    if dataset_path is not None:
        artifacts.append(Path(dataset_path))
    return tuple(artifacts)


def record_compile(
    tracking_uri: str,
    experiment: str,
    params: Mapping[str, Any],
    program_path: str | Path,
    *,
    dataset_path: str | Path | None = None,
    hyperparams: Mapping[str, Any] | None = None,
    split_manifest: Mapping[str, Any] | None = None,
) -> str:
    """Record one MLflow run holding the compile's config and its program artifact.

    The run pins the config that produced the compile plus the exact dataset
    (its sha256 as a param, the file as an artifact), then logs the compiled
    program itself, so the durable asset is retrievable from the run that made
    it. ``hyperparams`` carries the compile hyperparameters and the produced demo
    count, so a productive compile is distinguishable from a zero-bootstrap one.
    When ``split_manifest`` is given it is logged as ``split_manifest.json``
    beside the dataset artifact, pinning which dataset indices were held out.
    Returns the run id.
    """
    program_file = Path(program_path)
    logged_params = dict(params)
    if dataset_path is not None:
        logged_params["dataset_sha256"] = hashlib.sha256(
            Path(dataset_path).read_bytes()
        ).hexdigest()
    if hyperparams:
        logged_params.update(hyperparams)
    run_name = (
        "compile-"
        f"{str(logged_params.get('dataset_sha256', 'nodataset'))[:8]}"
    )

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name) as run:
        if logged_params:
            mlflow.log_params(logged_params)
        for artifact in _program_artifacts(program_file, dataset_path):
            mlflow.log_artifact(str(artifact))
        if split_manifest is not None:
            mlflow.log_dict(dict(split_manifest), SPLIT_MANIFEST_FILENAME)
        return run.info.run_id


def main(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    *,
    embedder: Any = None,
    lm_factory: Any = None,
) -> int:
    """Compile, save and record the compiled program, end to end.

    ``embedder`` and ``lm_factory`` are forwarded to ``create_app`` only when
    supplied (tests inject stubs so the CLI runs offline and keyless). The compile
    runs the builder's ``ChatProgram`` against the golden trainset (the program's
    own LM is the teacher), saves the JSON state to ``--out`` and logs it as an
    MLflow artifact with the compile's config and hyperparameters. ``--split`` is
    train-only and fails fast otherwise, so a compile can never train on the
    held-out val items; the run records ``split`` and ``trainset_size``.
    """
    from janbot.api.main import create_app
    from janbot.eval.__main__ import _app_kwargs, run_params

    parser = argparse.ArgumentParser(prog="python -m janbot.eval.optimize")
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET),
        help=f"golden dataset path (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"compiled program output path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--experiment",
        default=DEFAULT_EXPERIMENT,
        help=f"MLflow experiment name (default: {DEFAULT_EXPERIMENT})",
    )
    parser.add_argument(
        "--split",
        default="train",
        help="dataset split to compile over; only 'train' is accepted (default: train)",
    )
    args = parser.parse_args(argv)

    if args.split != "train":
        parser.error(
            f"compile is train-only; got --split {args.split!r}. "
            "Compiling over val (or all) would train on the held-out set."
        )

    source = os.environ if env is None else env
    tracking_uri = source.get(TRACKING_URI_ENV) or DEFAULT_TRACKING_URI

    config = load_config(source)
    app = create_app(env=source, **_app_kwargs(embedder, lm_factory))
    program = app.state.program

    all_items = load_golden_dataset(args.dataset)
    items = [item for item in all_items if item.split == args.split]
    trainset = trainset_from(items)

    compiled = compile_fewshot(program, trainset, compile_metric)
    out_path = save_program(compiled, args.out)

    params = run_params(config)
    params["program"] = program_marker(out_path)
    params["split"] = args.split
    params["trainset_size"] = len(trainset)
    run_id = record_compile(
        tracking_uri,
        args.experiment,
        params,
        out_path,
        dataset_path=args.dataset,
        hyperparams={
            "max_bootstrapped_demos": MAX_BOOTSTRAPPED_DEMOS,
            "max_labeled_demos": MAX_LABELED_DEMOS,
            "demos": _demo_count(compiled),
        },
        split_manifest=split_manifest(all_items),
    )

    print(f"MLflow tracking URI: {tracking_uri}")
    print(f"MLflow run: {run_id}")
    print(f"program: {out_path}")
    print(f"program marker: {params['program']}")
    print(f"demos: {_demo_count(compiled)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
