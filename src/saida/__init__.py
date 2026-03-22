"""Public package exports for SAIDA."""

from __future__ import annotations

from typing import Any

__all__ = ["Saida"]


def __getattr__(name: str) -> Any:
    if name == "Saida":
        from saida.engine import Saida

        return Saida
    raise AttributeError(f"module 'saida' has no attribute {name!r}")
