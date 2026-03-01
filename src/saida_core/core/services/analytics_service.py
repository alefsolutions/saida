from __future__ import annotations

from saida_core.core.domain.context import ContextBundle
from saida_core.core.domain.result import AnalysisResult
from saida_core.core.contracts.llm import LLM


class AnalyticsService:
    def __init__(self, llm: LLM):
        self.llm = llm

    def analyze(self, query: str, context: ContextBundle, task_type: str) -> AnalysisResult:
        prompt = (
            f"Task type: {task_type}\n"
            f"Query: {query}\n"
            f"Records: {len(context.records)}\n"
            f"Documents: {len(context.documents)}\n"
            "Provide an analytics-first answer grounded in retrieved evidence."
        )
        answer = self.llm.generate(prompt)
        evidence = context.records + context.documents
        return AnalysisResult(answer=answer, evidence=evidence)