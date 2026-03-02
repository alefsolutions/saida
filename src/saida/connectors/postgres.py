from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine, text

from saida.connectors.base import BaseConnector


class PostgresConnector(BaseConnector):
    name = "postgres"

    def __init__(self, dsn: str, schema: str = "public", row_limit: int = 1000, engine: Engine | None = None):
        self.dsn = dsn
        self.schema = schema
        self.row_limit = row_limit
        self.engine = engine or create_engine(dsn, future=True, pool_pre_ping=True)

    @staticmethod
    def _sanitize_identifier(value: str) -> str:
        if not value or not value.replace("_", "a").isalnum() or value[0].isdigit():
            raise ValueError(f"Invalid SQL identifier: {value}")
        return value

    def discover(self) -> list[str]:
        sql = text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"schema": self.schema}).scalars().all()
        return [f"{self.schema}.{name}" for name in rows]

    def _parse_resource(self, resource_id: str) -> tuple[str, str]:
        if "." in resource_id:
            schema, table = resource_id.split(".", 1)
        else:
            schema, table = self.schema, resource_id
        return self._sanitize_identifier(schema), self._sanitize_identifier(table)

    def load(self, resource_id: str) -> Any:
        schema, table = self._parse_resource(resource_id)
        sql = text(f'SELECT * FROM "{schema}"."{table}" LIMIT :row_limit')
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"row_limit": self.row_limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_metadata(self) -> dict:
        return {
            "type": "postgres",
            "dsn": self.dsn,
            "schema": self.schema,
            "row_limit": self.row_limit,
        }
