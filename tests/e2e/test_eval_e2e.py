"""End-to-end eval suite: the recorded eval run as an operator runs it.

Keyless tier: ``run_keyless_eval.py`` (a subprocess helper, like
``make_index.py``) drives ``python -m janbot.eval`` end to end — corpus, index,
golden dataset, ``create_app``-built program, ``run_eval``, one MLflow run —
with a deterministic stub embedder and a canned ``DummyLM``. The tier runs the
CLI twice and asserts the two recorded runs report **identical metric values**:
with the stubs fixed, the whole pipeline is deterministic, so any drift is a
regression the suite catches.

Keyed tier (skips without ``OPENROUTER_API_KEY``, runs in ``e2e-keyed.yml``):
two fresh locked-snapshot eval processes over a **fixed five-item golden
subset** (real ``eval/golden_dataset.yaml`` questions and expected sources,
mixed splits), each with its own ``DSPY_CACHEDIR`` so both generations are real.
The index under them is built fresh from the **real** ``public_profile_org``
corpus by the ingest CLI in its own subprocess — the golden expected sources
name real corpus files, so the metrics only mean something against the real
corpus. A non-vacuity guard asserts the runs measured something
(``retrieval_accuracy > 0``, ``citation_correctness > 0``), so a degenerate
all-declined run fails loudly instead of passing as ``0.0 == 0.0``. As with
``test_determinism_e2e.py``, ``gpt-4o-mini`` does not fix its wording at
temperature 0, so determinism is asserted at the layer the service controls —
``retrieval_accuracy`` and ``citation_correctness`` (grounded in retrieval and
cited-source sets, not wording) must agree run to run.

The test module imports no ``janbot`` internals — ``pytest``, the standard
library (incl. ``json``, which the loader's YAML parser reads) and nothing
else; ``janbot`` runs in the helper's and the CLI's own processes.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

from e2e._support import MODEL_KEY_ENV

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
KEYLESS_DRIVER = HERE / "run_keyless_eval.py"
REAL_CORPUS = REPO_ROOT / "public_profile_org"

RUN_TIMEOUT_SECONDS = 600.0
INDEX_TIMEOUT_SECONDS = 600.0

# The metrics the keyless tier pins across the two runs (every recorded metric).
KEYLESS_METRICS = (
    "answer_coverage",
    "public_references",
    "retrieval_accuracy",
    "retrieval_mrr",
    "citation_correctness",
    "citation_precision",
    "faithfulness",
    "refusal_pass_rate",
    "spurious_refusal_rate",
)

# The fixed keyed subset — real golden-dataset items (question, expected
# sources, split), chosen for distinct corpus grounding including one
# multi-source item, bounding the keyed row at ~10 model generations per run
# (one answer + one judge call per answered item).
KEYED_SUBSET = (
    (
        "Tell me about your matching engine project.",
        ["matching-engine.org"],
        "train",
    ),
    (
        "What Linux services have you actually run in production?",
        ["linux-server-era.org"],
        "train",
    ),
    (
        "Which of your projects can I inspect right now, and where?",
        ["public-proof-map.org"],
        "val",
    ),
    (
        "Where have you used Clojure in production and in testing?",
        ["edeposit.org", "clojure-testing.org"],
        "train",
    ),
    (
        "What is JanBot for?",
        ["janbot-value-proposition.org"],
        "val",
    ),
)

DETERMINISM_ENV = {
    "JANBOT_MODEL_MODE": "eval",
    "JANBOT_TEMPERATURE": "0",
    "JANBOT_SEED": "0",
    "JANBOT_MODEL_SNAPSHOT": "openai/gpt-4o-mini-2024-07-18",
}


def _run_keyless_eval(
    tmp_path: Path, tracking_uri: str, experiment: str, *extra_args: str
) -> subprocess.CompletedProcess[str]:
    """Run the keyless eval driver once; return the completed process."""
    return subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(KEYLESS_DRIVER),
            "--corpus",
            str(tmp_path / "corpus"),
            "--index",
            str(tmp_path / "index"),
            "--dataset",
            str(tmp_path / "dataset.yaml"),
            "--tracking-uri",
            tracking_uri,
            "--experiment",
            experiment,
            *extra_args,
        ],
        cwd=str(REPO_ROOT),
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SECONDS,
    )


def _run_cli_eval(
    env: dict[str, str], *cli_args: str
) -> subprocess.CompletedProcess[str]:
    """Run the real eval CLI once with ``cli_args``; return the completed process."""
    return subprocess.run(
        ["uv", "run", "python", "-m", "janbot.eval", *cli_args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SECONDS,
    )


def _tracking_uri(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'mlflow.db'}"


def _metrics_from_output(output: str) -> dict[str, float]:
    """Parse the ``name: value (n=…)`` metric lines the eval CLI prints.

    Only the registered metric names are accepted, so a failure line whose
    question text happens to contain ``": "`` and ``(n=`` can never inject a
    bogus entry.
    """
    metrics: dict[str, float] = {}
    for line in output.splitlines():
        if ": " not in line or "(n=" not in line:
            continue
        name, _, rest = line.partition(": ")
        if name not in KEYLESS_METRICS:
            continue
        value_text = rest.split(" ", 1)[0]
        try:
            metrics[name] = float(value_text)
        except ValueError:
            continue
    return metrics


def _run_ids_from_output(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("MLflow run: "):
            return line.removeprefix("MLflow run: ").strip()
    raise AssertionError(f"no MLflow run id in the eval output:\n{output}")


def _recorded_params(db_path: Path, run_id: str) -> dict[str, str]:
    """Read one recorded run's params from the MLflow sqlite store (stdlib only)."""
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT key, value FROM params WHERE run_uuid = ?", (run_id,)
        ).fetchall()
    finally:
        connection.close()
    return dict(rows)


def test_keyless_eval_records_identical_metrics_across_two_runs(
    tmp_path: Path,
) -> None:
    """Two keyless eval subprocesses record the same metrics for the same input."""
    outputs: list[tuple[Path, str]] = []
    for attempt in (1, 2):
        workspace = tmp_path / f"run-{attempt}"
        workspace.mkdir()
        result = _run_keyless_eval(workspace, _tracking_uri(workspace), "janbot-eval-e2e")
        assert result.returncode == 0, (
            f"keyless eval run {attempt} failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
        outputs.append((workspace / "mlflow.db", result.stdout))

    first_metrics = _metrics_from_output(outputs[0][1])
    second_metrics = _metrics_from_output(outputs[1][1])
    for name in KEYLESS_METRICS:
        assert name in first_metrics, (
            f"metric {name!r} missing from run 1:\n{outputs[0][1]}"
        )
        assert name in second_metrics, (
            f"metric {name!r} missing from run 2:\n{outputs[1][1]}"
        )
        assert first_metrics[name] == second_metrics[name], (
            f"metric {name!r} drifted between two keyless eval runs: "
            f"{first_metrics[name]} != {second_metrics[name]}"
        )

    # Both runs recorded (distinct run ids), each pinning its producing config.
    first_id = _run_ids_from_output(outputs[0][1])
    second_id = _run_ids_from_output(outputs[1][1])
    assert first_id != second_id
    for db_path, run_id in ((outputs[0][0], first_id), (outputs[1][0], second_id)):
        params = _recorded_params(db_path, run_id)
        assert params.get("model_mode") == "eval", (
            f"run {run_id} did not record model_mode=eval: {params}"
        )
        assert "top_k" in params and "temperature" in params, (
            f"run {run_id} is missing its config params: {params}"
        )

    # The fixture dataset carries both splits; the CLI evaluated all of it.
    assert "items: 4" in outputs[0][1]


def test_keyless_eval_val_split_records_the_val_items(tmp_path: Path) -> None:
    """The ``--split val`` row runs the same CLI path with a split filter."""
    workspace = tmp_path / "val-run"
    workspace.mkdir()
    result = _run_keyless_eval(
        workspace, _tracking_uri(workspace), "janbot-eval-e2e-val", "--split", "val"
    )
    assert result.returncode == 0, (
        f"keyless val eval failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "items: 2" in result.stdout


def _write_subset_dataset(path: Path) -> None:
    """Author the fixed keyed subset as JSON — valid YAML for the dataset loader."""
    items = [
        {"question": question, "expected_sources": list(sources), "split": split}
        for question, sources, split in KEYED_SUBSET
    ]
    path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def real_index(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A temp index built from the real public corpus by the ingest CLI subprocess.

    The golden expected sources name real corpus files, so the keyed tier must
    measure against the real corpus — not the two-file e2e fixture corpus — for
    its metrics to mean anything.
    """
    index_path = tmp_path_factory.mktemp("real_index") / "chroma"
    result = subprocess.run(
        ["uv", "run", "python", "-m", "janbot.ingest", "--index", str(index_path)],
        cwd=str(REPO_ROOT),
        env={**os.environ, "JANBOT_CORPUS_PATH": str(REAL_CORPUS)},
        capture_output=True,
        text=True,
        timeout=INDEX_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, (
        f"building the real-corpus index failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    return index_path


def _keyed_skip_reason() -> str | None:
    if not (os.environ.get(MODEL_KEY_ENV) or "").strip():
        return f"{MODEL_KEY_ENV} is not set: the keyed eval e2e row is skipped"
    if not REAL_CORPUS.is_dir():
        return f"the public corpus is missing: {REAL_CORPUS}"
    return None


@pytest.mark.skipif(
    _keyed_skip_reason() is not None, reason=_keyed_skip_reason() or ""
)
def test_two_locked_snapshot_eval_runs_agree_on_the_deterministic_metrics(
    real_index: Path,
    tmp_path: Path,
) -> None:
    """Two fresh locked-snapshot eval runs report the same retrieval/citation metrics."""

    def run_eval_once(attempt: int) -> dict[str, float]:
        workspace = tmp_path / f"keyed-{attempt}"
        workspace.mkdir()
        dataset = workspace / "keyed_subset.json"
        _write_subset_dataset(dataset)
        env = {
            **os.environ,
            **DETERMINISM_ENV,
            "JANBOT_CORPUS_PATH": str(REAL_CORPUS),
            "JANBOT_INDEX_PATH": str(real_index),
            "DSPY_CACHEDIR": str(workspace / "dspy_cache"),
            "MLFLOW_TRACKING_URI": _tracking_uri(workspace),
        }
        result = _run_cli_eval(
            env, "--dataset", str(dataset), "--experiment", "janbot-eval-e2e-keyed"
        )
        assert result.returncode == 0, (
            f"keyed eval run {attempt} failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
        metrics = _metrics_from_output(result.stdout)
        # Non-vacuity: the run measured something real — a degenerate run
        # (nothing retrieved, nothing answered) must fail loudly, not as 0 == 0.
        assert metrics.get("retrieval_accuracy", 0.0) > 0.0, (
            f"keyed eval run {attempt} measured nothing "
            f"(retrieval_accuracy is not > 0):\n{result.stdout}"
        )
        assert metrics.get("citation_correctness", 0.0) > 0.0, (
            f"keyed eval run {attempt} cited nothing "
            f"(citation_correctness is not > 0):\n{result.stdout}"
        )
        assert "items: 5" in result.stdout
        return metrics

    first = run_eval_once(1)
    second = run_eval_once(2)

    for name in ("retrieval_accuracy", "citation_correctness"):
        assert name in first and name in second, (
            f"metric {name!r} missing from a keyed run:\nfirst: {first}\nsecond: {second}"
        )
        assert first[name] == second[name], (
            f"two locked-snapshot runs disagree on the deterministic metric {name!r}: "
            f"{first[name]} != {second[name]}"
        )
