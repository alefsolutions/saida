"""JSON output helpers for canonical analytical results."""

from __future__ import annotations

from typing import Any

from saida.core.contracts import AnalysisResult
from saida.outputs.interfaces import OutputInterface


class JsonOutputFormatter(OutputInterface):
    """Return the canonical JSON-safe analytical result."""

    @property
    def output_format(self) -> str:
        return "json"

    def render(self, result: AnalysisResult) -> dict[str, Any]:
        """Render an analysis result as a JSON-safe payload."""
        return result.to_response_dict()

    def format(self, result: AnalysisResult) -> dict[str, Any]:
        """Compatibility wrapper for the historical formatter API."""
        return self.render(result)


JsonOutputAdapter = JsonOutputFormatter
