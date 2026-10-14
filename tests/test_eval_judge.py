"""Unit tests for the LLM-as-a-judge, its config routing, and the ``faithfulness`` metric.

They prove the story's matrix without a model or a network: a stub judge returning
``faithful`` passes an item and counts in the aggregate; one returning
``hallucinated`` fails it and records the verdict; a judge that raises on one item
leaves it unjudged, is flagged, and the run continues; and a run with no judge
leaves every item unjudged with the metric at ``0``. The judge LM builder is
asserted with a recording stub factory, so ``openrouter/<JANBOT_JUDGE_MODEL>``
routing and the shared key are verified without constructing a real LM.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from janbot.api.contract import ChatResponse, Citation
from janbot.config import load_config
from janbot.eval import __main__ as eval_cli
from janbot.eval.dataset import GoldenItem
from janbot.eval.judge import (
    FAITHFUL,
    HALLUCINATED,
    Verdict,
    build_judge,
    parse_verdict,
)
from janbot.eval.runner import run_eval
from janbot.ingest import index_corpus
from janbot.llm import build_judge_lm

Embedder = Callable[[list[str]], list[list[float]]]

DEFAULT_JUDGE_SNAPSHOT = "openrouter/openai/gpt-4o-mini-2024-07-18"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


@pytest.fixture(autouse=True)
def _clear_janbot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "JANBOT_MODEL_MODE",
        "JANBOT_MODEL_SNAPSHOT",
        "JANBOT_JUDGE_MODEL",
        "JANBOT_CORPUS_PATH",
        "JANBOT_INDEX_PATH",
        "JANBOT_PROJECT_ROOT",
        "JANBOT_TEMPERATURE",
        "JANBOT_SEED",
        "JANBOT_TOP_K",
    ):
        monkeypatch.delenv(name, raising=False)


class StubLMFactory:
    """Recording factory that captures construction kwargs instead of building an LM."""

    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None
        self.calls = 0

    def __call__(self, **kwargs: object) -> object:
        self.calls += 1
        self.kwargs = kwargs
        return "stub-lm"


@pytest.mark.parametrize(
    "raw", ["faithful", "Faithful", " faithful. ", "Verdict: faithful"]
)
def test_parse_verdict_accepts_faithful(raw: str) -> None:
    assert parse_verdict(raw) == FAITHFUL


@pytest.mark.parametrize(
    "raw", ["hallucinated", "Hallucinated", " hallucinated! ", "Verdict: hallucinated"]
)
def test_parse_verdict_accepts_hallucinated(raw: str) -> None:
    assert parse_verdict(raw) == HALLUCINATED


@pytest.mark.parametrize("raw", ["", "maybe", "cannot tell"])
def test_parse_verdict_rejects_an_unrecognized_verdict(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_verdict(raw)


@pytest.mark.parametrize(
    "raw",
    ["not hallucinated", "no hallucination detected", "not faithful", "unfaithful"],
)
def test_parse_verdict_never_reads_a_negation_as_the_opposite(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_verdict(raw)


def test_parse_verdict_reads_an_affirmed_faithful_with_a_negated_hallucination() -> None:
    assert parse_verdict("faithful, no hallucination") == FAITHFUL


def test_judge_model_defaults_to_the_locked_snapshot() -> None:
    assert load_config({}).judge_model == "openai/gpt-4o-mini-2024-07-18"


def test_judge_model_follows_a_snapshot_override_when_unset() -> None:
    config = load_config({"JANBOT_MODEL_SNAPSHOT": "vendor/model-x"})

    assert config.judge_model == "vendor/model-x"


def test_judge_model_override_is_independent_of_the_snapshot() -> None:
    config = load_config(
        {"JANBOT_MODEL_SNAPSHOT": "vendor/model-x", "JANBOT_JUDGE_MODEL": "vendor/judge-y"}
    )

    assert config.model_snapshot == "vendor/model-x"
    assert config.judge_model == "vendor/judge-y"


def test_build_judge_lm_routes_openrouter_judge_model_through_the_same_key() -> None:
    factory = StubLMFactory()
    config = load_config(
        {"JANBOT_JUDGE_MODEL": "anthropic/claude-3.5-sonnet", "JANBOT_SEED": "7"}
    )

    lm = build_judge_lm(config, "sk-openrouter", lm_factory=factory)

    assert lm == "stub-lm"
    assert factory.calls == 1
    assert factory.kwargs == {
        "model": "openrouter/anthropic/claude-3.5-sonnet",
        "temperature": 0.0,
        "api_base": OPENROUTER_API_BASE,
        "seed": 7,
        "api_key": "sk-openrouter",
    }


def test_build_judge_lm_defaults_to_the_locked_snapshot_and_eval_seed() -> None:
    factory = StubLMFactory()

    build_judge_lm(load_config({}), lm_factory=factory)

    assert factory.kwargs == {
        "model": DEFAULT_JUDGE_SNAPSHOT,
        "temperature": 0.0,
        "api_base": OPENROUTER_API_BASE,
        "seed": 0,
    }


def test_build_judge_scores_with_the_wrapped_lm() -> None:
    from dspy.utils import DummyLM

    lm = DummyLM([{"verdict": "hallucinated", "rationale": "invented a fact"}])
    judge = build_judge(lm)

    verdict = judge("The sky is blue.", "The sky is green.")

    assert verdict == Verdict(label=HALLUCINATED, rationale="invented a fact")


def test_resolve_judge_without_a_key_is_none() -> None:
    assert eval_cli._resolve_judge(load_config({}), None, None, None) is None


def test_resolve_judge_returns_an_injected_judge_unchanged() -> None:
    assert (
        eval_cli._resolve_judge(load_config({}), None, None, _faithful_judge)
        is _faithful_judge
    )


def test_resolve_judge_does_not_override_the_default_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel_lm = object()

    def fake_build_judge_lm(config: object, api_key: str | None = None, **kwargs: object) -> object:
        captured["api_key"] = api_key
        captured["kwargs"] = kwargs
        return sentinel_lm

    monkeypatch.setattr("janbot.llm.build_judge_lm", fake_build_judge_lm)
    monkeypatch.setattr(eval_cli, "build_judge", lambda lm: ("judge", lm))

    judge = eval_cli._resolve_judge(load_config({}), "sk-openrouter", None, None)

    assert judge == ("judge", sentinel_lm)
    assert captured == {"api_key": "sk-openrouter", "kwargs": {}}


def test_resolve_judge_forwards_an_injected_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    factory = object()

    def fake_build_judge_lm(config: object, api_key: str | None = None, **kwargs: object) -> str:
        captured.update(kwargs)
        return "lm"

    monkeypatch.setattr("janbot.llm.build_judge_lm", fake_build_judge_lm)
    monkeypatch.setattr(eval_cli, "build_judge", lambda lm: lm)

    eval_cli._resolve_judge(load_config({}), "sk-openrouter", factory, None)

    assert captured == {"lm_factory": factory}


def _faithful_judge(expected_answer: str, answer: str) -> Verdict:
    return Verdict(label=FAITHFUL, rationale="supported")


def _hallucinated_judge(expected_answer: str, answer: str) -> Verdict:
    return Verdict(label=HALLUCINATED, rationale="invented")


def _items() -> list[GoldenItem]:
    return [
        GoldenItem(question="q1", expected_answer="a1", expected_sources=["profile.org"]),
        GoldenItem(question="q2", expected_answer="a2", expected_sources=["profile.org"]),
    ]


def _program(*, question: str) -> ChatResponse:
    return ChatResponse(answer="Answer.", citations=[Citation(source="profile.org")])


def _tracking_uri(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'mlflow.db'}"


def test_run_eval_faithful_judge_passes_and_counts(tmp_path: Path) -> None:
    result = run_eval(
        _items(),
        _program,
        tracking_uri=_tracking_uri(tmp_path),
        experiment="janbot-eval",
        judge=_faithful_judge,
    )

    assert result.metrics["faithfulness"] == 1.0
    assert all(
        outcome.judge_verdict is not None
        and outcome.judge_verdict.label == FAITHFUL
        for outcome in result.outcomes
    )
    assert result.judge_failures == []


def test_run_eval_hallucinated_verdict_fails_and_is_recorded(tmp_path: Path) -> None:
    result = run_eval(
        _items(),
        _program,
        tracking_uri=_tracking_uri(tmp_path),
        experiment="janbot-eval",
        judge=_hallucinated_judge,
    )

    assert result.metrics["faithfulness"] == 0.0
    labels = [
        outcome.judge_verdict.label
        for outcome in result.outcomes
        if outcome.judge_verdict is not None
    ]
    assert labels == [HALLUCINATED, HALLUCINATED]
    assert result.judge_failures == []


def test_run_eval_records_a_judge_failure_and_continues(tmp_path: Path) -> None:
    def judge(expected_answer: str, answer: str) -> Verdict:
        if expected_answer == "a2":
            raise RuntimeError("judge exploded")
        return Verdict(label=FAITHFUL, rationale="supported")

    result = run_eval(
        _items(),
        _program,
        tracking_uri=_tracking_uri(tmp_path),
        experiment="janbot-eval",
        judge=judge,
    )

    assert result.metrics["faithfulness"] == 1.0
    assert result.outcomes[0].judge_verdict is not None
    assert result.outcomes[1].judge_verdict is None
    assert len(result.judge_failures) == 1
    assert "judge failed" in result.judge_failures[0]
    assert "judge exploded" in result.judge_failures[0]


def test_run_eval_without_a_judge_leaves_items_unjudged(tmp_path: Path) -> None:
    result = run_eval(
        _items(),
        _program,
        tracking_uri=_tracking_uri(tmp_path),
        experiment="janbot-eval",
    )

    assert result.metrics["faithfulness"] == 0.0
    assert all(outcome.judge_verdict is None for outcome in result.outcomes)
    assert result.judge_failures == []


class _DummyProgramLMFactory:
    """LM factory yielding a canned-answer ``DummyLM`` (no real model)."""

    def __call__(self, **kwargs: object) -> object:
        from dspy.utils import DummyLM

        answer = {"answer": "Grounded.", "citations": ["profile.org"]}
        return DummyLM([dict(answer) for _ in range(16)])


def test_cli_scores_with_an_injected_judge(
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
        lm_factory=_DummyProgramLMFactory(),
        judge=_faithful_judge,
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "faithfulness: 1.0000" in out
    assert "judged: 1/1" in out
    assert (
        "judge: What search infrastructure have you built? — faithful" in out
    )
