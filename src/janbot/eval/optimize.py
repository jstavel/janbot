"""Compile the ``/chat`` program with BootstrapFewShot (epic-evaluation, entry 8).

Entry 7 recorded the baseline (retrieval 0.78, citation 0.77, faithfulness 0.66)
and ruled ``BootstrapFewShot`` *needed*; this module is the stage that produces
the durable asset: a **compiled program** persisted as a DSPy JSON state file and
logged as an MLflow artifact. The compiled program is pinned by configuration
(``JANBOT_PROGRAM_PATH``), so production and eval load it without recompiling.

The compile objective is multi-objective (epic-evaluation, entry 8 Goodhart
trade): ``score = w_c·cited_ok + w_f·faithful`` (default ``w_c = w_f = 0.5``),
where ``cited_ok`` is the old citation atom (non-empty answer citing every golden
source) and ``faithful`` is the eval judge's verdict. A demo is accepted only
when ``cited_ok AND faithful`` — a citation-only win is never bootstrapped — and
the demo path short-circuits to ``False`` **without a judge call** when
``cited_ok`` is false, so a non-citing candidate stays near-free. The scalar path
(``trace is None``, the future MIPROv2 ranking signal) stays continuous and is
deferred to entry 5.9. The judge is the eval judge, injected (tests stub it); a
judge error fails closed (the demo is rejected) and is recorded. Each item's
``(cited_ok, faithful)`` pair is logged as an MLflow artifact beside the compiled
program for a future Pareto/GEPA objective. The teacher is the locked snapshot
(the LM the student already runs under in ``eval`` mode), passed through
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
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import mlflow

from janbot.config import PROJECT_ROOT, load_config
from janbot.eval.dataset import GoldenItem, load_golden_dataset, split_manifest
from janbot.eval.judge import FAITHFUL, Judge
from janbot.eval.runner import SPLIT_MANIFEST_FILENAME

DEFAULT_DATASET = PROJECT_ROOT / "eval" / "golden_dataset.yaml"
DEFAULT_OUT = PROJECT_ROOT / "eval" / "compiled_fewshot.json"
DEFAULT_EXPERIMENT = "janbot-eval"
TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"

MAX_BOOTSTRAPPED_DEMOS = 4
MAX_LABELED_DEMOS = 0
DEFAULT_W_C = 0.5
DEFAULT_W_F = 0.5
PROGRAM_MARKER_PREFIX = "fewshot"
BASELINE_MARKER = "baseline"
PAIRS_ARTIFACT_FILENAME = "compile_pairs.json"
_MARKER_SHA_LENGTH = 12


def trainset_from(
    items: Iterable[GoldenItem], *, indices: Iterable[int] | None = None
) -> list[Any]:
    """Build the DSPy trainset from golden items.

    Each item becomes a :class:`dspy.Example` carrying the question, the golden
    answer and the golden sources; only ``question`` is an input (the pipeline
    retrieves its own context), so the metric compares the program's answer and
    citations against the remaining fields. ``index`` is a non-input field the
    compile metric reads to key its recorded ``(cited_ok, faithful)`` pairs.

    ``indices`` supplies the dataset index per item (the caller passes the
    full-dataset positions of the split, so the pairs stay keyed on the stable
    dataset index); when omitted the item's position in ``items`` is used.
    """
    import dspy

    item_list = list(items)
    if indices is None:
        index_list = list(range(len(item_list)))
    else:
        index_list = list(indices)
        if len(index_list) != len(item_list):
            raise ValueError(
                f"indices has {len(index_list)} entries but there are "
                f"{len(item_list)} items"
            )
    return [
        dspy.Example(
            index=index,
            question=item.question,
            expected_answer=item.expected_answer,
            expected_sources=list(item.expected_sources),
        ).with_inputs("question")
        for index, item in zip(index_list, item_list)
    ]


def _cited_sources(prediction: Any) -> set[str]:
    """The sources a prediction cites, tolerant of ``Citation`` objects or bare strings."""
    citations = getattr(prediction, "citations", None) or []
    sources: set[str] = set()
    for citation in citations:
        sources.add(str(getattr(citation, "source", citation)))
    return sources


def _cited_ok(example: Any, prediction: Any) -> bool:
    """Whether the prediction answered and cites every golden expected source.

    The citation atom, aligned with the failure-inclusive eval
    ``citation_correctness`` contract: that metric's fixed population includes every
    in-corpus item with expected sources, and a non-answer is a failure. A declined
    or empty response therefore returns ``False`` here — the same verdict the
    metric gives it. A citation win is a non-empty answered response whose cited
    sources are a superset of the example's golden ``expected_sources``
    (containment, never exact-set equality). Tolerant of ``Citation`` objects or
    bare strings.
    """
    if getattr(prediction, "status", None) == "insufficient":
        return False
    answer = str(getattr(prediction, "answer", "") or "").strip()
    expected = set(getattr(example, "expected_sources", None) or [])
    return bool(answer) and expected.issubset(_cited_sources(prediction))


def _judge_faithful(
    judge: Judge | None, example: Any, prediction: Any
) -> tuple[bool | None, bool, str | None]:
    """Return ``(faithful, judged, failure)`` for one prediction's judge call.

    ``judged`` is ``True`` only when a verdict was obtained. A missing judge or a
    judge that raises fails closed: faithful is ``False``, judged is ``False`` and
    a readable failure line is returned — the verdict is unknowable, so the item
    is never a faithful demo. ``faithful`` is ``None`` only for the demo path's
    designed short-circuit (no judge call at all).
    """
    question = str(getattr(example, "question", "") or "")
    if judge is None:
        return False, False, f"{question} — no judge configured"
    context = str(getattr(example, "expected_answer", "") or "")
    answer = str(getattr(prediction, "answer", "") or "")
    try:
        verdict = judge(context, answer)
    except Exception as exc:  # noqa: BLE001 - fail closed on any judge error
        return False, False, f"{question} — judge failed: {type(exc).__name__}: {exc}"
    return verdict.label == FAITHFUL, True, None


def make_compile_metric(
    judge: Judge | None,
    *,
    w_c: float = DEFAULT_W_C,
    w_f: float = DEFAULT_W_F,
) -> Any:
    """Build the multi-objective BootstrapFewShot metric over ``judge``.

    The metric ``score = w_c·cited_ok + w_f·faithful``. On the demo path
    (``trace is not None``) it is the acceptance rule ``cited_ok AND faithful``:
    a candidate with no citation short-circuits to ``False`` **without a judge
    call**, and a candidate that cites but is judged not faithful is rejected, so
    a citation-only win is never bootstrapped. On the scalar path (``trace is
    None``, the deferred MIPROv2 ranking signal) it returns the continuous score
    and never short-circuits — with ``cited_ok`` false the faithful term is only
    knowable from the judge, so the call always happens.

    The judge is injected (tests stub it); a judge error fails closed. The
    returned callable carries the recording attributes ``pairs`` (one
    ``{index, question, cited_ok, faithful, judged}`` per item, where ``judged``
    is whether a verdict was obtained and ``faithful`` is ``None`` **only** for
    the demo path's designed short-circuit — a no-judge or judge-error item is
    ``judged=False, faithful=False``, never ``None``), ``failures`` (judge
    no-judge/error lines), and the declared ``w_c``/``w_f``.
    """
    pairs: list[dict[str, Any]] = []
    failures: list[str] = []
    recorded: dict[Any, dict[str, Any]] = {}

    def _record(
        index: Any,
        question: str,
        cited_ok: bool,
        faithful: bool | None,
        judged: bool,
    ) -> None:
        if index is not None and index in recorded:
            entry = recorded[index]
            entry["cited_ok"] = cited_ok
            entry["faithful"] = faithful
            entry["judged"] = judged
            return
        entry = {
            "index": index,
            "question": question,
            "cited_ok": cited_ok,
            "faithful": faithful,
            "judged": judged,
        }
        if index is not None:
            recorded[index] = entry
        pairs.append(entry)

    def compile_metric(example: Any, prediction: Any, trace: Any = None) -> Any:
        index = getattr(example, "index", None)
        question = str(getattr(example, "question", "") or "")
        cited_ok = _cited_ok(example, prediction)

        if trace is not None:
            if not cited_ok:
                _record(index, question, False, None, False)
                return False
            faithful, judged, failure = _judge_faithful(judge, example, prediction)
            if failure is not None:
                failures.append(failure)
            _record(index, question, True, faithful, judged)
            return bool(cited_ok and faithful)

        faithful, judged, failure = _judge_faithful(judge, example, prediction)
        if failure is not None:
            failures.append(failure)
        _record(index, question, cited_ok, faithful, judged)
        return w_c * (1.0 if cited_ok else 0.0) + w_f * (1.0 if faithful else 0.0)

    setattr(compile_metric, "pairs", pairs)
    setattr(compile_metric, "failures", failures)
    setattr(compile_metric, "w_c", w_c)
    setattr(compile_metric, "w_f", w_f)
    return compile_metric


def _disable_relevance_gate(program: Any) -> None:
    """Disable ``program``'s runtime low-relevance gate for a compile.

    The relevance gate is a runtime ``/chat`` behaviour: it declines a question
    whose best retrieved chunk is below the threshold. A compile must attempt
    every train item — that attempt is BootstrapFewShot's learning signal — so a
    gate left armed would starve the optimizer of demonstrations for any
    low-similarity item. The gate is set inert (``0.0``) for the compile and the
    full pairs pass; a served program loads its own configured threshold, so the
    shipped default is unchanged for ``/chat``.
    """
    if getattr(program, "_relevance_threshold", 0.0) != 0.0:
        program._relevance_threshold = 0.0


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


def record_train_pairs(
    program: Any, trainset: Iterable[Any], metric: Any
) -> None:
    """Evaluate every train item once so ``metric.pairs`` covers the whole split.

    ``BootstrapFewShot`` stops as soon as it has ``max_bootstrapped_demos``
    successes, so its own metric calls cover only a prefix of the trainset. This
    full pass calls the same metric (demo path, ``trace`` set) for every item, so
    the logged pairs are the per-item map the plan requires. ``program`` must have
    a runtime LM set (the compiled student carries none until the caller sets one).
    An item the program fails to answer records as an uncited short-circuit rather
    than aborting.
    """
    for example in trainset:
        try:
            prediction = program(**example.inputs())
        except Exception:  # noqa: BLE001 - an unanswered item is still recorded
            prediction = None
        metric(example, prediction, [])


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
    pairs: Iterable[Mapping[str, Any]] | None = None,
) -> str:
    """Record one MLflow run holding the compile's config and its program artifact.

    The run pins the config that produced the compile plus the exact dataset
    (its sha256 as a param, the file as an artifact), then logs the compiled
    program itself, so the durable asset is retrievable from the run that made
    it. ``hyperparams`` carries the compile hyperparameters (weights, judge model
    id) and the produced demo count, so a productive compile is distinguishable
    from a zero-bootstrap one. ``pairs`` is the per-item ``{index, question,
    cited_ok, faithful, judged}`` list, logged as ``compile_pairs.json`` beside
    the program for a future Pareto/GEPA objective.
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
        if pairs is not None:
            mlflow.log_text(
                json.dumps(list(pairs), indent=2), PAIRS_ARTIFACT_FILENAME
            )
        return run.info.run_id


