from __future__ import annotations

from saida_core.core.domain.query import Query
from saida_core.core.domain.result import AnalysisResult
from saida_core.core.services.orchestration_service import OrchestrationService


class AnalyticsThenReasoningPipeline:
    def __init__(self, orchestration: OrchestrationService):
        self.orchestration = orchestration

    def run(self, question: str) -> AnalysisResult:
        return self.orchestration.run(Query(text=question, task_type="analytics"))