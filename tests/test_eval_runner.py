"""Unit tests for the eval runner and CLI.

They prove the runner writes exactly one MLflow run (params + the stub metric)
against a ``tmp_path`` store, records per-item failures without aborting, fails
naming an unreachable tracking URI, and that the CLI reads the dataset and
reports the tracking URI on a keyless eval configuration. A stub embedder and a
``DummyLM`` factory keep the whole suite offline and keyless.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from mlflow.tracking import MlflowClient

from janbot.ingest import index_corpus

from dspy.utils import DummyLM

from janbot.api.contract import INSUFFICIENT_ANSWER, ChatResponse, Citation
from janbot.eval import __main__ as eval_cli
from janbot.eval.dataset import GoldenItem
from janbot.eval.judge import FAITHFUL, Verdict
from janbot.eval.runner import run_eval

Embedder = Callable[[list[str]], list[list[float]]]


def _tracking_uri(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'mlflow.db'}"


def _items() -> list[GoldenItem]:
    return [
        GoldenItem(question="q1", expected_answer="a1", expected_sources=["profile.org"]),
        GoldenItem(question="q2", expected_answer="a2", expected_sources=["projects.org"]),
    ]


def _stub_program(answer: str = "Grounded.", source: str = "profile.org") -> Callable[..., ChatResponse]:
    def program(*, question: str) -> ChatResponse:
        return ChatResponse(answer=answer, citations=[Citation(source=source)])

    return program


class StubLMFactory:
    """Recording LM factory yielding a canned-answer ``DummyLM`` (no real model)."""

    def __init__(self, citations: list[str] | None = None) -> None:
        self.citations = list(citations or ["profile.org"])

    def __call__(self, **kwargs: object) -> DummyLM:
        answer = {"answer": "Grounded.", "citations": list(self.citations)}
        return DummyLM([dict(answer) for _ in range(16)])


class _RetrievingProgram:
    """Program exposing the additive ``last_retrieved_sources`` seam the runner reads."""

    def __init__(self, sources: list[str]) -> None:
        self.last_retrieved_sources = list(sources)

    def __call__(self, *, question: str) -> ChatResponse:
        return ChatResponse(answer="Grounded.", citations=[Citation(source="profile.org")])


def test_run_eval_captures_retrieved_sources_and_records_accuracy(tmp_path: Path) -> None:
    uri = _tracking_uri(tmp_path)
    program = _RetrievingProgram(["profile.org", "projects.org"])

    result = run_eval(_items(), program, tracking_uri=uri, experiment="janbot-eval")

    assert result.outcomes[0].retrieved_sources == ["profile.org", "projects.org"]
    assert result.metrics["retrieval_accuracy"] == 1.0
    assert result.retrieval_misses == []


def test_run_eval_reports_a_retrieval_miss_per_item(tmp_path: Path) -> None:
    uri = _tracking_uri(tmp_path)
    program = _RetrievingProgram(["profile.org"])

    result = run_eval(_items(), program, tracking_uri=uri, experiment="janbot-eval")

    assert result.metrics["retrieval_accuracy"] == 0.5
    assert len(result.retrieval_misses) == 1
    assert "missing retrieved source(s): projects.org" in result.retrieval_misses[0]


def test_run_eval_reports_a_citation_miss_per_item(tmp_path: Path) -> None:
    uri = _tracking_uri(tmp_path)

    result = run_eval(
        _items(), _stub_program(source="profile.org"), tracking_uri=uri, experiment="janbot-eval"
    )

    assert result.metrics["citation_correctness"] == 0.5
    assert len(result.citation_misses) == 1
    assert "missing cited source(s): projects.org" in result.citation_misses[0]


def test_run_eval_citation_containment_ignores_an_extra_source(tmp_path: Path) -> None:
    uri = _tracking_uri(tmp_path)

    def program(*, question: str) -> ChatResponse:
        expected = "profile.org" if question == "q1" else "projects.org"
        return ChatResponse(
            answer="Grounded.",
            citations=[Citation(source=expected), Citation(source="other.org")],
        )

    result = run_eval(_items(), program, tracking_uri=uri, experiment="janbot-eval")

    assert result.metrics["citation_correctness"] == 1.0
    assert result.citation_misses == []
    assert result.metrics["citation_precision"] == 0.5


def test_run_eval_records_one_run_with_params_and_stub_metric(tmp_path: Path) -> None:
    uri = _tracking_uri(tmp_path)
    params = {
        "model_mode": "eval",
        "model_snapshot": "openai/gpt-4o-mini-2024-07-18",
        "temperature": 0.0,
        "seed": 0,
    }

    result = run_eval(
        _items(), _stub_program(), tracking_uri=uri, experiment="janbot-eval", params=params
    )

    assert result.metrics == {
        "answer_coverage": 1.0,
        "public_references": 1.0,
        "retrieval_accuracy": 0.0,
        "retrieval_mrr": 0.0,
        "citation_correctness": 0.5,
        "citation_precision": 0.5,
        "faithfulness": 0.0,
        "refusal_pass_rate": 0.0,
        "spurious_refusal_rate": 0.0,
    }
    assert result.counts == {
        "answer_coverage__n": 2,
        "public_references__n": 2,
        "retrieval_accuracy__n": 0,
        "retrieval_mrr__n": 0,
        "citation_correctness__n": 2,
        "citation_precision__n": 2,
        "faithfulness__n": 0,
        "refusal_pass_rate__n": 0,
        "spurious_refusal_rate__n": 2,
    }
    assert result.run_id
    assert result.reference_failures == []
    assert result.retrieval_misses == []
    assert len(result.citation_misses) == 1
    assert "missing cited source(s): projects.org" in result.citation_misses[0]

    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    assert experiment is not None
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 1
    run = runs[0]
    assert run.info.run_id == result.run_id
    assert run.data.params == {
        "model_mode": "eval",
        "model_snapshot": "openai/gpt-4o-mini-2024-07-18",
        "temperature": "0.0",
        "seed": "0",
    }
    assert run.data.metrics == {
        "answer_coverage": 1.0,
        "answer_coverage__n": 2.0,
        "public_references": 1.0,
        "public_references__n": 2.0,
        "retrieval_accuracy": 0.0,
        "retrieval_accuracy__n": 0.0,
        "retrieval_mrr": 0.0,
        "retrieval_mrr__n": 0.0,
        "citation_correctness": 0.5,
        "citation_correctness__n": 2.0,
        "citation_precision": 0.5,
        "citation_precision__n": 2.0,
        "faithfulness": 0.0,
        "faithfulness__n": 0.0,
        "refusal_pass_rate": 0.0,
        "refusal_pass_rate__n": 0.0,
        "spurious_refusal_rate": 0.0,
        "spurious_refusal_rate__n": 2.0,
    }


def test_run_eval_records_per_item_failure_without_aborting(tmp_path: Path) -> None:
    uri = _tracking_uri(tmp_path)

    def program(*, question: str) -> ChatResponse:
        if question == "q2":
            raise ValueError("retrieval returned 0 chunks")
        return ChatResponse(answer="ok", citations=[Citation(source="profile.org")])

    result = run_eval(_items(), program, tracking_uri=uri, experiment="janbot-eval")

    assert result.metrics["answer_coverage"] == 0.5
    assert result.outcomes[0].error is None
    assert result.outcomes[1].error is not None
    assert "ValueError" in result.outcomes[1].error
    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    assert len(client.search_runs([experiment.experiment_id])) == 1


def test_run_eval_maps_a_decline_to_the_contract_insufficient_response(
    tmp_path: Path,
) -> None:
    from janbot.pipeline.chat import UncitedAnswer

    uri = _tracking_uri(tmp_path)

    def program(*, question: str) -> ChatResponse:
        raise UncitedAnswer("the model claimed no sources")

    result = run_eval(_items(), program, tracking_uri=uri, experiment="janbot-eval")

    outcome = result.outcomes[0]
    assert outcome.response is not None
    assert outcome.response.status == "insufficient"
    assert outcome.response.answer == INSUFFICIENT_ANSWER
    assert outcome.response.citations == []
    assert outcome.error is None
    assert outcome.judge_verdict is None
    assert all(o.response is not None for o in result.outcomes)


def test_run_eval_maps_an_empty_retrieval_to_a_decline(tmp_path: Path) -> None:
    from janbot.pipeline.chat import EmptyRetrieval

    uri = _tracking_uri(tmp_path)

    def program(*, question: str) -> ChatResponse:
        raise EmptyRetrieval("retrieval returned 0 chunks")

    result = run_eval(_items(), program, tracking_uri=uri, experiment="janbot-eval")

    for outcome in result.outcomes:
        assert outcome.response is not None
        assert outcome.response.status == "insufficient"
        assert outcome.error is None


def test_run_eval_maps_a_low_relevance_gate_to_a_decline(tmp_path: Path) -> None:
    from janbot.pipeline.chat import LowRelevance

    uri = _tracking_uri(tmp_path)

    def program(*, question: str) -> ChatResponse:
        raise LowRelevance("the best retrieved chunk is below the relevance threshold")

    result = run_eval(_items(), program, tracking_uri=uri, experiment="janbot-eval")

    for outcome in result.outcomes:
        assert outcome.response is not None
        assert outcome.response.status == "insufficient"
        assert outcome.response.answer == INSUFFICIENT_ANSWER
        assert outcome.response.citations == []
        assert outcome.error is None


def test_run_eval_keeps_a_fabricated_citation_as_an_error(tmp_path: Path) -> None:
    from janbot.pipeline.chat import FabricatedCitation

    uri = _tracking_uri(tmp_path)

    def program(*, question: str) -> ChatResponse:
        raise FabricatedCitation("source outside the retrieved set")

    result = run_eval(_items(), program, tracking_uri=uri, experiment="janbot-eval")

    outcome = result.outcomes[0]
    assert outcome.response is None
    assert outcome.error is not None
    assert "FabricatedCitation" in outcome.error


def test_run_eval_does_not_judge_a_declined_item(tmp_path: Path) -> None:
    from janbot.pipeline.chat import UncitedAnswer

    uri = _tracking_uri(tmp_path)
    judged: list[str] = []

    class RecordingJudge:
        def __call__(self, expected: str, actual: str) -> object:
            judged.append(actual)
            raise AssertionError("a decline must not be judged")

    def program(*, question: str) -> ChatResponse:
        raise UncitedAnswer("the model claimed no sources")

    result = run_eval(
        _items(),
        program,
        tracking_uri=uri,
        experiment="janbot-eval",
        judge=RecordingJudge(),  # type: ignore[arg-type]
    )

    assert judged == []
    assert result.judge_failures == []
    assert all(o.judge_verdict is None for o in result.outcomes)


def _refusal_items() -> list[GoldenItem]:
    return [
        GoldenItem(
            question="What is your salary expectation?",
            expected_answer="",
            expected_sources=[],
            split="val",
            should_refuse=True,
        )
    ]


def test_run_eval_does_not_judge_an_answered_should_refuse_item(
    tmp_path: Path,
) -> None:
    uri = _tracking_uri(tmp_path)
    calls: list[str] = []

    class RecordingJudge:
        def __call__(self, expected: str, actual: str) -> Verdict:
            calls.append(actual)
            return Verdict(label=FAITHFUL, rationale="because")

    def program(*, question: str) -> ChatResponse:
        return ChatResponse(answer="x", citations=[Citation(source="profile.org")])

    result = run_eval(
        _refusal_items(),
        program,
        tracking_uri=uri,
        experiment="janbot-eval",
        judge=RecordingJudge(),
    )

    assert calls == []
    assert result.outcomes[0].judge_verdict is None
    assert result.judge_failures == []


def test_run_eval_excludes_should_refuse_items_from_reference_failures(
    tmp_path: Path,
) -> None:
    uri = _tracking_uri(tmp_path)

    def program(*, question: str) -> ChatResponse:
        return ChatResponse(
            answer="See https://github.com/jstavel/evil for details.",
            citations=[Citation(source="profile.org")],
        )

    result = run_eval(_refusal_items(), program, tracking_uri=uri, experiment="janbot-eval")

    assert result.reference_failures == []


def test_run_eval_fails_naming_the_tracking_uri_when_unreachable(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError) as excinfo:
        run_eval(
            _items(),
            _stub_program(),
            tracking_uri="bogus-scheme://nope",
            experiment="janbot-eval",
        )

    assert "bogus-scheme://nope" in str(excinfo.value)


def test_cli_keyless_run_reads_dataset_and_reports_tracking_uri(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = tmp_path / "public_profile_org"
    write_org(corpus / "profile.org", heading="About", body="Search infrastructure engineer.")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)

    dataset = tmp_path / "dataset.yaml"
    dataset.write_text(
        yaml.safe_dump(
            [
                {
                    "question": "What search infrastructure have you built?",
                    "expected_answer": "Search infrastructure.",
                    "expected_sources": ["profile.org"],
                    "split": "train",
                }
            ]
        ),
        encoding="utf-8",
    )

    uri = _tracking_uri(tmp_path)
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "MLFLOW_TRACKING_URI": uri,
    }

    code = eval_cli.main(
        ["--dataset", str(dataset)],
        env=env,
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "answer_coverage: " in out
    assert "(n=" in out


def test_cli_all_declined_items_returns_zero(
    tmp_path: Path,
    embedder: Embedder,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset = tmp_path / "dataset.yaml"
    dataset.write_text(
        yaml.safe_dump(
            [
                {
                    "question": "What search infrastructure have you built?",
                    "expected_answer": "Search infrastructure.",
                    "expected_sources": ["profile.org"],
                    "split": "train",
                }
            ]
        ),
        encoding="utf-8",
    )
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(tmp_path / "empty-index"),
        "MLFLOW_TRACKING_URI": _tracking_uri(tmp_path),
    }

    code = eval_cli.main(
        ["--dataset", str(dataset)],
        env=env,
        embedder=embedder,
        lm_factory=StubLMFactory(),
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "failed:" not in out
    assert "refusal:" in out
    assert "What search infrastructure have you built?" in out


class OffListLMFactory:
    """LM factory whose canned answer carries an off-list URL (unverifiable reference)."""

    def __call__(self, **kwargs: object) -> DummyLM:
        answer = {
            "answer": "See https://github.com/jstavel/evil for details.",
            "citations": ["profile.org"],
        }
        return DummyLM([dict(answer) for _ in range(16)])


def test_cli_flags_off_list_reference_per_item(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = tmp_path / "public_profile_org"
    write_org(corpus / "profile.org", heading="About", body="Search infrastructure engineer.")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)

    dataset = tmp_path / "dataset.yaml"
    dataset.write_text(
        yaml.safe_dump(
            [
                {
                    "question": "What search infrastructure have you built?",
                    "expected_answer": "Search infrastructure.",
                    "expected_sources": ["profile.org"],
                    "split": "train",
                }
            ]
        ),
        encoding="utf-8",
    )
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "MLFLOW_TRACKING_URI": _tracking_uri(tmp_path),
    }

    code = eval_cli.main(
        ["--dataset", str(dataset)],
        env=env,
        embedder=embedder,
        lm_factory=OffListLMFactory(),
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "reference:" in out
    assert "github.com/jstavel/evil" in out
    assert "What search infrastructure have you built?" in out


def test_cli_flags_a_citation_miss_per_item(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = tmp_path / "public_profile_org"
    write_org(corpus / "profile.org", heading="About", body="Search infrastructure engineer.")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)

    dataset = tmp_path / "dataset.yaml"
    dataset.write_text(
        yaml.safe_dump(
            [
                {
                    "question": "What search infrastructure have you built?",
                    "expected_answer": "Search infrastructure.",
                    "expected_sources": ["projects.org"],
                    "split": "train",
                }
            ]
        ),
        encoding="utf-8",
    )
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "MLFLOW_TRACKING_URI": _tracking_uri(tmp_path),
    }

    code = eval_cli.main(
        ["--dataset", str(dataset)],
        env=env,
        embedder=embedder,
        lm_factory=StubLMFactory(citations=["profile.org"]),
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "citation:" in out
    assert "missing cited source(s): projects.org" in out


def test_run_eval_pins_the_dataset_as_a_param_and_artifact(tmp_path: Path) -> None:
    import hashlib

    dataset = tmp_path / "dataset.yaml"
    dataset.write_text("[]\n", encoding="utf-8")
    uri = _tracking_uri(tmp_path)

    run_eval(
        _items(),
        _stub_program(),
        tracking_uri=uri,
        experiment="janbot-eval",
        params={"model_mode": "eval", "top_k": 3},
        dataset_path=dataset,
    )

    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    run = client.search_runs([experiment.experiment_id])[0]
    assert run.data.params["dataset_sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert run.data.params["top_k"] == "3"
    assert any(a.path == dataset.name for a in client.list_artifacts(run.info.run_id))


def test_two_runs_expose_config_and_metrics_side_by_side(tmp_path: Path) -> None:
    uri = _tracking_uri(tmp_path)

    run_eval(
        _items(),
        _stub_program(),
        tracking_uri=uri,
        experiment="janbot-eval",
        params={"model_mode": "eval", "top_k": 3},
    )
    run_eval(
        _items(),
        _stub_program(),
        tracking_uri=uri,
        experiment="janbot-eval",
        params={"model_mode": "production", "top_k": 4},
    )

    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 2
    assert {r.data.params["model_mode"] for r in runs} == {"eval", "production"}
    assert {r.data.params["top_k"] for r in runs} == {"3", "4"}
    assert all(r.data.metrics for r in runs)


def test_run_params_carries_every_run_affecting_config() -> None:
    from janbot.config import load_config
    from janbot.eval.__main__ import run_params

    assert set(run_params(load_config({}))) == {
        "model_mode",
        "model_snapshot",
        "judge_model",
        "temperature",
        "seed",
        "top_k",
        "retrieval_mode",
        "retrieval_window",
        "relevance_threshold",
        "program",
    }


def test_cli_pins_the_dataset_in_the_recorded_run(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
) -> None:
    import hashlib

    corpus = tmp_path / "public_profile_org"
    write_org(corpus / "profile.org", heading="About", body="Search infrastructure engineer.")
    index_path = tmp_path / "index"
    index_corpus(corpus, index_path, embedder)

    dataset = tmp_path / "dataset.yaml"
    dataset.write_text(
        yaml.safe_dump(
            [
                {
                    "question": "What search infrastructure have you built?",
                    "expected_answer": "Search infrastructure.",
                    "expected_sources": ["profile.org"],
                    "split": "train",
                }
            ]
        ),
        encoding="utf-8",
    )

    uri = _tracking_uri(tmp_path)
    env = {
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(index_path),
        "MLFLOW_TRACKING_URI": uri,
    }

    assert (
        eval_cli.main(
            ["--dataset", str(dataset)], env=env, embedder=embedder, lm_factory=StubLMFactory()
        )
        == 0
    )

    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("janbot-eval")
    run = client.search_runs([experiment.experiment_id])[0]
    assert run.data.params["dataset_sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert any(a.path == dataset.name for a in client.list_artifacts(run.info.run_id))
