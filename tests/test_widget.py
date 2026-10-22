"""The shipped widget's refusal UX, tested without network.

The widget is a static HTML page whose inline script is the whole client:
``tests/widget/index.test.mjs`` runs that script in a ``vm`` with stubbed
``document``/``fetch`` and drives the submit handler with fake responses.
This wrapper runs the node test file and maps its exit code onto pytest's;
it skips only when ``node`` is absent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WIDGET_TEST = PROJECT_ROOT / "tests" / "widget" / "index.test.mjs"


def test_widget_inline_script_behaviour() -> None:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        ["node", str(WIDGET_TEST)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
