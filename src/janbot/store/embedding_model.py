"""Pinned identity of Chroma's ONNX embedding model.

Chroma ships ``all-MiniLM-L6-v2`` as a downloadable ONNX archive and verifies its
own SHA256. This module makes that identity an explicit build input: it asserts
the pinned constant still matches the installed provider, warms the download
(with a small retry for transient network failures), re-verifies the archive
SHA256 and returns the identity recorded in the baked index.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

PINNED_MODEL_NAME = "all-MiniLM-L6-v2"
PINNED_MODEL_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
PINNED_MODEL_URL = (
    "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
)


class EmbeddingModelError(RuntimeError):
    """The embedding model is missing, mismatched, or downloaded incompletely."""


def _model_class() -> Any:
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
        ONNXMiniLM_L6_V2,
    )

    return ONNXMiniLM_L6_V2


def assert_model_pin() -> None:
    """Fail if the installed Chroma provider no longer uses the pinned model."""
    model = _model_class()
    if model._MODEL_SHA256 != PINNED_MODEL_SHA256:
        raise EmbeddingModelError(
            "the installed Chroma ONNX model sha256 no longer matches the pin: "
            f"provider {model._MODEL_SHA256!r}, pin {PINNED_MODEL_SHA256!r}"
        )
    if model.MODEL_NAME != PINNED_MODEL_NAME:
        raise EmbeddingModelError(
            f"the installed Chroma model name is {model.MODEL_NAME!r}, "
            f"not the pinned {PINNED_MODEL_NAME!r}"
        )


def verify_pinned_model(*, attempts: int = 3) -> dict[str, str]:
    """Warm and verify the pinned model; return its recorded identity.

    A transient network failure is retried a few times; a persistent failure or
    an archive-sha mismatch raises and fails the build.
    """
    assert_model_pin()
    from chromadb.utils import embedding_functions

    function = embedding_functions.DefaultEmbeddingFunction()
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            function(["pinned-model-warmup"])
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001 - retry transient downloads
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)

    if last_error is not None:
        raise EmbeddingModelError(
            f"the pinned embedding model could not be fetched: {last_error}"
        ) from last_error

    model = _model_class()
    archive = Path(model.DOWNLOAD_PATH) / model.ARCHIVE_FILENAME
    if not archive.is_file():
        raise EmbeddingModelError(f"embedding model archive is missing: {archive}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != PINNED_MODEL_SHA256:
        raise EmbeddingModelError(
            f"embedding model sha256 mismatch: {digest!r} != {PINNED_MODEL_SHA256!r}"
        )
    return {
        "name": PINNED_MODEL_NAME,
        "sha256": PINNED_MODEL_SHA256,
        "url": PINNED_MODEL_URL,
    }


def model_identity() -> dict[str, str]:
    """The pinned identity without downloading (asserts the provider pin)."""
    assert_model_pin()
    return {
        "name": PINNED_MODEL_NAME,
        "sha256": PINNED_MODEL_SHA256,
        "url": PINNED_MODEL_URL,
    }


def main() -> int:
    try:
        identity = verify_pinned_model()
    except EmbeddingModelError as exc:
        print(f"embedding-model: {exc}")
        return 1
    print(json.dumps(identity, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
