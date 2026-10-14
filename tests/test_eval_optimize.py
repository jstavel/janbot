"""Unit tests for BootstrapFewShot compilation and the pinned compiled program.

They prove the golden trainset mapping, the deterministic compile metric, a
keyless ``DummyLM``-driven compile that bootstraps demonstrations, the
save/load round trip and the "no demos" path, and that the eval marks a run with
a ``program`` parameter while ``create_app`` loads a pinned compiled program.
Every test is offline and keyless: a stub embedder and a ``DummyLM`` factory.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import yaml
import pytest
from dspy import Example
from dspy.utils import DummyLM
from mlflow.tracking import MlflowClient

from janbot.api.contract import ChatResponse, Citation
from janbot.api.main import create_app
from janbot.eval import __main__ as eval_cli
from janbot.eval.dataset import GoldenItem
from janbot.eval.optimize import (
    _demo_count,
    compile_fewshot,
    compile_metric,
    load_program,
    program_marker,
    save_program,
    trainset_from,
)
from janbot.ingest import index_corpus
from janbot.pipeline.chat import ChatProgram, corpus_relative
from janbot.store import VectorStore

Embedder = Callable[[list[str]], list[list[float]]]


def _tracking_uri(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'mlflow.db'}"


def _dummy_lm(citations: list[str] | None = None, *, count: int = 24) -> DummyLM:
    answer = {"answer": "Grounded.", "citations": list(citations or ["profile.org"])}
    return DummyLM([dict(answer) for _ in range(count)])


class StubLMFactory:
    """Recording LM factory yielding a canned-answer ``DummyLM`` (no real model)."""

    def __init__(self, citations: list[str] | None = None) -> None:
        self.citations = list(citations or ["profile.org"])

    def __call__(self, **kwargs: object) -> DummyLM:
        return _dummy_lm(self.citations)


def _corpus(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> tuple[Path, Path]:
    corpus = tmp_path / "public_profile_org"
    write_org(
        corpus / "profile.org",
        heading="About",
        body="Search infrastructure engineer.",
    )
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)
    return corpus, index_path


def _program(
    corpus: Path, index_path: Path, embedder: Embedder, lm: DummyLM
) -> ChatProgram:
    store = VectorStore(index_path, embedder, scope=corpus)
    program = ChatProgram(store, top_k=4, rewriter=corpus_relative(corpus))
    program.set_lm(lm)
    return program


def _item() -> GoldenItem:
    return GoldenItem(
        question="What search infrastructure have you built?",
        expected_answer="Search infrastructure.",
        expected_sources=["profile.org"],
    )


def _as_dicts(demos: list[object]) -> list[object]:
    return [
        demo.toDict() if hasattr(demo, "toDict") else demo  # type: ignore[attr-defined]
        for demo in demos
    ]


def _write_dataset(tmp_path: Path) -> Path:
    dataset = tmp_path / "dataset.yaml"
    dataset.write_text(
        yaml.safe_dump(
            [
                {
                    "question": _item().question,
                    "expected_answer": _item().expected_answer,
                    "expected_sources": _item().expected_sources,
                    "split": "train",
                }
            ]
        ),
        encoding="utf-8",
    )
    return dataset


def _write_split_dataset(tmp_path: Path) -> Path:
    dataset = tmp_path / "split_dataset.yaml"
    dataset.write_text(
        yaml.safe_dump(
            [
                {
                    "question": "train question",
                    "expected_answer": "Search infrastructure.",
                    "expected_sources": ["profile.org"],
                    "split": "train",
                },
                {
                    "question": "val question",
                    "expected_answer": "Search infrastructure.",
                    "expected_sources": ["profile.org"],
                    "split": "val",
                },
            ]
        ),
        encoding="utf-8",
    )
    return dataset


def test_trainset_from_maps_items_to_question_inputs() -> None:
    trainset = trainset_from([_item()])

    assert len(trainset) == 1
    example = trainset[0]
    assert example.question == _item().question
    assert example.expected_answer == _item().expected_answer
    assert example.expected_sources == ["profile.org"]
    assert set(example.inputs().keys()) == {"question"}


def test_compile_metric_requires_an_answer_and_every_source() -> None:
    example = Example(question="q", expected_sources=["a.org", "b.org"])

    complete = ChatResponse(
        answer="ok",
        citations=[Citation(source="a.org"), Citation(source="b.org")],
    )
    partial = ChatResponse(answer="ok", citations=[Citation(source="a.org")])
    empty = ChatResponse(
        answer="   ",
        citations=[Citation(source="a.org"), Citation(source="b.org")],
    )

    assert compile_metric(example, complete) is True
    assert compile_metric(example, partial) is False
    assert compile_metric(example, empty) is False


def test_compile_metric_tolerates_bare_string_citations() -> None:
    example = Example(question="q", expected_sources=["a.org"])

    assert compile_metric(example, SimpleNamespace(answer="ok", citations=[])) is False
    assert compile_metric(example, SimpleNamespace(answer="ok", citations=["a.org"])) is True


def test_compile_fewshot_bootstraps_with_a_stub_lm_and_round_trips(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    corpus, index_path = _corpus(tmp_path, embedder, write_org)
    teacher = _dummy_lm()
    program = _program(corpus, index_path, embedder, teacher)

    compiled = compile_fewshot(
        program,
        trainset_from([_item()]),
        compile_metric,
    )

    assert _demo_count(compiled) >= 1
    out = tmp_path / "compiled.json"
    assert save_program(compiled, out) == out
    assert out.is_file()
    assert program_marker(out).startswith("fewshot:")

    fresh = _program(corpus, index_path, embedder, _dummy_lm())
    load_program(fresh, out)

    assert fresh._answer.demos == _as_dicts(compiled._answer.demos)


def test_compile_fewshot_without_demos_still_produces_a_program(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    corpus, index_path = _corpus(tmp_path, embedder, write_org)
    teacher = _dummy_lm()
    program = _program(corpus, index_path, embedder, teacher)

    def never(example: object, prediction: object, trace: object = None) -> bool:
        return False

    compiled = compile_fewshot(
        program,
        trainset_from([_item()]),
        never,
    )

    assert _demo_count(compiled) == 0
    out = tmp_path / "baseline.json"
    save_program(compiled, out)
    assert out.is_file()


def test_program_marker_is_baseline_only_when_unset(tmp_path: Path) -> None:
    assert program_marker(None) == "baseline"

    with pytest.raises(ValueError) as excinfo:
        program_marker(tmp_path / "absent.json")

    assert "absent.json" in str(excinfo.value)


def test_create_app_rejects_a_missing_program_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as excinfo:
        create_app(env={"JANBOT_PROGRAM_PATH": str(tmp_path / "absent.json")})

    assert "absent.json" in str(excinfo.value)


def test_eval_marks_a_run_with_the_program_marker(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    corpus, index_path = _corpus(tmp_path, embedder, write_org)
    teacher = _dummy_lm()
    compiled = compile_fewshot(
        _program(corpus, index_path, embedder, teacher),
        trainset_from([_item()]),
        compile_metric,
    )
    program_file = save_program(compiled, tmp_path / "compiled.json")
    dataset = _write_dataset(tmp_path)

    uri = _tracking_uri(tmp_path)
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "JANBOT_PROGRAM_PATH": str(program_file),
        "MLFLOW_TRACKING_URI": uri,
    }

    code = eval_cli.main(
        ["--dataset", str(dataset)], env=env, embedder=embedder, lm_factory=StubLMFactory()
    )

    assert code == 0
    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    run = client.search_runs([experiment.experiment_id])[0]
    assert run.data.params["program"] == program_marker(program_file)


def test_eval_without_a_program_path_marks_the_baseline(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    corpus, index_path = _corpus(tmp_path, embedder, write_org)
    dataset = _write_dataset(tmp_path)

    uri = _tracking_uri(tmp_path)
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "MLFLOW_TRACKING_URI": uri,
    }

    code = eval_cli.main(
        ["--dataset", str(dataset)], env=env, embedder=embedder, lm_factory=StubLMFactory()
    )

    assert code == 0
    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    run = client.search_runs([experiment.experiment_id])[0]
    assert run.data.params["program"] == "baseline"


def test_create_app_loads_the_pinned_program(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    corpus, index_path = _corpus(tmp_path, embedder, write_org)
    teacher = _dummy_lm()
    compiled = compile_fewshot(
        _program(corpus, index_path, embedder, teacher),
        trainset_from([_item()]),
        compile_metric,
    )
    program_file = save_program(compiled, tmp_path / "compiled.json")

    app = create_app(
        env={
            "JANBOT_CORPUS_PATH": str(corpus),
            "JANBOT_INDEX_PATH": str(index_path),
            "JANBOT_PROGRAM_PATH": str(program_file),
        },
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )

    assert _as_dicts(app.state.program._answer.demos) == _as_dicts(
        compiled._answer.demos
    )


def test_optimize_cli_compiles_saves_and_logs_an_artifact(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    corpus, index_path = _corpus(tmp_path, embedder, write_org)
    dataset = _write_dataset(tmp_path)
    out = tmp_path / "compiled.json"
    uri = _tracking_uri(tmp_path)
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "MLFLOW_TRACKING_URI": uri,
    }

    from janbot.eval.optimize import main as optimize_main

    code = optimize_main(
        ["--dataset", str(dataset), "--out", str(out)],
        env=env,
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )

    assert code == 0
    assert out.is_file()
    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    run = client.search_runs([experiment.experiment_id])[0]
    assert run.data.params["dataset_sha256"] == hashlib.sha256(
        dataset.read_bytes()
    ).hexdigest()
    assert run.data.params["program"] == program_marker(out)
    assert run.data.params["split"] == "train"
    assert run.data.params["trainset_size"] == "1"
    assert run.data.params["max_bootstrapped_demos"] == "4"
    assert run.data.params["max_labeled_demos"] == "0"
    assert run.data.params["demos"] == "1"
    artifacts = {a.path for a in client.list_artifacts(run.info.run_id)}
    assert out.name in artifacts
    assert dataset.name in artifacts
    assert "split_manifest.json" in artifacts
    manifest_path = client.download_artifacts(run.info.run_id, "split_manifest.json")
    assert json.loads(Path(manifest_path).read_text(encoding="utf-8")) == {"train": [0]}


@pytest.mark.parametrize("split", ["val", "all"])
def test_optimize_cli_refuses_a_non_train_split(
    tmp_path: Path,
    split: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from janbot.eval.optimize import main as optimize_main

    dataset = _write_dataset(tmp_path)

    with pytest.raises(SystemExit):
        optimize_main(["--dataset", str(dataset), "--split", split], env={})

    assert "train" in capsys.readouterr().err


def test_eval_scores_only_val_and_records_the_split_manifest(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus, index_path = _corpus(tmp_path, embedder, write_org)
    dataset = _write_split_dataset(tmp_path)
    uri = _tracking_uri(tmp_path)
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "MLFLOW_TRACKING_URI": uri,
    }

    code = eval_cli.main(
        ["--dataset", str(dataset), "--split", "val"],
        env=env,
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "items: 1" in out

    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    run = client.search_runs([experiment.experiment_id])[0]
    assert run.data.params["split"] == "val"
    assert any(
        artifact.path == "split_manifest.json"
        for artifact in client.list_artifacts(run.info.run_id)
    )
    manifest_path = client.download_artifacts(run.info.run_id, "split_manifest.json")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert manifest == {"train": [0], "val": [1]}


def test_eval_cli_fails_when_the_split_selects_no_items(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path)

    assert eval_cli.main(["--dataset", str(dataset), "--split", "val"], env={}) == 2


def test_api_import_pulls_neither_mlflow_nor_the_eval_layer() -> None:
    import subprocess
    import sys

    code = (
        "import sys; import janbot.api.main; "
        "assert 'mlflow' not in sys.modules, 'mlflow imported by janbot.api.main'; "
        "assert 'janbot.eval' not in sys.modules, 'janbot.eval imported by janbot.api.main'"
    )

    subprocess.run([sys.executable, "-c", code], check=True)
