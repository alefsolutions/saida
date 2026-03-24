"""Formal output interfaces for SAIDA result rendering."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from saida.core.contracts import AnalysisResult


class OutputInterface(ABC):
    """Canonical interface for rendering AnalysisResult into delivery formats."""

    @property
    @abstractmethod
    def output_format(self) -> str:
        """Return the canonical output format identifier."""

    @abstractmethod
    def render(self, result: AnalysisResult) -> Any:
        """Render the canonical AnalysisResult into the adapter's format."""
