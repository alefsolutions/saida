from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine, text

from saida.connectors.base import BaseConnector


class MySQLConnector(BaseConnector):
    name = "mysql"

    def __init__(self, dsn: str, database: str | None = None, row_limit: int = 1000, engine: Engine | None = None):
        self.dsn = dsn
        self.database = database
        self.row_limit = row_limit
        self.engine = engine or create_engine(dsn, future=True, pool_pre_ping=True)

    @staticmethod
    def _sanitize_identifier(value: str) -> str:
        if not value or not value.replace("_", "a").isalnum() or value[0].isdigit():
            raise ValueError(f"Invalid SQL identifier: {value}")
        return value

    def _resolve_database(self) -> str:
        if self.database:
            return self._sanitize_identifier(self.database)
        with self.engine.connect() as conn:
            db = conn.execute(text("SELECT DATABASE()")).scalar_one_or_none()
        if not db:
            raise RuntimeError("MySQLConnector could not resolve database from DSN; set database explicitly.")
        return self._sanitize_identifier(str(db))

    def discover(self) -> list[str]:
        database = self._resolve_database()
        sql = text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :database
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"database": database}).scalars().all()
        return [f"{database}.{name}" for name in rows]

    def _parse_resource(self, resource_id: str) -> tuple[str, str]:
        if "." in resource_id:
            database, table = resource_id.split(".", 1)
        else:
            database, table = self._resolve_database(), resource_id
        return self._sanitize_identifier(database), self._sanitize_identifier(table)

    def load(self, resource_id: str) -> Any:
        database, table = self._parse_resource(resource_id)
        sql = text(f"SELECT * FROM `{database}`.`{table}` LIMIT :row_limit")
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"row_limit": self.row_limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_metadata(self) -> dict:
        return {
            "type": "mysql",
            "dsn": self.dsn,
            "database": self.database,
            "row_limit": self.row_limit,
        }
