"""The embedding model identity is pinned and recorded."""

from __future__ import annotations

from janbot.store.embedding_model import (
    PINNED_MODEL_NAME,
    PINNED_MODEL_SHA256,
    assert_model_pin,
    model_identity,
)


def test_the_installed_provider_matches_the_pinned_model() -> None:
    assert_model_pin()
    identity = model_identity()

    assert identity["name"] == PINNED_MODEL_NAME
    assert identity["sha256"] == PINNED_MODEL_SHA256
    assert len(identity["sha256"]) == 64
