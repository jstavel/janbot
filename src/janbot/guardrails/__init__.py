"""Deterministic guardrail layer (ADR-009/ADR-010)."""

from __future__ import annotations

from janbot.guardrails.output_guard import GuardResult, apply_output_guard

__all__ = ["GuardResult", "apply_output_guard"]
