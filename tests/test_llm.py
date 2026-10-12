"""Tests for :mod:`janbot.llm`.

Routing and LM-construction kwargs are asserted with literal values, so a
renamed constant or changed default breaks the suite. The LM seam is exercised
with a stub factory: no test constructs a real ``dspy.LM`` and nothing touches
the network.
"""

import pytest

import dspy
from janbot.config import load_config
from janbot.llm import build_lm, resolve_model

DEFAULT_SNAPSHOT = "openai/gpt-4o-mini-2024-07-18"
OPENROUTER_MODEL = "openrouter/auto"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


class StubLMFactory:
    """Callable factory that records construction kwargs instead of building."""

    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None
        self.calls = 0

    def __call__(self, **kwargs: object) -> object:
        self.calls += 1
        self.kwargs = kwargs
        return "stub-lm"


@pytest.fixture(autouse=True)
def _clear_janbot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "JANBOT_MODEL_MODE",
        "JANBOT_MODEL_SNAPSHOT",
        "JANBOT_CORPUS_PATH",
        "JANBOT_INDEX_PATH",
        "JANBOT_PROJECT_ROOT",
        "JANBOT_TEMPERATURE",
        "JANBOT_TOP_K",
    ):
        monkeypatch.delenv(name, raising=False)


def test_resolve_model_eval_returns_locked_snapshot() -> None:
    assert resolve_model(load_config({})) == DEFAULT_SNAPSHOT


def test_resolve_model_production_returns_openrouter_auto() -> None:
    config = load_config({"JANBOT_MODEL_MODE": "production"})

    assert resolve_model(config) == OPENROUTER_MODEL


def test_resolve_model_routes_by_environment_alone() -> None:
    eval_config = load_config({"JANBOT_MODEL_SNAPSHOT": "vendor/model-x"})
    production_config = load_config(
        {"JANBOT_MODEL_SNAPSHOT": "vendor/model-x", "JANBOT_MODEL_MODE": "production"}
    )

    assert resolve_model(eval_config) == "vendor/model-x"
    assert resolve_model(production_config) == OPENROUTER_MODEL


def test_build_lm_eval_uses_snapshot_and_configured_temperature() -> None:
    factory = StubLMFactory()
    config = load_config({"JANBOT_TEMPERATURE": "0.7"})

    lm = build_lm(config, lm_factory=factory)

    assert lm == "stub-lm"
    assert factory.calls == 1
    assert factory.kwargs == {"model": DEFAULT_SNAPSHOT, "temperature": 0.7}


def test_build_lm_eval_records_no_api_base_or_api_key() -> None:
    factory = StubLMFactory()
    config = load_config({})

    build_lm(config, "sk-test", lm_factory=factory)

    assert factory.kwargs == {"model": DEFAULT_SNAPSHOT, "temperature": 0.0}


def test_build_lm_production_uses_openrouter_snapshot_and_key() -> None:
    factory = StubLMFactory()
    config = load_config(
        {"JANBOT_MODEL_MODE": "production", "JANBOT_TEMPERATURE": "0.7"}
    )

    lm = build_lm(config, "sk-test", lm_factory=factory)

    assert lm == "stub-lm"
    assert factory.calls == 1
    assert factory.kwargs == {
        "model": OPENROUTER_MODEL,
        "temperature": 0.7,
        "api_base": OPENROUTER_API_BASE,
        "api_key": "sk-test",
    }


def test_build_lm_production_without_api_key_fails_fast() -> None:
    config = load_config({"JANBOT_MODEL_MODE": "production"})
    factory = StubLMFactory()

    with pytest.raises(ValueError) as excinfo:
        build_lm(config, lm_factory=factory)

    assert factory.calls == 0
    message = str(excinfo.value)
    assert "api_key" in message
    assert "production" in message


def test_default_lm_factory_is_dspy_lm() -> None:
    assert build_lm.__kwdefaults__ == {"lm_factory": dspy.LM}
