"""The cache-export CLI guards its own provenance before spending a run."""

from __future__ import annotations

from janbot.eval.__main__ import main


def test_cache_export_requires_val_split(capsys) -> None:
    code = main(
        ["--cache-out", "/tmp/unused.json", "--split", "train"],
        env={"JANBOT_MODEL_MODE": "production"},
    )

    assert code == 2
    assert "--split val" in capsys.readouterr().err


def test_cache_export_requires_production_mode(capsys) -> None:
    code = main(
        ["--cache-out", "/tmp/unused.json", "--split", "val"],
        env={"JANBOT_MODEL_MODE": "eval"},
    )

    assert code == 2
    assert "production" in capsys.readouterr().err


def test_cache_export_requires_the_output_guard_on(capsys) -> None:
    code = main(
        ["--cache-out", "/tmp/unused.json", "--split", "val"],
        env={
            "JANBOT_MODEL_MODE": "production",
            "JANBOT_OUTPUT_GUARD": "off",
        },
    )

    assert code == 2
    assert "OUTPUT_GUARD" in capsys.readouterr().err
