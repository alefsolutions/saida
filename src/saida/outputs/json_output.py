"""JSON output helpers for canonical analytical results."""

from __future__ import annotations

from typing import Any

from saida.core.contracts import AnalysisResult


class JsonOutputFormatter:
    """Return the canonical JSON-safe analytical result."""

    def format(self, result: AnalysisResult) -> dict[str, Any]:
        """Format an analysis result as a JSON-safe payload."""
        return result.to_response_dict()
