from saida_core.core.domain.query import Query
from saida_core.core.services.routing_service import RoutingService


def test_routes_financial_query():
    svc = RoutingService()
    assert svc.route(Query(text="Why did revenue drop in Q3?")) == "financial_analysis"