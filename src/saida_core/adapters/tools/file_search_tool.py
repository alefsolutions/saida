from __future__ import annotations

from saida_core.core.contracts.tool import Tool
from saida_core.adapters.data_sources.local_fs.connector import LocalFileSystemDataSource


class FileSearchTool(Tool):
    name = "file_search"

    def __init__(self):
        self.source = LocalFileSystemDataSource()

    def run(self, payload: dict) -> dict:
        query = payload.get("query", "")
        return {"tool": self.name, "data": self.source.fetch(query)}