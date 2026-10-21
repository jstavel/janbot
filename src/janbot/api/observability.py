"""Structured decline attribution for production logs.

Only a closed-set component and cause are emitted; question text, answer text,
citation labels and the API key never enter a log line. The ``/chat`` contract is
untouched — this is logging, not a response field.
"""

from __future__ import annotations

import json
import logging

DECLINE_COMPONENTS = frozenset({"program", "guardrail"})
logger = logging.getLogger("janbot.decline")


def log_decline(component: str, cause: str) -> None:
    """Emit one machine-readable decline record without any request text."""
    if component not in DECLINE_COMPONENTS:
        raise ValueError(f"unknown decline component: {component!r}")
    if not cause or "\n" in cause or "\r" in cause:
        raise ValueError("a decline cause must be a single non-empty token")
    payload = {"event": "decline", "component": component, "cause": cause}
    # WARNING is deliberate: it survives the default root logger level and is
    # captured by Cloud Run without a production logging reconfiguration.
    logger.warning(json.dumps(payload, sort_keys=True, separators=(",", ":")))
