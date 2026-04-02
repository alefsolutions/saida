"""SQLAlchemy-backed relational schema discovery helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from saida.exceptions import AdapterError
from saida.sources.sql.relational_schema import (
    RelationalColumnModel,
    RelationalIndexModel,
    RelationalRelationshipModel,
    RelationalSchemaModel,
    RelationalTableModel,
    RelationalUniqueConstraintModel,
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
        default_schema_name = getattr(inspector, "default_schema_name", None)
        schema_names = sorted(inspector.get_schema_names() or [])
        schema_argument = default_schema_name if default_schema_name not in {None, ""} else None
        table_names = sorted(inspector.get_table_names(schema=schema_argument))
        view_names = sorted(inspector.get_view_names(schema=schema_argument))
        tables: list[RelationalTableModel] = []
        relationships: list[RelationalRelationshipModel] = []

        for table_name in table_names:
            primary_key = list(inspector.get_pk_constraint(table_name, schema=schema_argument).get("constrained_columns") or [])
            columns: list[RelationalColumnModel] = []
            for column in inspector.get_columns(table_name, schema=schema_argument):
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

            unique_constraints = [
                RelationalUniqueConstraintModel(
                    name=constraint.get("name"),
                    columns=list(constraint.get("column_names") or []),
                    metadata=_filter_metadata(
                        constraint,
                        excluded_keys={"name", "column_names"},
                    ),
                )
                for constraint in inspector.get_unique_constraints(table_name, schema=schema_argument)
                if constraint.get("column_names")
            ]
            indexes = [
                RelationalIndexModel(
                    name=index.get("name"),
                    columns=list(index.get("column_names") or []),
                    unique=bool(index.get("unique", False)),
                    metadata=_filter_metadata(
                        index,
                        excluded_keys={"name", "column_names", "unique"},
                    ),
                )
                for index in inspector.get_indexes(table_name, schema=schema_argument)
                if index.get("column_names")
            ]
            tables.append(
                RelationalTableModel(
                    name=table_name,
                    schema_name=default_schema_name,
                    columns=columns,
                    primary_key=primary_key,
                    unique_constraints=unique_constraints,
                    indexes=indexes,
                    metadata={"table_kind": "table"},
                )
            )

            for foreign_key in inspector.get_foreign_keys(table_name, schema=schema_argument):
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
                        metadata={
                            "foreign_key_name": foreign_key.get("name"),
                            "referred_schema": foreign_key.get("referred_schema"),
                            "is_required": all(
                                next((column.nullable for column in columns if column.name == column_name), True) is False
                                for column_name in constrained_columns
                            ),
                        },
                    )
                )

        for view_name in view_names:
            columns = [
                RelationalColumnModel(
                    name=str(column["name"]),
                    data_type=_normalize_data_type(column.get("type")),
                    nullable=bool(column.get("nullable", True)),
                    default=_stringify_default(column.get("default")),
                )
                for column in inspector.get_columns(view_name, schema=schema_argument)
            ]
            tables.append(
                RelationalTableModel(
                    name=view_name,
                    schema_name=default_schema_name,
                    columns=columns,
                    is_view=True,
                    view_definition=_stringify_default(inspector.get_view_definition(view_name, schema=schema_argument)),
                    metadata={"table_kind": "view"},
                )
            )

        return RelationalSchemaModel(
            source_type=source_type,
            source_name=source_name,
            tables=sorted(tables, key=lambda table: (table.schema_name or "", table.name)),
            relationships=sorted(relationships, key=lambda relationship: relationship.name),
            metadata={
                **dict(metadata or {}),
                "table_count": len(table_names),
                "view_count": len(view_names),
                "relationship_count": len(relationships),
                "default_schema_name": default_schema_name,
                "schema_names": schema_names,
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


def _filter_metadata(payload: dict[str, Any], *, excluded_keys: set[str]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if key not in excluded_keys and value not in (None, [], {})
    }
