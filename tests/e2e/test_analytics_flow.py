from saida_core.core.runtime.container import build_container
from saida_core.core.domain.query import Query


def test_analytics_flow_runs():
    app = build_container()
    result = app.run(Query(text="Analyze revenue decline in Q3", task_type="analytics"))
    assert result.answer