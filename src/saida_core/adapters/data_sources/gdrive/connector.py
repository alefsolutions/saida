from __future__ import annotations

from saida_core.core.contracts.data_source import DataSource


class GoogleDriveDataSource(DataSource):
    def fetch(self, query: str) -> list[dict]:
        # Placeholder for Google Drive API integration.
        return [{"source": "gdrive", "query": query, "files": []}]