from __future__ import annotations

from dataclasses import asdict

from saida.analytics.engine import DuckDBAnalyticsEngine
from saida.benchmarking.runner import BenchmarkRunner
from saida.connectors.base import BaseConnector
from saida.embeddings.base import BaseEmbeddingProvider
from saida.embeddings.mock import MockEmbeddingProvider
from saida.embeddings.openai_provider import OpenAIEmbeddingProvider
from saida.ingestion.pipeline import IngestionPipeline
from saida.llm.base import BaseLLMProvider
from saida.llm.mock import MockLLMProvider
from saida.llm.openai_provider import OpenAILLMProvider
from saida.models.types import BenchmarkCase, BenchmarkReport, DatasetAsset, QueryResult
from saida.orchestration.langchain_orchestrator import LangChainOrchestrator
from saida.semantic.store import SemanticStore
from saida.storage.db import build_engine, build_session_factory, init_schema
from saida.storage.control_plane import ControlPlaneStore
from saida.storage.parquet_store import ParquetStore
from saida.utils.config import SaidaConfig


class SaidaAgent:
    def __init__(self, config: SaidaConfig | None = None):
        self.config = config or SaidaConfig()
        self.connectors: list[BaseConnector] = []

        self.engine = build_engine(self.config.control_plane_dsn)
        init_schema(self.engine)
        self.session_factory = build_session_factory(self.engine)

        self.control_plane = ControlPlaneStore(self.session_factory)
        self.parquet_store = ParquetStore(self.config.parquet_root)
        self.semantic_store = SemanticStore(self.session_factory)

        self.embedding_provider: BaseEmbeddingProvider = self._build_embedding_provider(self.config.embedding_provider)
        self.llm_provider: BaseLLMProvider = self._build_llm_provider(self.config.llm_provider)
        self.analytics_engine = DuckDBAnalyticsEngine()

        self.ingestion = IngestionPipeline(
            control_plane=self.control_plane,
            parquet_store=self.parquet_store,
            semantic_store=self.semantic_store,
            embedding_provider=self.embedding_provider,
        )
        self.orchestrator = LangChainOrchestrator(
            control_plane=self.control_plane,
            semantic_store=self.semantic_store,
            embedding_provider=self.embedding_provider,
            llm_provider=self.llm_provider,
            analytics_engine=self.analytics_engine,
        )

    def _build_embedding_provider(self, provider: str) -> BaseEmbeddingProvider:
        if provider == "openai":
            return OpenAIEmbeddingProvider()
        return MockEmbeddingProvider()

    def _build_llm_provider(self, provider: str) -> BaseLLMProvider:
        if provider == "openai":
            return OpenAILLMProvider()
        return MockLLMProvider()

    def add_connector(self, connector: BaseConnector) -> None:
        self.connectors.append(connector)

    def ingest_all(self) -> list[DatasetAsset]:
        assets: list[DatasetAsset] = []
        for connector in self.connectors:
            assets.extend(self.ingestion.ingest_connector(connector))
        return assets

    def sync(self) -> list[DatasetAsset]:
        return self.ingest_all()

    def query(self, prompt: str) -> QueryResult:
        return self.orchestrator.run_query(prompt)

    def run_benchmarks(self, cases: list[BenchmarkCase] | None = None) -> BenchmarkReport:
        benchmark_cases = cases or [
            BenchmarkCase(name="smoke-analytics", query="Show revenue summary by quarter", expected_rows_min=0),
            BenchmarkCase(name="smoke-semantic", query="What datasets are available?", expected_rows_min=0),
        ]
        runner = BenchmarkRunner(self.orchestrator)
        report = runner.run(benchmark_cases)
        self.control_plane.save_benchmark_report(asdict(report))
        return report
