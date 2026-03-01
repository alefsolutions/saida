from __future__ import annotations

from saida_core.core.contracts.tool import Tool
from saida_core.adapters.data_sources.sql.connector import SQLDataSource


class SQLQueryTool(Tool):
    name = "sql_query"

    def __init__(self):
        self.source = SQLDataSource()

    def run(self, payload: dict) -> dict:
        query = payload.get("query", "")
        return {"tool": self.name, "data": self.source.fetch(query)}