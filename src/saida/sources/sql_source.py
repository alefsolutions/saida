"""SQL source implementation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from saida.sources._helpers import build_dataset, load_context
from saida.exceptions import AdapterError
from saida.core.contracts import Dataset


class SQLSource:
    """Load query results from a SQLite database into the SAIDA dataset schema."""

    def __init__(
        self,
        database_path: str | Path,
        query: str,
        *,
        name: str = "sql_query",
        context_path: str | Path | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.query = query
        self.name = name
        self.context_path = Path(context_path) if context_path else None

    def load(self) -> Dataset:
        """Execute the SQL query and return a normalized dataset."""
        if not self.database_path.exists():
            raise AdapterError(f"SQLite database not found: {self.database_path}")

        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.database_path)
            dataframe = pd.read_sql_query(self.query, connection)
        except Exception as exc:  # pragma: no cover
            raise AdapterError(f"Failed to load SQL query results from: {self.database_path}") from exc
        finally:
            if connection is not None:
                connection.close()

        context = load_context(self.context_path)
        return build_dataset(
            dataframe,
            name=self.name,
            source_type="sql",
            metadata={"database_path": str(self.database_path), "query": self.query},
            context=context,
        )


SQLAdapter = SQLSource
