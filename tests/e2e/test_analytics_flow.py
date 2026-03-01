from saida_core.core.runtime.container import build_container
from saida_core.core.runtime.config import RuntimeConfig
from saida_core.core.domain.query import Query


def test_analytics_flow_runs():
    cfg = RuntimeConfig(
        llm_provider="mock",
        embedding_provider="mock",
        vector_store_provider="mock",
        data_source_provider="local_fs",
    )
    app = build_container(cfg)
    result = app.run(Query(text="Analyze revenue decline in Q3", task_type="analytics"))
    assert result.answer
