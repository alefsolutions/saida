from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SQLPlan:
    sql: str | None
    parquet_path: str | None
    reason: str


class SQLPlanner:
    """Deterministic SQL planner for analytics queries."""

    def plan(self, query: str, route: str, retrieved_context: list[dict[str, Any]]) -> SQLPlan:
        if route != "analytics":
            return SQLPlan(sql=None, parquet_path=None, reason="non_analytics_route")

        top = next((r for r in retrieved_context if r.get("parquet_path")), None)
        if top is None:
            return SQLPlan(sql=None, parquet_path=None, reason="no_parquet_dataset")

        parquet_path = str(top["parquet_path"])
        escaped = parquet_path.replace("'", "''")
        query_l = query.lower()

        # Deterministic, bounded SQL templates only.
        if "count" in query_l:
            sql = f"SELECT COUNT(*) AS row_count FROM read_parquet('{escaped}')"
            return SQLPlan(sql=sql, parquet_path=parquet_path, reason="count_template")
        if "avg" in query_l or "average" in query_l:
            sql = f"SELECT * FROM read_parquet('{escaped}') LIMIT 25"
            return SQLPlan(sql=sql, parquet_path=parquet_path, reason="avg_fallback_preview")
        if "sum" in query_l:
            sql = f"SELECT * FROM read_parquet('{escaped}') LIMIT 25"
            return SQLPlan(sql=sql, parquet_path=parquet_path, reason="sum_fallback_preview")

        sql = f"SELECT * FROM read_parquet('{escaped}') LIMIT 25"
        return SQLPlan(sql=sql, parquet_path=parquet_path, reason="default_preview")
