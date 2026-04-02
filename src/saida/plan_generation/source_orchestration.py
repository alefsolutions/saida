"""Source-aware prompt orchestration helpers outside the core runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import difflib
from typing import Any

import pandas as pd

from saida.core.contracts import Dataset, DatasetProfile
from saida.sources import SchemaDiscoveryService
from saida.sources.interfaces import SQLSourceInterface, SourceInterface
from saida.sources.relational_schema import RelationalSchemaModel


@dataclass(slots=True)
class SourcePlanningContext:
    """Planning-time source view used before a final dataset is materialized."""

    dataset: Dataset
    profile: DatasetProfile
    source_name: str
    source_type: str
    schema_model: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceMaterializationResult:
    """Materialized dataset and metadata derived from a source-side request."""

    dataset: Dataset
    profile: DatasetProfile
    mode: str
    source_materialization_request: dict[str, Any] | None = None
    access_plan: dict[str, Any] | None = None
    generated_query: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PreparedSourceAnalysis:
    """Prepared source-aware analysis bundle used by the prompt frontend."""

    planning_context: SourcePlanningContext
    materialization: SourceMaterializationResult
    generation: Any
    prompt_contract: Any
    plan: Any


@dataclass(slots=True)
class SourceClarification:
    """Clarification guidance raised by source-side relational materialization."""

    reason: str
    message: str
    detail: str
    candidate_tables: list[str] = field(default_factory=list)
    suggested_qualified_fields: list[str] = field(default_factory=list)
    candidate_join_paths: list[str] = field(default_factory=list)
    candidate_columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_source_planning_context(
    source: SourceInterface,
    *,
    discovery: SchemaDiscoveryService | None = None,
) -> SourcePlanningContext:
    """Build the planning-time dataset/profile pair for a source."""
    active_discovery = discovery or SchemaDiscoveryService()

    if isinstance(source, SQLSourceInterface):
        schema_model = source.discover_schema()
        planning_dataset = _build_schema_planning_dataset(source, schema_model)
        planning_profile = active_discovery.profile(planning_dataset)
        return SourcePlanningContext(
            dataset=planning_dataset,
            profile=planning_profile,
            source_name=source.source_name,
            source_type=source.source_type,
            schema_model=schema_model.to_dict(),
            metadata={"planning_mode": "schema_discovery"},
        )

    dataset = source.load()
    profile = active_discovery.profile(dataset)
    return SourcePlanningContext(
        dataset=dataset,
        profile=profile,
        source_name=source.source_name,
        source_type=source.source_type,
        metadata={"planning_mode": "loaded_dataset"},
    )


def materialize_source_for_request(
    source: SourceInterface,
    request: object,
    *,
    discovery: SchemaDiscoveryService | None = None,
) -> SourceMaterializationResult:
    """Materialize the final dataset for one prompt-derived request."""
    active_discovery = discovery or SchemaDiscoveryService()
    source_materialization_request = getattr(request, "options", {}).get("source_materialization_request")

    if isinstance(source, SQLSourceInterface) and isinstance(source_materialization_request, dict):
        required_columns = list(source_materialization_request.get("required_columns") or [])
        preferred_base_table = source_materialization_request.get("preferred_base_table")
        mode = str(source_materialization_request.get("mode") or "analysis_frame")
        filters = source_materialization_request.get("filters")
        sort_by = source_materialization_request.get("sort_by") if mode == "tabular_recordset" else None
        sort_direction = source_materialization_request.get("sort_direction") if mode == "tabular_recordset" else None
        row_limit = source_materialization_request.get("row_limit") if mode == "tabular_recordset" else None
        access_plan = source.plan_access(
            required_columns=required_columns,
            preferred_base_table=preferred_base_table if isinstance(preferred_base_table, str) else None,
            filters=dict(filters) if isinstance(filters, dict) else None,
            sort_by=sort_by if isinstance(sort_by, str) else None,
            sort_direction=sort_direction if isinstance(sort_direction, str) else None,
            limit=int(row_limit) if isinstance(row_limit, int) else None,
        )
        query = source.render_access_query(access_plan)
        dataset = source.load_from_access_plan(access_plan)
        profile = active_discovery.profile(dataset)
        return SourceMaterializationResult(
            dataset=dataset,
            profile=profile,
            mode="relational_access_plan",
            source_materialization_request=dict(source_materialization_request),
            access_plan=access_plan.to_dict(),
            generated_query=query,
            metadata={"source_name": source.source_name, "source_type": source.source_type},
        )

    dataset = source.load()
    profile = active_discovery.profile(dataset)
    return SourceMaterializationResult(
        dataset=dataset,
        profile=profile,
        mode="direct_load",
        source_materialization_request=(
            dict(source_materialization_request) if isinstance(source_materialization_request, dict) else None
        ),
        metadata={"source_name": source.source_name, "source_type": source.source_type},
    )


def build_source_clarification(
    error: Exception,
    *,
    source_name: str,
    source_type: str,
    source_materialization_request: dict[str, Any] | None,
    schema_model: dict[str, Any] | None = None,
) -> SourceClarification:
    """Classify a source-side materialization failure into clarification guidance."""
    detail = str(error).strip() or "The relational source could not be materialized safely."
    lowered = detail.lower()
    required_columns = list(source_materialization_request.get("required_columns") or [])
    schema_insights = _schema_insights(schema_model)

    if "ambiguous across tables" in lowered:
        requested_column = _extract_quoted_value(detail)
        candidate_tables = _candidate_tables_for_column(schema_insights, requested_column) if requested_column else []
        if not candidate_tables:
            candidates = _extract_suffix_after(detail, "tables:")
            candidate_tables = [value.strip() for value in str(candidates or "").split(",") if value.strip()]
        suggestions = (
            [f"{table_name}.{requested_column}" for table_name in candidate_tables]
            if requested_column is not None
            else []
        )
        column_label = requested_column or "the requested field"
        suggestion_text = f" Try one of: {', '.join(suggestions)}." if suggestions else ""
        message = (
            f"Please clarify which table you mean for {column_label!r}. "
            f"The SQL source has multiple matching columns"
            f"{f': {', '.join(candidate_tables)}' if candidate_tables else '.'}"
            f"{suggestion_text}"
        )
        return SourceClarification(
            reason="ambiguous_relational_column",
            message=message,
            detail=detail,
            candidate_tables=candidate_tables,
            suggested_qualified_fields=suggestions,
        )

    if "no relational join path exists" in lowered:
        joined_columns = ", ".join(required_columns) if required_columns else "the requested fields"
        candidate_tables = sorted(
            {
                table_name
                for column_name in required_columns
                for table_name in _candidate_tables_for_column(schema_insights, column_name)
            }
        )
        suggestions = _qualified_field_suggestions(schema_insights, required_columns)
        join_paths = _reachable_join_paths(schema_insights, candidate_tables)
        join_path_text = (
            f" Available connected paths include: {', '.join(join_paths)}."
            if join_paths
            else ""
        )
        suggestion_text = f" Try qualified fields like: {', '.join(suggestions)}." if suggestions else ""
        return SourceClarification(
            reason="missing_relational_join_path",
            message=(
                "Please clarify which related tables should be analyzed together. "
                f"SAIDA could not find a safe relational join path for {joined_columns}."
                f"{suggestion_text}{join_path_text}"
            ),
            detail=detail,
            candidate_tables=candidate_tables,
            suggested_qualified_fields=suggestions,
            candidate_join_paths=join_paths,
        )

    if "was not found in the relational schema" in lowered or "does not exist in the relational schema" in lowered:
        requested_column = _extract_quoted_value(detail)
        suggestions = _closest_columns(schema_insights, requested_column)
        suggestion_text = f" Similar columns include: {', '.join(suggestions)}." if suggestions else ""
        return SourceClarification(
            reason="unknown_relational_column",
            message=(
                f"Please clarify the requested field{f' {requested_column!r}' if requested_column else ''}. "
                f"SAIDA could not resolve it from the {source_type} schema for {source_name}."
                f"{suggestion_text}"
            ),
            detail=detail,
            candidate_columns=suggestions,
        )

    if "preferred base table" in lowered:
        requested_table = _extract_quoted_value(detail)
        available_tables = list(schema_insights["table_names"])
        suggestion_text = f" Available tables include: {', '.join(available_tables)}." if available_tables else ""
        return SourceClarification(
            reason="unknown_relational_base_table",
            message=(
                f"Please clarify the base table{f' {requested_table!r}' if requested_table else ''}. "
                f"SAIDA could not find it in the {source_type} schema for {source_name}."
                f"{suggestion_text}"
            ),
            detail=detail,
            candidate_tables=available_tables,
        )

    return SourceClarification(
        reason="relational_source_clarification",
        message=(
            "Please clarify the relational data request. "
            f"SAIDA could not safely materialize the needed dataset from {source_name}."
        ),
        detail=detail,
        candidate_tables=list(schema_insights["table_names"]),
    )


def _build_schema_planning_dataset(source: SQLSourceInterface, schema_model: RelationalSchemaModel) -> Dataset:
    columns: list[str] = []
    values: dict[str, object] = {}
    duplicate_columns: list[str] = []

    for table in schema_model.tables:
        for column in table.columns:
            if column.name in values:
                duplicate_columns.append(column.name)
                continue
            columns.append(column.name)
            values[column.name] = _placeholder_value(column.data_type, column.name)

    if not columns:
        raise ValueError(f"SQL source {source.source_name!r} contains no columns to plan against.")

    dataframe = pd.DataFrame([{column_name: values[column_name] for column_name in columns}])
    context = source.load_context()
    metadata = {
        "planning_mode": "schema_discovery",
        "schema_table_count": len(schema_model.tables),
        "schema_relationship_count": len(schema_model.relationships),
    }
    if duplicate_columns:
        metadata["duplicate_schema_columns_omitted"] = sorted(dict.fromkeys(duplicate_columns))

    return Dataset(
        name=source.source_name,
        source_type=source.source_type,
        data=dataframe,
        metadata=metadata,
        context=context,
    )


def _placeholder_value(data_type: str, column_name: str) -> object:
    normalized = data_type.lower()
    lowered_name = column_name.lower()
    if any(token in normalized for token in ("int",)):
        return 1
    if any(token in normalized for token in ("real", "float", "double", "numeric", "decimal")):
        return 1.0
    if "bool" in normalized:
        return True
    if (
        "date" in normalized
        or "time" in normalized
        or lowered_name.endswith("_date")
        or lowered_name.endswith("_at")
        or lowered_name.endswith("_time")
    ):
        return "2026-01-01"
    if lowered_name.endswith("_id") or lowered_name == "id":
        return "sample_id"
    return "sample"


def _extract_quoted_value(text: str) -> str | None:
    parts = text.split("'")
    if len(parts) >= 3 and parts[1].strip():
        return parts[1].strip()
    return None


def _extract_suffix_after(text: str, marker: str) -> str | None:
    if marker not in text:
        return None
    suffix = text.split(marker, 1)[1].strip().rstrip(".")
    return suffix or None


def _schema_insights(schema_model: dict[str, Any] | None) -> dict[str, Any]:
    table_names: list[str] = []
    column_to_tables: dict[str, list[str]] = {}
    relationships: list[tuple[str, str]] = []
    all_columns: list[str] = []

    if not isinstance(schema_model, dict):
        return {
            "table_names": table_names,
            "column_to_tables": column_to_tables,
            "relationships": relationships,
            "all_columns": all_columns,
        }

    for table in schema_model.get("tables", []):
        if not isinstance(table, dict):
            continue
        table_name = table.get("name")
        if not isinstance(table_name, str) or not table_name:
            continue
        table_names.append(table_name)
        for column in table.get("columns", []):
            if not isinstance(column, dict):
                continue
            column_name = column.get("name")
            if not isinstance(column_name, str) or not column_name:
                continue
            column_to_tables.setdefault(column_name, []).append(table_name)
            all_columns.append(column_name)

    for relationship in schema_model.get("relationships", []):
        if not isinstance(relationship, dict):
            continue
        left_table = relationship.get("left_table")
        right_table = relationship.get("right_table")
        if isinstance(left_table, str) and isinstance(right_table, str):
            relationships.append((left_table, right_table))
            relationships.append((right_table, left_table))

    for tables in column_to_tables.values():
        tables.sort()

    return {
        "table_names": sorted(dict.fromkeys(table_names)),
        "column_to_tables": column_to_tables,
        "relationships": relationships,
        "all_columns": sorted(dict.fromkeys(all_columns)),
    }


def _candidate_tables_for_column(schema_insights: dict[str, Any], column_name: str | None) -> list[str]:
    if not isinstance(column_name, str) or not column_name:
        return []
    return list(schema_insights.get("column_to_tables", {}).get(column_name, []))


def _qualified_field_suggestions(schema_insights: dict[str, Any], required_columns: list[str]) -> list[str]:
    suggestions: list[str] = []
    for column_name in required_columns:
        for table_name in _candidate_tables_for_column(schema_insights, column_name):
            suggestion = f"{table_name}.{column_name}"
            if suggestion not in suggestions:
                suggestions.append(suggestion)
    return suggestions[:6]


def _reachable_join_paths(schema_insights: dict[str, Any], candidate_tables: list[str]) -> list[str]:
    if len(candidate_tables) < 2:
        return []
    adjacency: dict[str, list[str]] = {}
    for left_table, right_table in schema_insights.get("relationships", []):
        adjacency.setdefault(left_table, []).append(right_table)
    for neighbors in adjacency.values():
        neighbors.sort()

    paths: list[str] = []
    for start_table in candidate_tables:
        for end_table in candidate_tables:
            if start_table >= end_table:
                continue
            path = _shortest_table_path(adjacency, start_table, end_table)
            if path is not None:
                rendered = " -> ".join(path)
                if rendered not in paths:
                    paths.append(rendered)
    return paths[:4]


def _shortest_table_path(adjacency: dict[str, list[str]], start_table: str, end_table: str) -> list[str] | None:
    queue: list[list[str]] = [[start_table]]
    visited = {start_table}
    while queue:
        path = queue.pop(0)
        current = path[-1]
        if current == end_table:
            return path
        for next_table in adjacency.get(current, []):
            if next_table in visited:
                continue
            visited.add(next_table)
            queue.append([*path, next_table])
    return None


def _closest_columns(schema_insights: dict[str, Any], requested_column: str | None) -> list[str]:
    if not isinstance(requested_column, str) or not requested_column:
        return []
    return difflib.get_close_matches(requested_column, schema_insights.get("all_columns", []), n=5, cutoff=0.4)
