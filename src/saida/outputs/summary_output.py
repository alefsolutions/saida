"""Summary-text output adapter."""

from __future__ import annotations

from saida.core.contracts import AnalysisResult
from saida.outputs.interfaces import OutputInterface


class SummaryOutputAdapter(OutputInterface):
    """Render the preferred summary text from an AnalysisResult."""

    @property
    def output_format(self) -> str:
        return "summary"

    def render(self, result: AnalysisResult) -> str:
        return result.llm_summary or result.summary
