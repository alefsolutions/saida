"""Prompt-side relational source materialization helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from saida.core.contracts import AnalysisRequest, Dataset, DatasetProfile

RELATIONAL_SOURCE_TYPES = {"sqlite", "sql", "postgresql", "mysql"}


@dataclass(slots=True)
class SourceMaterializationRequest:
    """Prompt-facing description of the fields a relational source should materialize."""

    source_type: str
    mode: str
    required_columns: list[str] = field(default_factory=list)
    preferred_base_table: str | None = None
    candidate_measure_columns: list[str] = field(default_factory=list)
    candidate_dimension_columns: list[str] = field(default_factory=list)
    candidate_time_columns: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_source_materialization_request(
    request: AnalysisRequest,
    dataset: Dataset,
    profile: DatasetProfile,
) -> SourceMaterializationRequest | None:
    """Return a source-materialization request for SQL-backed datasets."""
    if dataset.source_type not in RELATIONAL_SOURCE_TYPES:
        return None

    required_columns: list[str] = []
    reasons: list[str] = []
    selected_columns = request.options.get("selected_columns", [])

    if isinstance(selected_columns, list) and selected_columns:
        required_columns.extend(str(column) for column in selected_columns if isinstance(column, str))
        reasons.append("selected_columns")

    if request.target:
        required_columns.append(request.target)
        reasons.append("target")

    if request.group_by:
        required_columns.extend(str(column) for column in request.group_by if isinstance(column, str))
        reasons.append("group_by")

    if request.filters:
        required_columns.extend(str(column_name) for column_name in request.filters)
        reasons.append("filters")

    if request.intent_name in {"tabular_query", "row_ranking"} and not selected_columns:
        required_columns.extend(column.name for column in profile.columns)
        reasons.append("full_row_projection")

    sort_by = request.options.get("sort_by")
    if isinstance(sort_by, str) and sort_by.strip():
        required_columns.append(sort_by)
        reasons.append("sort")

    feature_columns = request.options.get("feature_columns", [])
    if isinstance(feature_columns, list) and feature_columns:
        required_columns.extend(str(column) for column in feature_columns if isinstance(column, str))
        reasons.append("features")

    comparison_columns = request.options.get("comparison_columns", [])
    if isinstance(comparison_columns, list) and comparison_columns:
        required_columns.extend(str(column) for column in comparison_columns if isinstance(column, str))
        reasons.append("comparison_columns")

    if (
        request.intent_name in {"time_coverage", "time_bucket_counts", "time_bucket_breakdown", "time_period_comparison"}
        or request.time_reference
    ) and profile.time_columns:
        required_columns.append(profile.time_columns[0])
        reasons.append("time_context")

    deduped_required_columns = _dedupe(required_columns)
    if not deduped_required_columns:
        return None

    measure_columns = set(profile.measure_columns)
    dimension_columns = set(profile.dimension_columns)
    time_columns = set(profile.time_columns)

    return SourceMaterializationRequest(
        source_type=dataset.source_type,
        mode=_derive_materialization_mode(request),
        required_columns=deduped_required_columns,
        preferred_base_table=_preferred_base_table(request),
        candidate_measure_columns=[column for column in deduped_required_columns if column in measure_columns],
        candidate_dimension_columns=[column for column in deduped_required_columns if column in dimension_columns],
        candidate_time_columns=[column for column in deduped_required_columns if column in time_columns],
        reasons=_dedupe(reasons),
    )


def _derive_materialization_mode(request: AnalysisRequest) -> str:
    if request.intent_name == "tabular_query":
        return "tabular_recordset"
    if request.intent_name == "grouped_tabular_query":
        return "grouped_table"
    if request.intent_name in {"row_count", "existence_check"}:
        return "filtered_rowset"
    if request.intent_name in {"time_coverage", "time_bucket_counts", "time_bucket_breakdown", "time_period_comparison"}:
        return "time_series"
    if request.options.get("statistical_test"):
        return "statistical_frame"
    return "analysis_frame"


def _preferred_base_table(request: AnalysisRequest) -> str | None:
    preferred_base_table = request.options.get("preferred_base_table")
    if isinstance(preferred_base_table, str) and preferred_base_table.strip():
        return preferred_base_table
    return None


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped
