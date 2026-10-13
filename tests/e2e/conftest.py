"""Fixtures for the port-only end-to-end harness (tracer bullet).

The harness proves the *shipped service answers through its HTTP port*: it starts
``uv run uvicorn janbot.api.main:app`` as a subprocess against a fixture index
built for **this** checkout, waits on ``GET /health``, and hands the tests a base
URL. This module imports no ``janbot`` internals — only ``httpx``, ``pytest`` and
the standard library — so nothing here can reach into the service except over
HTTP (Done-when 5).

The fixture index is built at session setup by running the ingestion CLI as a
subprocess (which imports ``janbot`` in *its own* process, not in the test
process). It is not committed: a ChromaDB index bakes absolute ``source_path``
values, so a committed index would only ever match the author's checkout path.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
FIXTURE_CORPUS = HERE / "fixture_corpus"

HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 120.0
BUILD_TIMEOUT_SECONDS = 300.0
POLL_INTERVAL_SECONDS = 0.25


def _free_port() -> int:
    """Ask the OS for an unused TCP port on the loopback interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def _build_fixture_index(index_path: Path) -> None:
    """Build ``index_path`` from the fixture corpus via the ingestion CLI subprocess."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "janbot.ingest", "--index", str(index_path)],
        cwd=str(REPO_ROOT),
        env={**os.environ, "JANBOT_CORPUS_PATH": str(FIXTURE_CORPUS)},
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "building the fixture index failed "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )


def _stop(process: subprocess.Popen[bytes]) -> None:
    """Terminate ``process``, escalating to kill."""
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def _log_text(log_path: Path) -> str:
    try:
        return log_path.read_text() or "<no output captured>"
    except OSError:
        return "<no output captured>"


def _wait_for_health(base_url: str, process: subprocess.Popen[bytes], log_path: Path) -> None:
    """Poll ``GET /health`` until the service is ready or the bounded wait expires."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error = "no response yet"
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"the janbot service exited with code {return_code} before "
                f"GET /health became ready; output:\n{_log_text(log_path)}"
            )
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code == 200:
                return
            last_error = f"GET /health returned {response.status_code}"
        time.sleep(POLL_INTERVAL_SECONDS)

    raise RuntimeError(
        f"the janbot service was not ready at {base_url} within "
        f"{STARTUP_TIMEOUT_SECONDS:.0f}s (last error: {last_error}); "
        f"output:\n{_log_text(log_path)}"
    )


@pytest.fixture(scope="session")
def fixture_index(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a fixture index for this checkout and return its path."""
    if not FIXTURE_CORPUS.is_dir():
        pytest.fail(f"the fixture corpus is missing: {FIXTURE_CORPUS}")
    index_path = tmp_path_factory.mktemp("fixture_index") / "chroma"
    _build_fixture_index(index_path)
    return index_path


@contextmanager
def _serve(index_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Start the service as a subprocess against ``index_path``; yield its base URL."""
    port = _free_port()
    base_url = f"http://{HOST}:{port}"
    log_path = tmp_path_factory.mktemp("service") / "service.log"
    env = {
        **os.environ,
        "JANBOT_CORPUS_PATH": str(FIXTURE_CORPUS),
        "JANBOT_INDEX_PATH": str(index_path),
        "JANBOT_MODEL_MODE": "eval",
    }

    with open(log_path, "wb") as log_file:
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "uvicorn",
                "janbot.api.main:app",
                "--host",
                HOST,
                "--port",
                str(port),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_health(base_url, process, log_path)
            yield base_url
        finally:
            _stop(process)


@pytest.fixture(scope="session")
def service_base_url(
    fixture_index: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[str]:
    """The service started against the fixture index (a populated corpus)."""
    with _serve(fixture_index, tmp_path_factory) as base_url:
        yield base_url


@pytest.fixture(scope="session")
def empty_service_base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """The service started against an empty index (no corpus grounding)."""
    empty_index = tmp_path_factory.mktemp("empty_index") / "chroma"
    with _serve(empty_index, tmp_path_factory) as base_url:
        yield base_url

