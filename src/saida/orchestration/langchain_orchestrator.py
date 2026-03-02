from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool

from saida.analytics.engine import DuckDBAnalyticsEngine
from saida.analytics.sql_planner import SQLPlanner
from saida.analytics.sql_validator import SQLValidator
from saida.embeddings.base import BaseEmbeddingProvider
from saida.llm.base import BaseLLMProvider
from saida.models.types import QueryResult
from saida.orchestration.llm_guard import enforce_no_unverified_numbers
from saida.orchestration.router import QueryRouter
from saida.semantic.store import SemanticStore
from saida.storage.control_plane import ControlPlaneStore


@dataclass(slots=True)
class GraphState:
    query: str
    route: str
    retrieved: list[dict[str, Any]]
    sql: str | None
    analytics_rows: list[dict[str, Any]]
    explanation: str


class LangChainOrchestrator:
    """LangChain runnable graph using explicit tools.

    Graph:
      route -> semantic_retrieve_tool -> analytics_query_tool -> llm_synthesis
    """

    def __init__(
        self,
        control_plane: ControlPlaneStore,
        semantic_store: SemanticStore,
        embedding_provider: BaseEmbeddingProvider,
        llm_provider: BaseLLMProvider,
        analytics_engine: DuckDBAnalyticsEngine,
    ):
        self.control_plane = control_plane
        self.semantic_store = semantic_store
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider
        self.analytics_engine = analytics_engine
        self.router = QueryRouter()
        self.sql_planner = SQLPlanner()
        self.sql_validator = SQLValidator()

        self.semantic_retrieve_tool = self._build_semantic_retrieve_tool()
        self.analytics_query_tool = self._build_analytics_query_tool()

        self.graph = (
            RunnableLambda(self._route_step)
            | RunnableLambda(self._semantic_step)
            | RunnableLambda(self._analytics_step)
            | RunnableLambda(self._synthesis_step)
        )

    def _build_semantic_retrieve_tool(self):
        @tool("semantic_retrieve")
        def semantic_retrieve(query: str) -> list[dict]:
            """Retrieve semantically relevant datasets and context for a user query."""
            q_emb = self.embedding_provider.embed([query])[0]
            rows = self.semantic_store.retrieve(q_emb, limit=5)
            out: list[dict] = []
            for item in rows:
                dataset = item["dataset"]
                out.append(
                    {
                        "dataset_id": dataset.dataset_id,
                        "source": dataset.source_resource_id,
                        "parquet_path": dataset.parquet_path,
                        "score": float(item["score"]),
                    }
                )
            return out

        return semantic_retrieve

    def _build_analytics_query_tool(self):
        @tool("analytics_query")
        def analytics_query(sql: str | None) -> dict:
            """Run deterministic DuckDB analytics from a pre-validated SQL plan."""
            if not sql:
                return {"sql": None, "rows": []}
            self.sql_validator.validate(sql)
            rows = self.analytics_engine.execute(sql)
            return {"sql": sql, "rows": rows}

        return analytics_query

    def _route_step(self, prompt: str) -> GraphState:
        return GraphState(
            query=prompt,
            route=self.router.classify(prompt),
            retrieved=[],
            sql=None,
            analytics_rows=[],
            explanation="",
        )

    def _semantic_step(self, state: GraphState) -> GraphState:
        retrieved = self.semantic_retrieve_tool.invoke({"query": state.query})
        state.retrieved = retrieved
        return state

    def _analytics_step(self, state: GraphState) -> GraphState:
        if state.route != "analytics":
            return state

        plan = self.sql_planner.plan(state.query, state.route, state.retrieved)
        if not plan.sql:
            state.sql = None
            state.analytics_rows = []
            return state

        result = self.analytics_query_tool.invoke({"sql": plan.sql})
        state.sql = result.get("sql")
        state.analytics_rows = result.get("rows", [])
        return state

    def _synthesis_step(self, state: GraphState) -> QueryResult:
        prompt = (
            "You are SAIDA. Use tool outputs only. "
            "Do not fabricate numeric values not present in analytics rows.\n"
            f"query={state.query}\n"
            f"route={state.route}\n"
            f"retrieved_context={[{'dataset_id': r.get('dataset_id'), 'source': r.get('source')} for r in state.retrieved]}\n"
            f"analytics_rows={state.analytics_rows}"
        )
        explanation = self.llm_provider.explain(prompt)
        if state.route == "analytics":
            enforce_no_unverified_numbers(state.query, state.analytics_rows, explanation)
        return QueryResult(
            query=state.query,
            route=state.route,
            sql=state.sql,
            analytics_rows=state.analytics_rows,
            retrieved_context=[
                {
                    "dataset_id": item.get("dataset_id"),
                    "source": item.get("source"),
                    "score": item.get("score"),
                }
                for item in state.retrieved
            ],
            explanation=explanation,
        )

    def run_query(self, prompt: str) -> QueryResult:
        return self.graph.invoke(prompt)
