from __future__ import annotations

import os
from pathlib import Path

from saida_core.core.contracts.data_source import DataSource


class LocalFileSystemDataSource(DataSource):
    def __init__(self, root: str | None = None):
        self.root = Path(root or os.getenv("SAIDA_LOCAL_FS_ROOT", "./data"))

    def fetch(self, query: str) -> list[dict]:
        if not self.root.exists():
            return []

        results: list[dict] = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if query.lower() in path.name.lower():
                results.append({"source": "local_fs", "path": str(path), "match": "filename"})
        return results