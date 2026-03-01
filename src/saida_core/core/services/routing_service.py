from __future__ import annotations

from saida_core.core.domain.query import Query


class RoutingService:
    def route(self, query: Query) -> str:
        lowered = query.text.lower()
        if any(k in lowered for k in ("revenue", "margin", "cost", "growth", "q1", "q2", "q3", "q4")):
            return "financial_analysis"
        return query.task_type