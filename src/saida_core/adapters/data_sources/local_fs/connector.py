from __future__ import annotations

import os
from pathlib import Path

from saida_core.adapters.data_sources.local_fs.parser import parse_file
from saida_core.core.contracts.data_source import DataSource


class LocalFileSystemDataSource(DataSource):
    def __init__(self, root: str | None = None, max_file_chars: int = 20_000):
        self.root = Path(root or os.getenv("SAIDA_LOCAL_FS_ROOT", "./data"))
        self.max_file_chars = max_file_chars

    def fetch(self, query: str) -> list[dict]:
        if not self.root.exists():
            return []

        needle = query.lower().strip()
        results: list[dict] = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            parsed = parse_file(path, max_chars=self.max_file_chars)
            file_name_hit = needle and needle in path.name.lower()
            content_hit = needle and needle in parsed["text"].lower()

            if file_name_hit or content_hit:
                snippet = parsed["text"][:240]
                results.append(
                    {
                        "source": "local_fs",
                        "path": str(path),
                        "extension": parsed["extension"],
                        "size_bytes": path.stat().st_size,
                        "match": "content" if content_hit else "filename",
                        "snippet": snippet,
                    }
                )
        return results
