"""SQLAlchemy-backed relational schema discovery helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from saida.exceptions import AdapterError
from saida.sources.relational_schema import (
    RelationalColumnModel,
    RelationalRelationshipModel,
    RelationalSchemaModel,
    RelationalTableModel,
)


def discover_relational_schema(
    *,
    source_type: str,
    source_name: str,
    connection_factory: Callable[[], Any],
    metadata: dict[str, Any] | None = None,
) -> RelationalSchemaModel:
    """Inspect a SQL-backed source and normalize its schema into SAIDA models."""
    try:
        from sqlalchemy import inspect
    except Exception as exc:  # pragma: no cover
        raise AdapterError("SQLAlchemy is required for relational SQL schema discovery.") from exc

    engine = None
    try:
        engine = connection_factory()
        inspector = inspect(engine)
        table_names = sorted(inspector.get_table_names())
        tables: list[RelationalTableModel] = []
        relationships: list[RelationalRelationshipModel] = []

        for table_name in table_names:
            primary_key = list(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
            columns: list[RelationalColumnModel] = []
            for column in inspector.get_columns(table_name):
                column_name = str(column["name"])
                columns.append(
                    RelationalColumnModel(
                        name=column_name,
                        data_type=_normalize_data_type(column.get("type")),
                        nullable=bool(column.get("nullable", True)),
                        is_primary_key=column_name in primary_key,
                        default=_stringify_default(column.get("default")),
                    )
                )

            tables.append(
                RelationalTableModel(
                    name=table_name,
                    columns=columns,
                    primary_key=primary_key,
                )
            )

            for foreign_key in inspector.get_foreign_keys(table_name):
                constrained_columns = list(foreign_key.get("constrained_columns") or [])
                referred_table = foreign_key.get("referred_table")
                referred_columns = list(foreign_key.get("referred_columns") or [])
                if not constrained_columns or not referred_table or not referred_columns:
                    continue
                relationship_name = str(
                    foreign_key.get("name")
                    or f"{table_name}__{'_'.join(constrained_columns)}__{referred_table}"
                )
                relationships.append(
                    RelationalRelationshipModel(
                        name=relationship_name,
                        left_table=table_name,
                        left_columns=constrained_columns,
                        right_table=str(referred_table),
                        right_columns=referred_columns,
                        relationship_type="many_to_one",
                    )
                )

        return RelationalSchemaModel(
            source_type=source_type,
            source_name=source_name,
            tables=tables,
            relationships=relationships,
            metadata={
                **dict(metadata or {}),
                "table_count": len(tables),
                "relationship_count": len(relationships),
                "introspection_backend": "sqlalchemy",
            },
        )
    except AdapterError:
        raise
    except Exception as exc:  # pragma: no cover
        raise AdapterError(f"Failed to discover relational schema for SQL source {source_name!r}.") from exc
    finally:
        if engine is not None:
            engine.dispose()


def _normalize_data_type(sql_type: object) -> str:
    if sql_type is None:
        return "unknown"
    return str(sql_type).lower()


def _stringify_default(value: object) -> str | None:
    if value is None:
        return None
    return str(value)

