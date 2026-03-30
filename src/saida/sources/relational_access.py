"""Deterministic relational access planning for SQL-backed source adapters."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

from saida.exceptions import AdapterError
from saida.sources.relational_schema import (
    RelationalRelationshipModel,
    RelationalSchemaModel,
    RelationalTableModel,
)


@dataclass(slots=True)
class RelationalProjectionSpec:
    """One projected output field selected from a relational table."""

    source_table: str
    source_column: str
    output_name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelationalJoinSpec:
    """One relational join edge in a materialization access plan."""

    relationship_name: str
    left_table: str
    left_columns: list[str]
    right_table: str
    right_columns: list[str]
    join_type: str = "inner"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelationalAccessPlan:
    """Deterministic source-side access plan for materializing a relational dataset."""

    base_table: str
    required_tables: list[str] = field(default_factory=list)
    projections: list[RelationalProjectionSpec] = field(default_factory=list)
    joins: list[RelationalJoinSpec] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_relational_access_plan(
    schema: RelationalSchemaModel,
    *,
    required_columns: list[str],
    preferred_base_table: str | None = None,
) -> RelationalAccessPlan:
    """Build a deterministic relational access plan from a discovered schema."""
    if not required_columns:
        raise AdapterError("Relational access planning requires at least one requested column.")

    tables_by_name = {table.name: table for table in schema.tables}
    if not tables_by_name:
        raise AdapterError("Relational schema discovery returned no tables to plan against.")

    relationship_lookup = {relationship.name: relationship for relationship in schema.relationships}
    column_candidates = _build_column_candidate_index(schema)

    projection_bindings: list[tuple[str, str, str]] = []
    for requested_column in required_columns:
        source_table, source_column, output_name = _resolve_projection_binding(
            requested_column,
            column_candidates,
            preferred_base_table=preferred_base_table,
        )
        projection_bindings.append((source_table, source_column, output_name))

    if preferred_base_table is not None and preferred_base_table not in tables_by_name:
        raise AdapterError(f"Preferred base table {preferred_base_table!r} was not found in the relational schema.")

    projection_tables = {output_name: source_table for source_table, _source_column, output_name in projection_bindings}
    base_table = preferred_base_table or _choose_base_table(schema, projection_tables)
    required_tables = sorted({base_table, *(source_table for source_table, _source_column, _output_name in projection_bindings)})

    joins = _build_join_plan(base_table, required_tables, schema, relationship_lookup)
    projections = [
        RelationalProjectionSpec(
            source_table=source_table,
            source_column=source_column,
            output_name=output_name,
        )
        for source_table, source_column, output_name in projection_bindings
    ]

    return RelationalAccessPlan(
        base_table=base_table,
        required_tables=required_tables,
        projections=projections,
        joins=joins,
        metadata={
            "requested_columns": list(required_columns),
            "preferred_base_table": preferred_base_table,
        },
    )


def _build_column_candidate_index(schema: RelationalSchemaModel) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for table in schema.tables:
        for column in table.columns:
            index.setdefault(column.name, []).append(table.name)
    for candidates in index.values():
        candidates.sort()
    return index


def _resolve_projection_binding(
    requested_column: str,
    column_candidates: dict[str, list[str]],
    *,
    preferred_base_table: str | None,
) -> tuple[str, str, str]:
    if "." in requested_column:
        table_name, column_name = requested_column.split(".", 1)
        candidates = column_candidates.get(column_name, [])
        if table_name not in candidates:
            raise AdapterError(
                f"Requested qualified column {requested_column!r} does not exist in the relational schema."
            )
        return table_name, column_name, column_name

    candidates = column_candidates.get(requested_column, [])
    if not candidates:
        raise AdapterError(f"Requested column {requested_column!r} was not found in the relational schema.")
    if len(candidates) == 1:
        return candidates[0], requested_column, requested_column
    if preferred_base_table in candidates:
        return str(preferred_base_table), requested_column, requested_column
    joined_candidates = ", ".join(candidates)
    raise AdapterError(
        f"Requested column {requested_column!r} is ambiguous across tables: {joined_candidates}. "
        "Qualify the column or provide a preferred base table."
    )


def _choose_base_table(schema: RelationalSchemaModel, projection_tables: dict[str, str]) -> str:
    projected_counts: dict[str, int] = {}
    for table_name in projection_tables.values():
        projected_counts[table_name] = projected_counts.get(table_name, 0) + 1

    scored_tables = []
    for table in schema.tables:
        score = (
            projected_counts.get(table.name, 0),
            _fact_like_score(table, schema.relationships),
            len(table.columns),
            -len(table.name),
        )
        scored_tables.append((score, table.name))

    scored_tables.sort(key=lambda item: (item[0], item[1]))
    return scored_tables[-1][1]


def _fact_like_score(table: RelationalTableModel, relationships: list[RelationalRelationshipModel]) -> int:
    outgoing_relationships = sum(1 for relationship in relationships if relationship.left_table == table.name)
    numeric_like_columns = sum(1 for column in table.columns if _is_numeric_like(column.data_type))
    return (outgoing_relationships * 10) + numeric_like_columns


def _is_numeric_like(data_type: str) -> bool:
    normalized = data_type.lower()
    return any(token in normalized for token in ("int", "numeric", "decimal", "real", "float", "double"))


def _build_join_plan(
    base_table: str,
    required_tables: list[str],
    schema: RelationalSchemaModel,
    relationship_lookup: dict[str, RelationalRelationshipModel],
) -> list[RelationalJoinSpec]:
    if len(required_tables) <= 1:
        return []

    joins_by_name: dict[str, RelationalJoinSpec] = {}
    for target_table in required_tables:
        if target_table == base_table:
            continue
        path = _shortest_relationship_path(base_table, target_table, schema.relationships)
        if path is None:
            raise AdapterError(
                f"No relational join path exists between base table {base_table!r} and required table {target_table!r}."
            )
        for relationship_name in path:
            relationship = relationship_lookup[relationship_name]
            joins_by_name.setdefault(
                relationship.name,
                RelationalJoinSpec(
                    relationship_name=relationship.name,
                    left_table=relationship.left_table,
                    left_columns=list(relationship.left_columns),
                    right_table=relationship.right_table,
                    right_columns=list(relationship.right_columns),
                ),
            )

    return sorted(joins_by_name.values(), key=lambda join: join.relationship_name)


def _shortest_relationship_path(
    start_table: str,
    end_table: str,
    relationships: list[RelationalRelationshipModel],
) -> list[str] | None:
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for relationship in relationships:
        adjacency.setdefault(relationship.left_table, []).append((relationship.right_table, relationship.name))
        adjacency.setdefault(relationship.right_table, []).append((relationship.left_table, relationship.name))

    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1]))

    queue: deque[tuple[str, list[str]]] = deque([(start_table, [])])
    visited = {start_table}
    while queue:
        current_table, path = queue.popleft()
        if current_table == end_table:
            return path
        for next_table, relationship_name in adjacency.get(current_table, []):
            if next_table in visited:
                continue
            visited.add(next_table)
            queue.append((next_table, [*path, relationship_name]))
    return None