def main(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    *,
    embedder: Any = None,
    lm_factory: Any = None,
    judge: Judge | None = None,
) -> int:
    """Compile, save and record the compiled program, end to end.

    ``embedder`` and ``lm_factory`` are forwarded to ``create_app`` only when
    supplied (tests inject stubs so the CLI runs offline and keyless). ``judge``
    is the LLM-as-a-judge seam: when omitted a real judge is built from
    configuration (``JANBOT_JUDGE_MODEL``) only if ``OPENROUTER_API_KEY`` is
    present, exactly as the eval CLI does. The multi-objective compile needs the
    faithfulness term, so a compile with no judge fails fast rather than
    bootstrapping nothing. The compile runs the builder's ``ChatProgram`` against
    the golden trainset (the program's own LM is the teacher), makes a full pass
    over the trainset so the per-item pairs cover every train item, saves the
    JSON state to ``--out`` and logs it as an MLflow artifact with the compile's
    config, hyperparameters (weights, judge model id, demo count) and the
    per-item ``compile_pairs.json``. The relevance gate is a runtime ``/chat``
    behaviour, so it is disabled for the compile and the full pairs pass: the
    optimizer must attempt every train item (that attempt is its learning
    signal), while the shipped default still gates serving. ``--split`` is
    train-only and fails fast
    otherwise, so a compile can never train on the held-out val items; the run
    records ``split`` and ``trainset_size``.
    """
    from janbot.api.main import create_app
    from janbot.eval.__main__ import (
        OPENROUTER_API_KEY_ENV,
        _app_kwargs,
        _resolve_judge,
        run_params,
    )

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
    api_key = (source.get(OPENROUTER_API_KEY_ENV) or "").strip() or None
    app = create_app(env=source, **_app_kwargs(embedder, lm_factory))
    program = app.state.program
    judge = _resolve_judge(config, api_key, lm_factory, judge)
    if judge is None:
        parser.error(
            "the multi-objective compile needs a judge for the faithfulness "
            "term: set OPENROUTER_API_KEY (and JANBOT_JUDGE_MODEL), or inject "
            "a judge"
        )

    all_items = load_golden_dataset(args.dataset)
    indexed = [
        (index, item)
        for index, item in enumerate(all_items)
        if item.split == args.split
    ]
    trainset = trainset_from(
        [item for _, item in indexed], indices=[index for index, _ in indexed]
    )

    metric = make_compile_metric(judge)
    _disable_relevance_gate(program)
    compiled = compile_fewshot(program, trainset, metric)
    out_path = save_program(compiled, args.out)

    runtime_lm = _program_lm(program)
    if runtime_lm is not None:
        compiled.set_lm(runtime_lm)
    _disable_relevance_gate(compiled)
    record_train_pairs(compiled, trainset, metric)

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
            "w_c": metric.w_c,
            "w_f": metric.w_f,
            "judge_model_id": config.judge_model,
            "demos": _demo_count(compiled),
        },
        split_manifest=split_manifest(all_items),
        pairs=metric.pairs,
    )

    print(f"MLflow tracking URI: {tracking_uri}")
    print(f"MLflow run: {run_id}")
    print(f"program: {out_path}")
    print(f"program marker: {params['program']}")
    print(f"judge model: {config.judge_model}")
    print(f"objective: w_c={metric.w_c} w_f={metric.w_f}")
    print(f"demos: {_demo_count(compiled)}")
    for failure in metric.failures:
        print(f"judge: {failure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
