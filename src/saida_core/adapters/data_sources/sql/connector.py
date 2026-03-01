from __future__ import annotations

from saida_core.core.contracts.data_source import DataSource


class SQLDataSource(DataSource):
    def fetch(self, query: str) -> list[dict]:
        # Placeholder for SQL execution.
        return [{"source": "sql", "query": query, "rows": 0}]