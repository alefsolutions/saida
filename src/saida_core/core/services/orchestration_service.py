from __future__ import annotations

from saida_core.core.domain.query import Query
from saida_core.core.domain.result import AnalysisResult
from saida_core.core.services.retrieval_service import RetrievalService
from saida_core.core.services.analytics_service import AnalyticsService
from saida_core.core.services.routing_service import RoutingService


class OrchestrationService:
    def __init__(self, routing: RoutingService, retrieval: RetrievalService, analytics: AnalyticsService):
        self.routing = routing
        self.retrieval = retrieval
        self.analytics = analytics

    def run(self, query: Query) -> AnalysisResult:
        task_type = self.routing.route(query)
        bundle = self.retrieval.collect(query.text)
        return self.analytics.analyze(query.text, bundle, task_type)