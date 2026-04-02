"""Deterministic relational access planning for SQL-backed source adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import heapq
from typing import Any

from saida.exceptions import AdapterError
from saida.sources.sql.relational_schema import (
    RelationalRelationshipModel,
    RelationalSchemaModel,
)
from saida.sources.sql.relational_semantics import RelationalTableSemantics, infer_relational_table_semantics


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
class RelationalFilterSpec:
    """One source-side filter predicate bound to a relational column."""

    source_table: str
    source_column: str
    predicate: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelationalOrderSpec:
    """One source-side ordering directive bound to a relational column."""

    source_table: str
    source_column: str
    direction: str = "asc"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelationalAccessPlan:
    """Deterministic source-side access plan for materializing a relational dataset."""

    base_table: str
    required_tables: list[str] = field(default_factory=list)
    projections: list[RelationalProjectionSpec] = field(default_factory=list)
    joins: list[RelationalJoinSpec] = field(default_factory=list)
    filters: list[RelationalFilterSpec] = field(default_factory=list)
    order_by: list[RelationalOrderSpec] = field(default_factory=list)
    limit: int | None = None
    offset: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_relational_access_plan(
    schema: RelationalSchemaModel,
    *,
    required_columns: list[str],
    preferred_base_table: str | None = None,
    filters: dict[str, Any] | None = None,
    sort_by: str | None = None,
    sort_direction: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> RelationalAccessPlan:
    """Build a deterministic relational access plan from a discovered schema."""
    if not required_columns:
        raise AdapterError("Relational access planning requires at least one requested column.")

    tables_by_name = {table.name: table for table in schema.tables}
    if not tables_by_name:
        raise AdapterError("Relational schema discovery returned no tables to plan against.")

    relationship_lookup = {relationship.name: relationship for relationship in schema.relationships}
    column_candidates = _build_column_candidate_index(schema)
    table_semantics = infer_relational_table_semantics(schema)

    if preferred_base_table is not None and preferred_base_table not in tables_by_name:
        raise AdapterError(f"Preferred base table {preferred_base_table!r} was not found in the relational schema.")

    effective_preferred_base_table = preferred_base_table
    if isinstance(sort_by, str) and sort_by.strip():
        sort_table, _sort_column, _sort_output_name = _resolve_projection_binding(
            sort_by,
            column_candidates,
            preferred_base_table=preferred_base_table,
        )
        if effective_preferred_base_table is None:
            effective_preferred_base_table = sort_table

    projection_bindings: list[tuple[str, str, str]] = []
    for requested_column in required_columns:
        source_table, source_column, output_name = _resolve_projection_binding(
            requested_column,
            column_candidates,
            preferred_base_table=effective_preferred_base_table,
        )
        projection_bindings.append((source_table, source_column, output_name))

    filter_specs: list[RelationalFilterSpec] = []
    for filter_column, predicate in (filters or {}).items():
        source_table, source_column, _output_name = _resolve_projection_binding(
            str(filter_column),
            column_candidates,
            preferred_base_table=effective_preferred_base_table,
        )
        filter_specs.append(
            RelationalFilterSpec(
                source_table=source_table,
                source_column=source_column,
                predicate=predicate,
            )
        )

    order_specs: list[RelationalOrderSpec] = []
    if isinstance(sort_by, str) and sort_by.strip():
        source_table, source_column, _output_name = _resolve_projection_binding(
            sort_by,
            column_candidates,
            preferred_base_table=effective_preferred_base_table,
        )
        order_specs.append(
            RelationalOrderSpec(
                source_table=source_table,
                source_column=source_column,
                direction=(sort_direction or "asc").lower(),
            )
        )

    (
        base_table,
        base_table_reason,
        base_table_candidates,
    ) = _choose_base_table(
        schema,
        projection_bindings,
        table_semantics=table_semantics,
        preferred_base_table=effective_preferred_base_table,
    )
    required_tables = sorted(
        {
            base_table,
            *(source_table for source_table, _source_column, _output_name in projection_bindings),
            *(filter_spec.source_table for filter_spec in filter_specs),
            *(order_spec.source_table for order_spec in order_specs),
        }
    )

    joins, join_analysis = _build_join_plan(
        base_table,
        required_tables,
        schema,
        relationship_lookup,
        table_semantics=table_semantics,
    )
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
        filters=filter_specs,
        order_by=order_specs,
        limit=limit,
        offset=offset,
        metadata={
            "requested_columns": list(required_columns),
            "preferred_base_table": preferred_base_table,
            "effective_preferred_base_table": effective_preferred_base_table,
            "requested_filters": dict(filters or {}),
            "requested_sort_by": sort_by,
            "requested_sort_direction": (sort_direction or "asc").lower() if sort_by else None,
            "requested_limit": limit,
            "requested_offset": offset,
            "table_roles": {
                table_name: semantics.role
                for table_name, semantics in sorted(table_semantics.items())
            },
            "table_role_reasons": {
                table_name: list(semantics.reasons)
                for table_name, semantics in sorted(table_semantics.items())
            },
            "base_table_reason": base_table_reason,
            "base_table_candidates": base_table_candidates,
            "join_analysis": join_analysis,
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


def _choose_base_table(
    schema: RelationalSchemaModel,
    projection_bindings: list[tuple[str, str, str]],
    *,
    table_semantics: dict[str, RelationalTableSemantics],
    preferred_base_table: str | None,
) -> tuple[str, str, list[dict[str, Any]]]:
    projection_counts: dict[str, int] = {}
    measure_like_counts: dict[str, int] = {}
    for table_name, _source_column, output_name in projection_bindings:
        projection_counts[table_name] = projection_counts.get(table_name, 0) + 1
        if _is_measure_like(output_name):
            measure_like_counts[table_name] = measure_like_counts.get(table_name, 0) + 1

    candidate_entries: list[dict[str, Any]] = []
    best_score: tuple[int, int, int, int, int] | None = None
    best_table_name: str | None = None

    for table in schema.tables:
        semantics = table_semantics[table.name]
        role_bonus = _role_bonus(semantics.role)
        projection_count = projection_counts.get(table.name, 0)
        measure_count = measure_like_counts.get(table.name, 0)
        score = (
            projection_count * 100,
            measure_count * 40,
            role_bonus,
            len(table.columns),
            -len(table.name),
        )
        candidate_entries.append(
            {
                "table_name": table.name,
                "role": semantics.role,
                "score": list(score),
                "projected_column_count": projection_count,
                "measure_like_projection_count": measure_count,
            }
        )
        if best_score is None or score > best_score:
            best_score = score
            best_table_name = table.name

    candidate_entries.sort(key=lambda entry: (entry["score"], entry["table_name"]))
    chosen_table = preferred_base_table or str(best_table_name)
    chosen_semantics = table_semantics[chosen_table]
    reason = (
        f"Selected base table {chosen_table!r} with role {chosen_semantics.role!r} "
        f"and projected-column priority."
    )
    if preferred_base_table is not None:
        reason = f"Used caller-provided preferred base table {preferred_base_table!r}."
    return chosen_table, reason, candidate_entries


def _role_bonus(role: str) -> int:
    return {
        "fact": 30,
        "dimension": 15,
        "bridge": 5,
        "view": 0,
        "unknown": 0,
    }.get(role, 0)


def _is_measure_like(column_name: str) -> bool:
    lowered = column_name.lower()
    return any(token in lowered for token in ("total", "amount", "revenue", "sales", "cost", "price", "quantity"))


def _build_join_plan(
    base_table: str,
    required_tables: list[str],
    schema: RelationalSchemaModel,
    relationship_lookup: dict[str, RelationalRelationshipModel],
    *,
    table_semantics: dict[str, RelationalTableSemantics],
) -> tuple[list[RelationalJoinSpec], list[dict[str, Any]]]:
    if len(required_tables) <= 1:
        return [], []

    joins_by_name: dict[str, RelationalJoinSpec] = {}
    join_analysis_by_name: dict[str, dict[str, Any]] = {}
    for target_table in required_tables:
        if target_table == base_table:
            continue
        path, path_cost, edge_analysis = _best_relationship_path(
            start_table=base_table,
            end_table=target_table,
            relationships=schema.relationships,
            table_semantics=table_semantics,
            preferred_intermediate_tables=set(required_tables) - {base_table, target_table},
        )
        if path is None:
            raise AdapterError(
                f"No relational join path exists between base table {base_table!r} and required table {target_table!r}."
            )
        for relationship_name, edge_details in zip(path, edge_analysis, strict=True):
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
            join_analysis_by_name.setdefault(
                relationship.name,
                {
                    "relationship_name": relationship.name,
                    "target_table": target_table,
                    "direction": edge_details["direction"],
                    "fanout_risk": edge_details["fanout_risk"],
                    "cost": edge_details["cost"],
                    "from_table": edge_details["from_table"],
                    "to_table": edge_details["to_table"],
                    "left_role": table_semantics[relationship.left_table].role,
                    "right_role": table_semantics[relationship.right_table].role,
                },
            )
        join_analysis_by_name[f"path::{target_table}"] = {
            "target_table": target_table,
            "path": path,
            "path_cost": path_cost,
            "preferred_intermediate_tables": sorted(set(required_tables) - {base_table, target_table}),
        }

    join_entries = sorted(joins_by_name.values(), key=lambda join: join.relationship_name)
    analysis_entries = [
        join_analysis_by_name[join.relationship_name]
        for join in join_entries
    ]
    analysis_entries.extend(
        sorted(
            (
                details
                for key, details in join_analysis_by_name.items()
                if key.startswith("path::")
            ),
            key=lambda details: str(details["target_table"]),
        )
    )
    return join_entries, analysis_entries


def _best_relationship_path(
    start_table: str,
    end_table: str,
    relationships: list[RelationalRelationshipModel],
    *,
    table_semantics: dict[str, RelationalTableSemantics],
    preferred_intermediate_tables: set[str],
) -> tuple[list[str] | None, int | None, list[dict[str, Any]]]:
    adjacency: dict[str, list[tuple[str, str, str]]] = {}
    for relationship in relationships:
        adjacency.setdefault(relationship.left_table, []).append(
            (relationship.right_table, relationship.name, "child_to_parent")
        )
        adjacency.setdefault(relationship.right_table, []).append(
            (relationship.left_table, relationship.name, "parent_to_child")
        )

    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1], item[2]))

    queue: list[tuple[int, int, str, str, list[str], list[dict[str, Any]]]] = [
        (0, 0, start_table, start_table, [], [])
    ]
    best_cost_by_table: dict[str, tuple[int, int]] = {start_table: (0, 0)}

    while queue:
        total_cost, hop_count, _signature, current_table, path, edge_analysis = heapq.heappop(queue)
        if current_table == end_table:
            return path, total_cost, edge_analysis
        for next_table, relationship_name, direction in adjacency.get(current_table, []):
            edge_cost = _relationship_edge_cost(
                next_table=next_table,
                direction=direction,
                role=table_semantics.get(next_table, RelationalTableSemantics(next_table, "unknown", 0, 0, 0, 0, 0)).role,
                preferred_intermediate=next_table in preferred_intermediate_tables,
                is_terminal=next_table == end_table,
            )
            next_cost = total_cost + edge_cost
            next_hop_count = hop_count + 1
            best_known = best_cost_by_table.get(next_table)
            if best_known is not None and (next_cost, next_hop_count) >= best_known:
                continue
            best_cost_by_table[next_table] = (next_cost, next_hop_count)
            next_edge_analysis = [
                *edge_analysis,
                {
                    "relationship_name": relationship_name,
                    "from_table": current_table,
                    "to_table": next_table,
                    "direction": direction,
                    "fanout_risk": direction == "parent_to_child",
                    "cost": edge_cost,
                },
            ]
            heapq.heappush(
                queue,
                (
                    next_cost,
                    next_hop_count,
                    "|".join([*path, relationship_name]),
                    next_table,
                    [*path, relationship_name],
                    next_edge_analysis,
                ),
            )
    return None, None, []


def _relationship_edge_cost(
    *,
    next_table: str,
    direction: str,
    role: str,
    preferred_intermediate: bool,
    is_terminal: bool,
) -> int:
    cost = 10
    if direction == "parent_to_child":
        cost += 20
    if role == "bridge":
        cost += 8
    elif role == "view":
        cost += 4
    if preferred_intermediate and not is_terminal:
        cost -= 6
    if direction == "child_to_parent" and role == "dimension":
        cost -= 2
    return max(cost, 1)
