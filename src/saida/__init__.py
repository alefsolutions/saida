"""Public package exports for SAIDA."""

from __future__ import annotations

from typing import Any

__all__ = ["PromptAnalysisFrontend", "Saida"]


def __getattr__(name: str) -> Any:
    if name == "PromptAnalysisFrontend":
        from saida.plan_generation import PromptAnalysisFrontend

        return PromptAnalysisFrontend
    if name == "Saida":
        from saida.engine import Saida

        return Saida
    raise AttributeError(f"module 'saida' has no attribute {name!r}")
