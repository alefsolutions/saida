"""SQL source implementations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from saida.core.contracts import Dataset
from saida.exceptions import AdapterError
from saida.sources._helpers import build_dataset, load_context
from saida.sources.interfaces import SQLSourceInterface
from saida.sources.sql.introspection import discover_relational_schema
from saida.sources.sql.relational_access import RelationalAccessPlan, build_relational_access_plan
from saida.sources.sql.relational_schema import RelationalSchemaModel
from saida.sources.sql.rendering import render_relational_access_query


class SQLiteSource(SQLSourceInterface):
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
        self._query = query
        self.name = name
        self.context_path = Path(context_path) if context_path else None
        self._schema_model: RelationalSchemaModel | None = None

    @property
    def source_type(self) -> str:
        return "sqlite"

    @property
    def source_name(self) -> str:
        return self.name

    @property
    def query(self) -> str:
        return self._query

    def describe_source(self) -> dict[str, object]:
        return {"database_path": str(self.database_path), "query": self.query}

    def load_context(self) -> object:
        return load_context(self.context_path)

    def discover_schema(self) -> RelationalSchemaModel:
        """Inspect the SQLite database and return a canonical relational schema model."""
        if self._schema_model is None:
            if not self.database_path.exists():
                raise AdapterError(f"SQLite database not found: {self.database_path}")
            self._schema_model = discover_relational_schema(
                source_type=self.source_type,
                source_name=self.name,
                connection_factory=self._build_engine,
                metadata={"database_path": str(self.database_path)},
            )
        return self._schema_model

    def plan_access(
        self,
        *,
        required_columns: list[str],
        preferred_base_table: str | None = None,
        filters: dict[str, object] | None = None,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> RelationalAccessPlan:
        """Build a deterministic relational access plan for the requested fields."""
        return build_relational_access_plan(
            self.discover_schema(),
            required_columns=required_columns,
            preferred_base_table=preferred_base_table,
            filters=filters,
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset,
        )

    def render_access_query(self, access_plan: RelationalAccessPlan) -> str:
        """Render a relational access plan into executable SQLite SQL."""
        return render_relational_access_query(self.source_type, access_plan)

    def load_from_access_plan(self, access_plan: RelationalAccessPlan) -> Dataset:
        """Materialize a relational access plan into a canonical SAIDA dataset."""
        query = self.render_access_query(access_plan)
        return self._load_query_dataset(
            query=query,
            metadata={
                **self.describe_source(),
                "materialization_mode": "relational_access_plan",
                "generated_query": query,
                "required_tables": list(access_plan.required_tables),
                "access_plan": access_plan.to_dict(),
            },
        )

    def load_for_columns(
        self,
        *,
        required_columns: list[str],
        preferred_base_table: str | None = None,
        filters: dict[str, object] | None = None,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Dataset:
        """Plan and materialize a dataset for the requested relational fields."""
        return self.load_from_access_plan(
            self.plan_access(
                required_columns=required_columns,
                preferred_base_table=preferred_base_table,
                filters=filters,
                sort_by=sort_by,
                sort_direction=sort_direction,
                limit=limit,
                offset=offset,
            )
        )

    def load(self) -> Dataset:
        """Execute the SQL query and return a normalized dataset."""
        return self._load_query_dataset(query=self.query, metadata=self.describe_source())

    def _build_engine(self):
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.engine import URL
        except Exception as exc:  # pragma: no cover
            raise AdapterError("SQLAlchemy is required for SQLite relational schema discovery.") from exc
        return create_engine(URL.create("sqlite", database=str(self.database_path)))

    def _load_query_dataset(self, *, query: str, metadata: dict[str, object]) -> Dataset:
        if not self.database_path.exists():
            raise AdapterError(f"SQLite database not found: {self.database_path}")

        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.database_path)
            dataframe = pd.read_sql_query(query, connection)
        except Exception as exc:  # pragma: no cover
            raise AdapterError(f"Failed to load SQL query results from: {self.database_path}") from exc
        finally:
            if connection is not None:
                connection.close()

        return build_dataset(
            dataframe,
            name=self.name,
            source_type=self.source_type,
            metadata=metadata,
            context=self.load_context(),
        )


class SQLQuerySource(SQLSourceInterface):
    """Load SQL query results through a SQLAlchemy-compatible connection URI."""

    source_kind = "sql"

    def __init__(
        self,
        connection_uri: str,
        query: str,
        *,
        name: str = "sql_query",
        context_path: str | Path | None = None,
    ) -> None:
        self.connection_uri = connection_uri
        self._query = query
        self.name = name
        self.context_path = Path(context_path) if context_path else None
        self._schema_model: RelationalSchemaModel | None = None

    @property
    def source_type(self) -> str:
        return self.source_kind

    @property
    def source_name(self) -> str:
        return self.name

    @property
    def query(self) -> str:
        return self._query

    def describe_source(self) -> dict[str, object]:
        return {"connection_uri": self._masked_connection_uri(), "query": self.query}

    def load_context(self) -> object:
        return load_context(self.context_path)

    def discover_schema(self) -> RelationalSchemaModel:
        """Inspect the SQL source and return a canonical relational schema model."""
        if self._schema_model is None:
            self._schema_model = discover_relational_schema(
                source_type=self.source_type,
                source_name=self.name,
                connection_factory=self._build_engine,
                metadata={"connection_uri": self._masked_connection_uri()},
            )
        return self._schema_model

    def plan_access(
        self,
        *,
        required_columns: list[str],
        preferred_base_table: str | None = None,
        filters: dict[str, object] | None = None,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> RelationalAccessPlan:
        """Build a deterministic relational access plan for the requested fields."""
        return build_relational_access_plan(
            self.discover_schema(),
            required_columns=required_columns,
            preferred_base_table=preferred_base_table,
            filters=filters,
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset,
        )

    def render_access_query(self, access_plan: RelationalAccessPlan) -> str:
        """Render a relational access plan into executable SQL."""
        return render_relational_access_query(self.source_type, access_plan)

    def load_from_access_plan(self, access_plan: RelationalAccessPlan) -> Dataset:
        """Materialize a relational access plan into a canonical SAIDA dataset."""
        query = self.render_access_query(access_plan)
        return self._load_query_dataset(
            query=query,
            metadata={
                **self.describe_source(),
                "materialization_mode": "relational_access_plan",
                "generated_query": query,
                "required_tables": list(access_plan.required_tables),
                "access_plan": access_plan.to_dict(),
            },
        )

    def load_for_columns(
        self,
        *,
        required_columns: list[str],
        preferred_base_table: str | None = None,
        filters: dict[str, object] | None = None,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Dataset:
        """Plan and materialize a dataset for the requested relational fields."""
        return self.load_from_access_plan(
            self.plan_access(
                required_columns=required_columns,
                preferred_base_table=preferred_base_table,
                filters=filters,
                sort_by=sort_by,
                sort_direction=sort_direction,
                limit=limit,
                offset=offset,
            )
        )

    def load(self) -> Dataset:
        """Execute the SQL query through SQLAlchemy and return a normalized dataset."""
        return self._load_query_dataset(query=self.query, metadata=self.describe_source())

    def _build_engine(self):
        try:
            from sqlalchemy import create_engine
        except Exception as exc:  # pragma: no cover
            raise AdapterError(
                "SQLAlchemy is required for SQLQuerySource, PostgreSQLSource, and MySQLSource."
            ) from exc
        return create_engine(self.connection_uri)

    def _masked_connection_uri(self) -> str:
        if "://" not in self.connection_uri or "@" not in self.connection_uri:
            return self.connection_uri
        scheme, remainder = self.connection_uri.split("://", 1)
        credentials, target = remainder.split("@", 1)
        if ":" not in credentials:
            return self.connection_uri
        user, _password = credentials.split(":", 1)
        return f"{scheme}://{user}:***@{target}"

    def _load_query_dataset(self, *, query: str, metadata: dict[str, object]) -> Dataset:
        engine = None
        connection = None
        try:
            engine = self._build_engine()
            connection = engine.connect()
            dataframe = pd.read_sql_query(query, connection)
        except Exception as exc:  # pragma: no cover
            raise AdapterError(f"Failed to load SQL query results from: {self._masked_connection_uri()}") from exc
        finally:
            if connection is not None:
                connection.close()
            if engine is not None:
                engine.dispose()

        return build_dataset(
            dataframe,
            name=self.name,
            source_type=self.source_type,
            metadata=metadata,
            context=self.load_context(),
        )


class PostgreSQLSource(SQLQuerySource):
    """Load query results from a PostgreSQL connection URI."""

    source_kind = "postgresql"


class MySQLSource(SQLQuerySource):
    """Load query results from a MySQL connection URI."""

    source_kind = "mysql"


class SQLSource(SQLiteSource):
    """Compatibility alias preserving the legacy SQL source_type contract."""

    @property
    def source_type(self) -> str:
        return "sql"


SQLAdapter = SQLSource
SQLiteAdapter = SQLiteSource
SQLQueryAdapter = SQLQuerySource
PostgreSQLAdapter = PostgreSQLSource
MySQLAdapter = MySQLSource
