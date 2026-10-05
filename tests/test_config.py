"""Tests for :mod:`janbot.config`."""

from pathlib import Path

import pytest

from janbot.config import (
    CORPUS_PATH_ENV,
    DEFAULT_CORPUS_PATH,
    DEFAULT_INDEX_PATH,
    DEFAULT_MODEL_MODE,
    DEFAULT_MODEL_SNAPSHOT,
    INDEX_PATH_ENV,
    MODEL_MODE_ENV,
    MODEL_MODE_EVAL,
    MODEL_MODE_PRODUCTION,
    MODEL_SNAPSHOT_ENV,
    load_config,
)


@pytest.fixture(autouse=True)
def _clear_janbot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (MODEL_MODE_ENV, MODEL_SNAPSHOT_ENV, CORPUS_PATH_ENV, INDEX_PATH_ENV):
        monkeypatch.delenv(name, raising=False)


def test_defaults_when_no_env() -> None:
    config = load_config({})

    assert config.model_mode == DEFAULT_MODEL_MODE == MODEL_MODE_EVAL
    assert config.model_snapshot == DEFAULT_MODEL_SNAPSHOT
    assert config.corpus_path == Path(DEFAULT_CORPUS_PATH)
    assert config.index_path == Path(DEFAULT_INDEX_PATH)


def test_defaults_from_process_environment() -> None:
    config = load_config()

    assert config.model_mode == MODEL_MODE_EVAL
    assert config.corpus_path == Path(DEFAULT_CORPUS_PATH)


def test_process_environment_variable_is_picked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_MODE_ENV, MODEL_MODE_PRODUCTION)

    config = load_config()

    assert config.model_mode == MODEL_MODE_PRODUCTION
    assert config.model_snapshot == DEFAULT_MODEL_SNAPSHOT
    assert config.corpus_path == Path(DEFAULT_CORPUS_PATH)
    assert config.index_path == Path(DEFAULT_INDEX_PATH)


def test_model_mode_override() -> None:
    config = load_config({MODEL_MODE_ENV: MODEL_MODE_PRODUCTION})

    assert config.model_mode == MODEL_MODE_PRODUCTION
    assert config.model_snapshot == DEFAULT_MODEL_SNAPSHOT
    assert config.corpus_path == Path(DEFAULT_CORPUS_PATH)
    assert config.index_path == Path(DEFAULT_INDEX_PATH)


def test_model_snapshot_override() -> None:
    snapshot = "anthropic/claude-3.5-sonnet"
    config = load_config({MODEL_SNAPSHOT_ENV: snapshot})

    assert config.model_snapshot == snapshot
    assert config.model_mode == DEFAULT_MODEL_MODE
    assert config.corpus_path == Path(DEFAULT_CORPUS_PATH)
    assert config.index_path == Path(DEFAULT_INDEX_PATH)


def test_corpus_path_override_is_coerced_to_path() -> None:
    config = load_config({CORPUS_PATH_ENV: "some/dir"})

    assert isinstance(config.corpus_path, Path)
    assert config.corpus_path == Path("some/dir")
    assert config.index_path == Path(DEFAULT_INDEX_PATH)


def test_index_path_override_is_coerced_to_path() -> None:
    config = load_config({INDEX_PATH_ENV: "other/db"})

    assert isinstance(config.index_path, Path)
    assert config.index_path == Path("other/db")
    assert config.corpus_path == Path(DEFAULT_CORPUS_PATH)


def test_invalid_model_mode_raises() -> None:
    with pytest.raises(ValueError) as excinfo:
        load_config({MODEL_MODE_ENV: "bogus"})

    message = str(excinfo.value)
    assert MODEL_MODE_ENV in message
    assert "bogus" in message
    assert MODEL_MODE_EVAL in message
    assert MODEL_MODE_PRODUCTION in message


def test_config_is_frozen() -> None:
    config = load_config({})

    with pytest.raises(AttributeError):
        config.model_mode = MODEL_MODE_PRODUCTION  # type: ignore[misc]
