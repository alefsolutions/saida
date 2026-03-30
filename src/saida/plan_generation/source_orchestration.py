"""Source-aware prompt orchestration helpers outside the core runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
        access_plan = source.plan_access(
            required_columns=required_columns,
            preferred_base_table=preferred_base_table if isinstance(preferred_base_table, str) else None,
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
) -> SourceClarification:
    """Classify a source-side materialization failure into clarification guidance."""
    detail = str(error).strip() or "The relational source could not be materialized safely."
    lowered = detail.lower()
    required_columns = list(source_materialization_request.get("required_columns") or [])

    if "ambiguous across tables" in lowered:
        requested_column = _extract_quoted_value(detail)
        candidates = _extract_suffix_after(detail, "tables:")
        column_label = requested_column or "the requested field"
        message = (
            f"Please clarify which table you mean for {column_label!r}. "
            f"The SQL source has multiple matching columns{f': {candidates}' if candidates else '.'}"
        )
        return SourceClarification(
            reason="ambiguous_relational_column",
            message=message,
            detail=detail,
        )

    if "no relational join path exists" in lowered:
        joined_columns = ", ".join(required_columns) if required_columns else "the requested fields"
        return SourceClarification(
            reason="missing_relational_join_path",
            message=(
                "Please clarify which related tables should be analyzed together. "
                f"SAIDA could not find a safe relational join path for {joined_columns}."
            ),
            detail=detail,
        )

    if "was not found in the relational schema" in lowered or "does not exist in the relational schema" in lowered:
        requested_column = _extract_quoted_value(detail)
        return SourceClarification(
            reason="unknown_relational_column",
            message=(
                f"Please clarify the requested field{f' {requested_column!r}' if requested_column else ''}. "
                f"SAIDA could not resolve it from the {source_type} schema for {source_name}."
            ),
            detail=detail,
        )

    if "preferred base table" in lowered:
        requested_table = _extract_quoted_value(detail)
        return SourceClarification(
            reason="unknown_relational_base_table",
            message=(
                f"Please clarify the base table{f' {requested_table!r}' if requested_table else ''}. "
                f"SAIDA could not find it in the {source_type} schema for {source_name}."
            ),
            detail=detail,
        )

    return SourceClarification(
        reason="relational_source_clarification",
        message=(
            "Please clarify the relational data request. "
            f"SAIDA could not safely materialize the needed dataset from {source_name}."
        ),
        detail=detail,
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
    if "date" in normalized or "time" in normalized:
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
