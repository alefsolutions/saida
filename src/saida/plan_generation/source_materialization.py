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
    candidate_group_columns: list[str] = field(default_factory=list)
    candidate_entity_columns: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    sort_by: str | None = None
    sort_direction: str | None = None
    row_limit: int | None = None
    page: int | None = None
    page_size: int | None = None
    time_reference: dict[str, Any] | None = None
    requires_full_rows: bool = False
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
    requires_full_rows = False

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
        requires_full_rows = True

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
    identifier_columns = set(profile.identifier_columns)
    candidate_group_columns = [column for column in (request.group_by or []) if column in dimension_columns]
    candidate_entity_columns = [
        column
        for column in deduped_required_columns
        if column in dimension_columns or column in identifier_columns
    ]
    sort_direction = request.options.get("sort_direction")
    if not isinstance(sort_direction, str) or not sort_direction.strip():
        sort_direction = None

    return SourceMaterializationRequest(
        source_type=dataset.source_type,
        mode=_derive_materialization_mode(request),
        required_columns=deduped_required_columns,
        preferred_base_table=_preferred_base_table(request),
        candidate_measure_columns=[column for column in deduped_required_columns if column in measure_columns],
        candidate_dimension_columns=[column for column in deduped_required_columns if column in dimension_columns],
        candidate_time_columns=[column for column in deduped_required_columns if column in time_columns],
        candidate_group_columns=candidate_group_columns,
        candidate_entity_columns=candidate_entity_columns,
        filters=dict(request.filters or {}),
        sort_by=sort_by if isinstance(sort_by, str) and sort_by.strip() else None,
        sort_direction=sort_direction.lower() if isinstance(sort_direction, str) else None,
        row_limit=_derive_row_limit(request),
        page=_as_positive_int(request.options.get("page")),
        page_size=_as_positive_int(request.options.get("page_size")),
        time_reference=dict(request.time_reference) if request.time_reference is not None else None,
        requires_full_rows=requires_full_rows,
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


def _as_positive_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _derive_row_limit(request: AnalysisRequest) -> int | None:
    if _derive_materialization_mode(request) != "tabular_recordset":
        return None

    limit = _as_positive_int(request.options.get("limit"))
    page = _as_positive_int(request.options.get("page"))
    page_size = _as_positive_int(request.options.get("page_size"))
    pagination_window = page * page_size if page is not None and page_size is not None else None

    if limit is not None and pagination_window is not None:
        return min(limit, pagination_window)
    if limit is not None:
        return limit
    return pagination_window
