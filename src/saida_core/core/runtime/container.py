from __future__ import annotations

from saida_core.adapters.data_sources.local_fs.connector import LocalFileSystemDataSource
from saida_core.adapters.embeddings.openai_embeddings_adapter import OpenAIEmbeddingAdapter
from saida_core.adapters.llm.openai_adapter import OpenAILLMAdapter
from saida_core.adapters.vector_store.chroma_adapter import ChromaVectorStoreAdapter
from saida_core.pipelines.query.rag_pipeline import SimpleRetriever
from saida_core.core.runtime.config import RuntimeConfig
from saida_core.core.runtime.registry import ProviderRegistry
from saida_core.core.services.analytics_service import AnalyticsService
from saida_core.core.services.orchestration_service import OrchestrationService
from saida_core.core.services.retrieval_service import RetrievalService
from saida_core.core.services.routing_service import RoutingService


def build_container(config: RuntimeConfig | None = None) -> OrchestrationService:
    cfg = config or RuntimeConfig()
    registry = ProviderRegistry()

    registry.register("llm", "openai", OpenAILLMAdapter())
    registry.register("embeddings", "openai", OpenAIEmbeddingAdapter())
    registry.register("vector_store", "chroma", ChromaVectorStoreAdapter())
    registry.register("data_source", "local_fs", LocalFileSystemDataSource())

    llm = registry.get("llm", cfg.llm_provider)
    data_source = registry.get("data_source", cfg.data_source_provider)
    retriever = SimpleRetriever()

    routing = RoutingService()
    retrieval = RetrievalService(data_source=data_source, retriever=retriever)
    analytics = AnalyticsService(llm=llm)
    return OrchestrationService(routing=routing, retrieval=retrieval, analytics=analytics)