"""Tests for :mod:`janbot.config`.

These tests assert the documented ``JANBOT_*`` contract using literal env names
and literal default values (not the module's own constants), so a renamed
prefix or changed default breaks the suite.
"""

from pathlib import Path

import pytest

from janbot.config import PROJECT_ROOT, load_config

DEFAULT_SNAPSHOT = "openai/gpt-4o-mini-2024-07-18"


@pytest.fixture(autouse=True)
def _clear_janbot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "JANBOT_MODEL_MODE",
        "JANBOT_MODEL_SNAPSHOT",
        "JANBOT_CORPUS_PATH",
        "JANBOT_INDEX_PATH",
        "JANBOT_PROJECT_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_when_no_env() -> None:
    config = load_config({})

    assert config.model_mode == "eval"
    assert config.model_snapshot == DEFAULT_SNAPSHOT
    assert config.corpus_path == (PROJECT_ROOT / "public_profile_org").resolve()
    assert config.index_path == (PROJECT_ROOT / "chroma_db").resolve()


def test_default_paths_are_absolute_under_project_root() -> None:
    config = load_config({})

    assert config.corpus_path.is_absolute()
    assert config.index_path.is_absolute()
    assert config.corpus_path == PROJECT_ROOT / "public_profile_org"
    assert config.index_path == PROJECT_ROOT / "chroma_db"


def test_project_root_is_repository_root() -> None:
    assert PROJECT_ROOT == Path(__file__).resolve().parents[1]
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_defaults_from_process_environment() -> None:
    config = load_config()

    assert config.model_mode == "eval"
    assert config.corpus_path == (PROJECT_ROOT / "public_profile_org").resolve()


def test_process_environment_variable_is_picked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JANBOT_MODEL_MODE", "production")

    config = load_config()

    assert config.model_mode == "production"
    assert config.model_snapshot == DEFAULT_SNAPSHOT
    assert config.corpus_path == (PROJECT_ROOT / "public_profile_org").resolve()
    assert config.index_path == (PROJECT_ROOT / "chroma_db").resolve()


def test_model_snapshot_override() -> None:
    snapshot = "anthropic/claude-3.5-sonnet"
    config = load_config({"JANBOT_MODEL_SNAPSHOT": snapshot})

    assert config.model_snapshot == snapshot
    assert config.model_mode == "eval"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_model_mode_falls_back_to_default(blank: str) -> None:
    assert load_config({"JANBOT_MODEL_MODE": blank}).model_mode == "eval"


@pytest.mark.parametrize("value", ["Production", " production ", "PRODUCTION"])
def test_model_mode_is_normalized(value: str) -> None:
    assert load_config({"JANBOT_MODEL_MODE": value}).model_mode == "production"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_snapshot_falls_back_to_default(blank: str) -> None:
    assert load_config({"JANBOT_MODEL_SNAPSHOT": blank}).model_snapshot == DEFAULT_SNAPSHOT


def test_invalid_model_mode_raises() -> None:
    with pytest.raises(ValueError) as excinfo:
        load_config({"JANBOT_MODEL_MODE": "bogus"})

    message = str(excinfo.value)
    assert "JANBOT_MODEL_MODE" in message
    assert "bogus" in message
    assert "eval" in message
    assert "production" in message


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_paths_fall_back_to_default(blank: str) -> None:
    config = load_config({"JANBOT_CORPUS_PATH": blank, "JANBOT_INDEX_PATH": blank})

    assert config.corpus_path == (PROJECT_ROOT / "public_profile_org").resolve()
    assert config.index_path == (PROJECT_ROOT / "chroma_db").resolve()


def test_relative_corpus_path_resolves_under_project_root() -> None:
    config = load_config({"JANBOT_CORPUS_PATH": "corpus"})

    assert config.corpus_path.is_absolute()
    assert config.corpus_path == (PROJECT_ROOT / "corpus").resolve()


def test_relative_index_path_resolves_under_project_root() -> None:
    config = load_config({"JANBOT_INDEX_PATH": "other/db"})

    assert config.index_path.is_absolute()
    assert config.index_path == (PROJECT_ROOT / "other/db").resolve()


def test_tilde_path_expands_to_home() -> None:
    config = load_config({"JANBOT_CORPUS_PATH": "~/x"})

    assert config.corpus_path.is_absolute()
    assert config.corpus_path == (Path.home() / "x").resolve()


def test_absolute_path_used_as_is() -> None:
    config = load_config({"JANBOT_CORPUS_PATH": "/tmp/x"})

    assert config.corpus_path == Path("/tmp/x").resolve()


def test_project_root_override(tmp_path: Path) -> None:
    config = load_config(
        {"JANBOT_PROJECT_ROOT": str(tmp_path), "JANBOT_CORPUS_PATH": "corpus"}
    )

    assert config.corpus_path == (tmp_path / "corpus").resolve()
    assert config.index_path == (tmp_path / "chroma_db").resolve()


def test_config_is_frozen() -> None:
    config = load_config({})

    with pytest.raises(AttributeError):
        config.model_mode = "production"  # type: ignore[misc]
