"""Reusable DAG graph templates for prompt-driven analysis planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from saida.core.contracts import AnalysisRequest, DatasetProfile, PlanStep, StepInputRef
from saida.exceptions import PlanningError


@dataclass(slots=True)
class GraphTemplateSpec:
    """Describes one reusable graph template available to the planner."""

    template_id: str
    label: str
    description: str
    supported_prompt_families: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "label": self.label,
            "description": self.description,
            "supported_prompt_families": list(self.supported_prompt_families),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class GraphTemplatePlan:
    """Compiled step sequence for one graph template instance."""

    template_id: str
    steps: list[PlanStep]
    final_output_ref: str


def build_default_graph_template_catalog() -> dict[str, GraphTemplateSpec]:
    """Return the built-in reusable graph template catalog."""

    templates = [
        GraphTemplateSpec(
            template_id="grouped_table_pipeline",
            label="Grouped Table Pipeline",
            description="Filter, group, aggregate, sort, and optionally limit a grouped tabular result.",
            supported_prompt_families=("grouped_entity_count", "grouped_metric_table"),
        ),
        GraphTemplateSpec(
            template_id="group_ranking_pipeline",
            label="Group Ranking Pipeline",
            description="Filter, group, aggregate, and rank grouped metric totals.",
            supported_prompt_families=("group_ranking", "representation_ranking"),
        ),
        GraphTemplateSpec(
            template_id="time_bucket_breakdown_pipeline",
            label="Time Bucket Breakdown Pipeline",
            description="Filter, derive time buckets, and aggregate across them.",
            supported_prompt_families=("time_bucket_counts", "time_bucket_breakdown"),
        ),
        GraphTemplateSpec(
            template_id="time_period_comparison_pipeline",
            label="Time Period Comparison Pipeline",
            description="Filter, derive time buckets, and compare adjacent periods.",
            supported_prompt_families=("time_period_comparison",),
        ),
        GraphTemplateSpec(
            template_id="row_ranking_pipeline",
            label="Row Ranking Pipeline",
            description="Filter and rank individual rows by one target measure.",
            supported_prompt_families=("row_ranking",),
        ),
        GraphTemplateSpec(
            template_id="tabular_retrieval_pipeline",
            label="Tabular Retrieval Pipeline",
            description="Filter, sort, limit, project, and paginate record retrieval requests.",
            supported_prompt_families=("tabular_record_retrieval",),
        ),
        GraphTemplateSpec(
            template_id="metric_aggregate_pipeline",
            label="Metric Aggregate Pipeline",
            description="Filter rows and reduce them to a scalar aggregate.",
            supported_prompt_families=("metric_aggregate", "distinct_value_count"),
        ),
        GraphTemplateSpec(
            template_id="exploratory_metric_overview_pipeline",
            label="Exploratory Metric Overview Pipeline",
            description="Build a shared-source exploratory graph with grouped, time, and diagnostic branches.",
            supported_prompt_families=("exploratory_metric_overview",),
        ),
    ]
    return {template.template_id: template for template in templates}


def _resolve_grouped_sort_column(request: AnalysisRequest, *, value_label: str) -> str | None:
    sort_by = request.options.get("sort_by")
    if sort_by is None:
        return value_label
    if sort_by == request.target and request.target is not None:
        return value_label
    return str(sort_by)


def _step_output_input(input_id: str, ref: str) -> StepInputRef:
    return StepInputRef(
        input_id=input_id,
        source_type="step_output",
        ref=ref,
        expected_kind="frame",
    )


def build_grouped_table_template(
    request: AnalysisRequest,
    *,
    aggregation: str,
    value_label: str,
    final_output_ref: str,
) -> GraphTemplatePlan:
    sort_direction = request.options.get("sort_direction", "desc")
    sort_by = _resolve_grouped_sort_column(request, value_label=value_label)
    limit = request.options.get("limit")
    steps = [
        PlanStep(
            step_id="group_frame",
            tool_family="duckdb",
            action="group_frame",
            parameters={
                "group_by": request.group_by,
                "filters": request.filters,
                "table_name": "grouped_source_rows",
            },
            description="Prepare grouped rows for downstream aggregation.",
            output_refs=["grouped_source_rows"],
        ),
        PlanStep(
            step_id="grouped_tabular_query",
            tool_family="duckdb",
            action="aggregate_frame",
            parameters={
                "target": request.target,
                "aggregation": aggregation,
                "value_label": value_label,
                "table_name": "grouped_tabular_query",
            },
            description="Aggregate the grouped rows into a tabular grouped result.",
            inputs=[_step_output_input("grouped_rows_input", "grouped_source_rows")],
            output_refs=["grouped_aggregate"],
        ),
    ]
    previous_output_ref = "grouped_aggregate"
    if sort_by is not None:
        steps.append(
            PlanStep(
                step_id="sort_grouped_result",
                tool_family="duckdb",
                action="sort_frame",
                parameters={
                    "sort_by": sort_by,
                    "sort_direction": sort_direction,
                    "table_name": "grouped_tabular_query",
                },
                description="Sort the grouped tabular result for presentation.",
                inputs=[_step_output_input("aggregate_rows_input", previous_output_ref)],
                output_refs=["sorted_grouped_result"],
            )
        )
        previous_output_ref = "sorted_grouped_result"
    if isinstance(limit, int) and limit > 0:
        steps.append(
            PlanStep(
                step_id="limit_grouped_result",
                tool_family="duckdb",
                action="limit_frame",
                parameters={
                    "limit": limit,
                    "table_name": "grouped_tabular_query",
                },
                description="Limit the grouped tabular result when a top-N size is requested.",
                inputs=[_step_output_input("sorted_rows_input", previous_output_ref)],
                output_refs=[final_output_ref],
            )
        )
    else:
        steps[-1].output_refs = [final_output_ref]
    return GraphTemplatePlan(
        template_id="grouped_table_pipeline",
        steps=steps,
        final_output_ref=final_output_ref,
    )


def build_group_ranking_template(request: AnalysisRequest) -> GraphTemplatePlan:
    ranking_limit = int(request.options.get("ranking_limit", 5))
    sort_direction = "asc" if request.options.get("ranking_direction") == "asc" else "desc"
    steps = [
        PlanStep(
            step_id="group_frame",
            tool_family="duckdb",
            action="group_frame",
            parameters={
                "group_by": request.group_by,
                "filters": request.filters,
                "table_name": "grouped_ranking_source",
            },
            description="Prepare grouped rows for grouped ranking.",
            output_refs=["grouped_ranking_source"],
        ),
        PlanStep(
            step_id="aggregate_group_ranking",
            tool_family="duckdb",
            action="aggregate_frame",
            parameters={
                "target": request.target,
                "aggregation": request.aggregation or "sum",
                "value_label": "target_total",
                "table_name": "ranked_breakdown",
            },
            description="Aggregate the grouped rows before ranking them.",
            inputs=[_step_output_input("grouped_rows_input", "grouped_ranking_source")],
            output_refs=["grouped_ranking_values"],
        ),
        PlanStep(
            step_id="ranked_breakdown",
            tool_family="duckdb",
            action="rank_frame",
            parameters={
                "sort_by": "target_total",
                "sort_direction": sort_direction,
                "limit": ranking_limit,
                "table_name": "ranked_breakdown",
            },
            description="Rank the grouped metric totals according to the requested ordering.",
            inputs=[_step_output_input("aggregate_rows_input", "grouped_ranking_values")],
            output_refs=["ranked_breakdown"],
        ),
    ]
    return GraphTemplatePlan(
        template_id="group_ranking_pipeline",
        steps=steps,
        final_output_ref="ranked_breakdown",
    )


def build_representation_ranking_template(request: AnalysisRequest) -> GraphTemplatePlan:
    ranking_limit = int(request.options.get("ranking_limit", 1))
    sort_direction = "asc" if request.options.get("ranking_direction") == "asc" else "desc"
    steps = [
        PlanStep(
            step_id="group_frame",
            tool_family="duckdb",
            action="group_frame",
            parameters={
                "group_by": [request.target],
                "filters": request.filters,
                "table_name": "representation_groups",
            },
            description="Prepare the requested representation groups.",
            output_refs=["representation_groups"],
        ),
        PlanStep(
            step_id="count_rows_by_group",
            tool_family="duckdb",
            action="aggregate_frame",
            parameters={
                "aggregation": "count",
                "value_label": "row_count",
                "table_name": "count_rows_by_group",
            },
            description="Count rows for each requested group.",
            inputs=[_step_output_input("grouped_rows_input", "representation_groups")],
            output_refs=["representation_counts"],
        ),
        PlanStep(
            step_id="sort_representation",
            tool_family="duckdb",
            action="sort_frame",
            parameters={
                "sort_by": "row_count",
                "sort_direction": sort_direction,
                "table_name": "count_rows_by_group",
            },
            description="Sort the grouped row counts for representation analysis.",
            inputs=[_step_output_input("count_rows_input", "representation_counts")],
            output_refs=["sorted_representation_counts"],
        ),
        PlanStep(
            step_id="limit_representation",
            tool_family="duckdb",
            action="limit_frame",
            parameters={
                "limit": ranking_limit,
                "table_name": "count_rows_by_group",
            },
            description="Return only the requested top or bottom representation rows.",
            inputs=[_step_output_input("sorted_rows_input", "sorted_representation_counts")],
            output_refs=["count_rows_by_group"],
        ),
    ]
    return GraphTemplatePlan(
        template_id="group_ranking_pipeline",
        steps=steps,
        final_output_ref="count_rows_by_group",
    )


def build_distinct_value_count_template(request: AnalysisRequest) -> GraphTemplatePlan:
    steps = [
        PlanStep(
            step_id="distinct_frame",
            tool_family="duckdb",
            action="distinct_frame",
            parameters={
                "selected_columns": [request.target],
                "filters": request.filters,
                "table_name": "distinct_values",
            },
            description="Project the distinct values for the requested dimension.",
            output_refs=["distinct_values"],
        ),
        PlanStep(
            step_id="distinct_value_count",
            tool_family="duckdb",
            action="row_count",
            parameters={},
            description="Count the distinct values from the upstream distinct frame.",
            inputs=[_step_output_input("distinct_values_input", "distinct_values")],
            output_refs=["distinct_value_count"],
        ),
    ]
    return GraphTemplatePlan(
        template_id="metric_aggregate_pipeline",
        steps=steps,
        final_output_ref="distinct_value_count",
    )


def build_time_bucket_breakdown_template(
    request: AnalysisRequest,
    profile: DatasetProfile,
) -> GraphTemplatePlan:
    bucket = str(request.options.get("time_bucket", "month"))
    grouped_columns = [bucket, *(request.group_by or [])]
    steps = [
        PlanStep(
            step_id="time_bucket_frame",
            tool_family="duckdb",
            action="time_bucket_frame",
            parameters={
                "time_column": profile.time_columns[0],
                "bucket": bucket,
                "filters": request.filters,
                "table_name": "time_bucket_frame",
            },
            description="Add explicit time bucket labels for downstream aggregation.",
            output_refs=["bucketed_rows"],
        ),
        PlanStep(
            step_id="time_bucket_breakdown",
            tool_family="duckdb",
            action="aggregate_frame",
            parameters={
                "target": request.target,
                "aggregation": request.aggregation or "sum",
                "group_by": grouped_columns,
                "value_label": "target_total",
                "table_name": "time_bucket_breakdown",
            },
            description="Aggregate the metric across derived time buckets and optional groups.",
            inputs=[_step_output_input("bucketed_rows_input", "bucketed_rows")],
            output_refs=["time_bucket_breakdown"],
        ),
    ]
    return GraphTemplatePlan(
        template_id="time_bucket_breakdown_pipeline",
        steps=steps,
        final_output_ref="time_bucket_breakdown",
    )


def build_time_bucket_counts_template(
    request: AnalysisRequest,
    profile: DatasetProfile,
) -> GraphTemplatePlan:
    bucket = str(request.options.get("time_bucket", "year"))
    steps = [
        PlanStep(
            step_id="time_bucket_frame",
            tool_family="duckdb",
            action="time_bucket_frame",
            parameters={
                "time_column": profile.time_columns[0],
                "bucket": bucket,
                "filters": request.filters,
                "table_name": "time_bucket_frame",
            },
            description="Add explicit time bucket labels for downstream row counting.",
            output_refs=["bucketed_rows"],
        ),
        PlanStep(
            step_id="time_bucket_counts",
            tool_family="duckdb",
            action="aggregate_frame",
            parameters={
                "aggregation": "count",
                "group_by": [bucket],
                "value_label": "row_count",
                "table_name": "time_bucket_counts",
            },
            description="Count rows across the derived time buckets.",
            inputs=[_step_output_input("bucketed_rows_input", "bucketed_rows")],
            output_refs=["time_bucket_counts"],
        ),
    ]
    return GraphTemplatePlan(
        template_id="time_bucket_breakdown_pipeline",
        steps=steps,
        final_output_ref="time_bucket_counts",
    )


def build_time_period_comparison_template(
    request: AnalysisRequest,
    profile: DatasetProfile,
) -> GraphTemplatePlan:
    bucket = str(request.options.get("time_bucket", "month"))
    comparison_action = "grouped_period_comparison" if request.group_by else "period_comparison"
    steps = [
        PlanStep(
            step_id="time_bucket_frame",
            tool_family="duckdb",
            action="time_bucket_frame",
            parameters={
                "time_column": profile.time_columns[0],
                "bucket": bucket,
                "filters": request.filters,
                "table_name": "time_bucket_frame",
            },
            description="Prepare bucketed time rows for downstream period comparison.",
            output_refs=["bucketed_rows"],
        ),
        PlanStep(
            step_id=comparison_action,
            tool_family="duckdb",
            action=comparison_action,
            parameters={
                "target": request.target,
                "group_by": request.group_by,
                "time_column": profile.time_columns[0],
                "time_reference": request.time_reference,
                "bucket": bucket,
                "aggregation": request.aggregation or "sum",
            },
            description="Compare adjacent derived time periods such as month, quarter, or year.",
            inputs=[_step_output_input("bucketed_rows_input", "bucketed_rows")],
            output_refs=[comparison_action],
        ),
    ]
    return GraphTemplatePlan(
        template_id="time_period_comparison_pipeline",
        steps=steps,
        final_output_ref=comparison_action,
    )


def build_row_ranking_template(request: AnalysisRequest) -> GraphTemplatePlan:
    ranking_limit = int(request.options.get("ranking_limit", 5))
    sort_direction = "asc" if request.options.get("ranking_direction") == "asc" else "desc"
    steps = [
        PlanStep(
            step_id="filter_frame",
            tool_family="duckdb",
            action="filter_frame",
            parameters={
                "filters": request.filters,
                "table_name": "ranking_source_rows",
            },
            description="Prepare the filtered source rows for row ranking.",
            output_refs=["ranking_source_rows"],
        ),
        PlanStep(
            step_id="ranked_rows",
            tool_family="duckdb",
            action="rank_frame",
            parameters={
                "sort_by": request.target,
                "sort_direction": sort_direction,
                "limit": ranking_limit,
                "table_name": "ranked_rows",
            },
            description="Rank individual rows by the requested numeric target.",
            inputs=[_step_output_input("ranking_source_input", "ranking_source_rows")],
            output_refs=["ranked_rows"],
        ),
    ]
    return GraphTemplatePlan(
        template_id="row_ranking_pipeline",
        steps=steps,
        final_output_ref="ranked_rows",
    )


def build_metric_aggregate_template(request: AnalysisRequest) -> GraphTemplatePlan:
    aggregation = request.aggregation or "sum"
    steps = [
        PlanStep(
            step_id="filter_frame",
            tool_family="duckdb",
            action="filter_frame",
            parameters={
                "filters": request.filters,
                "table_name": "metric_aggregate_source",
            },
            description="Prepare the filtered source rows for scalar aggregation.",
            output_refs=["metric_aggregate_source"],
        ),
        PlanStep(
            step_id="aggregate_value",
            tool_family="duckdb",
            action="aggregate_value",
            parameters={"target": request.target, "aggregation": aggregation},
            description="Reduce the prepared frame to the requested scalar aggregate.",
            inputs=[_step_output_input("metric_source_input", "metric_aggregate_source")],
            output_refs=["aggregate_value"],
        ),
    ]
    return GraphTemplatePlan(
        template_id="metric_aggregate_pipeline",
        steps=steps,
        final_output_ref="aggregate_value",
    )


def build_tabular_retrieval_template(request: AnalysisRequest) -> GraphTemplatePlan:
    selected_columns = [str(column) for column in request.options.get("selected_columns", []) if isinstance(column, str)]
    sort_by = request.options.get("sort_by")
    sort_direction = str(request.options.get("sort_direction", "asc"))
    limit = request.options.get("limit")
    page = int(request.options.get("page", 1))
    page_size = int(request.options.get("page_size", 50))

    steps: list[PlanStep] = [
        PlanStep(
            step_id="filter_frame",
            tool_family="duckdb",
            action="filter_frame",
            parameters={
                "filters": request.filters,
                "table_name": "filtered_rows",
            },
            description="Prepare the filtered source rows for tabular retrieval.",
            output_refs=["filtered_rows"],
        )
    ]

    previous_output_ref = "filtered_rows"
    if isinstance(sort_by, str) and sort_by:
        steps.append(
            PlanStep(
                step_id="sort_frame",
                tool_family="duckdb",
                action="sort_frame",
                parameters={
                    "sort_by": sort_by,
                    "sort_direction": sort_direction,
                    "table_name": "sorted_rows",
                },
                description="Sort the retrieval rows before pagination or limiting.",
                inputs=[_step_output_input("filtered_rows_input", previous_output_ref)],
                output_refs=["sorted_rows"],
            )
        )
        previous_output_ref = "sorted_rows"

    if isinstance(limit, int) and limit > 0:
        steps.append(
            PlanStep(
                step_id="limit_frame",
                tool_family="duckdb",
                action="limit_frame",
                parameters={
                    "limit": limit,
                    "table_name": "limited_rows",
                },
                description="Apply the requested row limit after sorting.",
                inputs=[_step_output_input("sorted_rows_input", previous_output_ref)],
                output_refs=["limited_rows"],
            )
        )
        previous_output_ref = "limited_rows"

    if selected_columns:
        steps.append(
            PlanStep(
                step_id="select_columns",
                tool_family="duckdb",
                action="select_columns",
                parameters={
                    "selected_columns": selected_columns,
                    "table_name": "projected_rows",
                },
                description="Project the requested columns for the tabular result.",
                inputs=[_step_output_input("rows_input", previous_output_ref)],
                output_refs=["projected_rows"],
            )
        )
        previous_output_ref = "projected_rows"

    steps.append(
        PlanStep(
            step_id="tabular_query",
            tool_family="duckdb",
            action="tabular_query",
            parameters={
                "selected_columns": None,
                "filters": None,
                "sort_by": None,
                "sort_direction": "asc",
                "limit": None,
                "page": page,
                "page_size": page_size,
            },
            description="Paginate and materialize the final tabular recordset.",
            inputs=[_step_output_input("rows_input", previous_output_ref)],
            output_refs=["tabular_query"],
        )
    )

    return GraphTemplatePlan(
        template_id="tabular_retrieval_pipeline",
        steps=steps,
        final_output_ref="tabular_query",
    )


def build_exploratory_metric_overview_template(
    request: AnalysisRequest,
    profile: DatasetProfile,
    task_type: str,
) -> GraphTemplatePlan:
    if request.target is None or request.target not in set(profile.measure_columns):
        raise PlanningError("Exploratory metric workflows require a numeric target.")

    time_bucket = str(request.options.get("time_bucket", "month"))
    steps: list[PlanStep] = [
        PlanStep(
            step_id="filter_frame",
            tool_family="duckdb",
            action="filter_frame",
            parameters={
                "filters": request.filters,
                "table_name": "overview_source_rows",
            },
            description="Prepare a reusable filtered source frame for the exploratory workflow.",
            output_refs=["overview_source_rows"],
        ),
        PlanStep(
            step_id="summary_metrics",
            tool_family="duckdb",
            action="dataset_summary",
            parameters={"target": request.target},
            description="Compute top-level dataset metrics.",
            inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
            output_refs=["summary_metrics"],
        ),
    ]

    if profile.time_columns:
        steps.extend(
            [
                PlanStep(
                    step_id="time_bucket_frame",
                    tool_family="duckdb",
                    action="time_bucket_frame",
                    parameters={
                        "time_column": profile.time_columns[0],
                        "bucket": time_bucket,
                        "table_name": "overview_time_bucket_frame",
                    },
                    description="Add reusable time bucket labels for downstream trend and period steps.",
                    inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                    output_refs=["overview_time_bucket_rows"],
                ),
                PlanStep(
                    step_id="time_trend",
                    tool_family="duckdb",
                    action="aggregate_frame",
                    parameters={
                        "target": request.target,
                        "group_by": [time_bucket],
                        "aggregation": request.aggregation or "sum",
                        "value_label": "target_total",
                        "table_name": "time_trend",
                    },
                    description="Compute the target trend over time.",
                    inputs=[_step_output_input("bucketed_rows_input", "overview_time_bucket_rows")],
                    output_refs=["time_trend"],
                ),
            ]
        )

    if request.time_reference and profile.time_columns:
        steps.append(
            PlanStep(
                step_id="period_comparison",
                tool_family="duckdb",
                action="period_comparison",
                parameters={
                    "target": request.target,
                    "time_column": profile.time_columns[0],
                    "time_reference": request.time_reference,
                    "bucket": time_bucket,
                    "aggregation": request.aggregation or "sum",
                },
                description="Compare the requested period against the previous comparable period.",
                inputs=[_step_output_input("time_series_input", "overview_time_bucket_rows")],
                output_refs=["period_comparison"],
            )
        )
        if request.group_by:
            steps.append(
                PlanStep(
                    step_id="grouped_period_comparison",
                    tool_family="duckdb",
                    action="grouped_period_comparison",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "time_column": profile.time_columns[0],
                        "time_reference": request.time_reference,
                        "bucket": time_bucket,
                        "aggregation": request.aggregation or "sum",
                    },
                    description="Compare grouped totals between adjacent periods.",
                    inputs=[_step_output_input("time_series_input", "overview_time_bucket_rows")],
                    output_refs=["grouped_period_comparison"],
                )
            )

    if request.group_by:
        steps.extend(
            [
                PlanStep(
                    step_id="group_frame",
                    tool_family="duckdb",
                    action="group_frame",
                    parameters={
                        "group_by": request.group_by,
                        "table_name": "overview_grouped_rows",
                    },
                    description="Prepare grouped exploratory rows for downstream grouped summaries.",
                    inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                    output_refs=["overview_grouped_rows"],
                ),
                PlanStep(
                    step_id="group_breakdown",
                    tool_family="duckdb",
                    action="aggregate_frame",
                    parameters={
                        "target": request.target,
                        "aggregation": request.aggregation or "sum",
                        "value_label": "target_total",
                        "table_name": "group_breakdown",
                    },
                    description="Break down the target metric by requested dimensions.",
                    inputs=[_step_output_input("grouped_rows_input", "overview_grouped_rows")],
                    output_refs=["group_breakdown"],
                ),
                PlanStep(
                    step_id="ranked_breakdown",
                    tool_family="duckdb",
                    action="rank_frame",
                    parameters={
                        "sort_by": "target_total",
                        "sort_direction": "desc",
                        "limit": 5,
                        "table_name": "ranked_breakdown",
                    },
                    description="Rank the largest grouped contributors.",
                    inputs=[_step_output_input("group_breakdown_input", "group_breakdown")],
                    output_refs=["ranked_breakdown"],
                ),
            ]
        )
        if request.time_reference and profile.time_columns:
            steps.append(
                PlanStep(
                    step_id="top_movers",
                    tool_family="duckdb",
                    action="top_movers",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "time_column": profile.time_columns[0],
                        "time_reference": request.time_reference,
                        "bucket": time_bucket,
                        "aggregation": request.aggregation or "sum",
                        "limit": 5,
                    },
                    description="Identify the largest grouped movers between adjacent periods.",
                    inputs=[_step_output_input("time_series_input", "overview_time_bucket_rows")],
                    output_refs=["top_movers"],
                )
            )
    elif task_type == "diagnostic" and profile.dimension_columns:
        primary_dimension = profile.dimension_columns[0]
        steps.extend(
            [
                PlanStep(
                    step_id="top_dimension_group_frame",
                    tool_family="duckdb",
                    action="group_frame",
                    parameters={
                        "group_by": [primary_dimension],
                        "table_name": "top_dimension_group_rows",
                    },
                    description="Prepare grouped rows for the leading dimension candidate.",
                    inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                    output_refs=["top_dimension_group_rows"],
                ),
                PlanStep(
                    step_id="top_dimension_breakdown",
                    tool_family="duckdb",
                    action="aggregate_frame",
                    parameters={
                        "target": request.target,
                        "aggregation": request.aggregation or "sum",
                        "value_label": "target_total",
                        "table_name": "group_breakdown",
                    },
                    description="Break down the target metric by the leading dimension candidate.",
                    inputs=[_step_output_input("top_dimension_group_input", "top_dimension_group_rows")],
                    output_refs=["top_dimension_breakdown"],
                ),
                PlanStep(
                    step_id="top_dimension_ranking",
                    tool_family="duckdb",
                    action="rank_frame",
                    parameters={
                        "sort_by": "target_total",
                        "sort_direction": "desc",
                        "limit": 5,
                        "table_name": "ranked_breakdown",
                    },
                    description="Rank the leading grouped contributors for the diagnostic workflow.",
                    inputs=[_step_output_input("top_dimension_breakdown_input", "top_dimension_breakdown")],
                    output_refs=["top_dimension_ranking"],
                ),
            ]
        )
        if request.time_reference and profile.time_columns:
            steps.append(
                PlanStep(
                    step_id="top_dimension_movers",
                    tool_family="duckdb",
                    action="top_movers",
                    parameters={
                        "target": request.target,
                        "group_by": [primary_dimension],
                        "time_column": profile.time_columns[0],
                        "time_reference": request.time_reference,
                        "bucket": time_bucket,
                        "aggregation": request.aggregation or "sum",
                        "limit": 5,
                    },
                    description="Identify the largest movers for the leading dimension candidate.",
                    inputs=[_step_output_input("time_series_input", "overview_time_bucket_rows")],
                    output_refs=["top_dimension_movers"],
                )
            )

    if task_type == "diagnostic" and profile.dimension_columns:
        steps.append(
            PlanStep(
                step_id="contribution_breakdown",
                tool_family="duckdb",
                action="contribution_breakdown",
                parameters={
                    "target": request.target,
                    "group_by": request.group_by or [profile.dimension_columns[0]],
                    "time_column": profile.time_columns[0] if profile.time_columns else None,
                    "time_reference": request.time_reference,
                    "bucket": time_bucket if profile.time_columns else None,
                    "aggregation": request.aggregation or "sum",
                },
                description="Estimate group-level contribution changes for the diagnostic workflow.",
                inputs=[
                    _step_output_input("time_series_input", "overview_time_bucket_rows")
                    if profile.time_columns
                    else _step_output_input("overview_source_input", "overview_source_rows")
                ],
                output_refs=["contribution_breakdown"],
            )
        )

    steps.extend(
        [
            PlanStep(
                step_id="missingness_summary",
                tool_family="stats",
                action="missingness_summary",
                parameters={},
                description="Summarize missing values by column.",
                inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                output_refs=["missingness_summary"],
            ),
            PlanStep(
                step_id="numeric_summary",
                tool_family="stats",
                action="numeric_summary",
                parameters={},
                description="Summarize numeric columns with deterministic statistics.",
                inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                output_refs=["numeric_summary"],
            ),
            PlanStep(
                step_id="distribution_summary",
                tool_family="stats",
                action="distribution_summary",
                parameters={"target": request.target},
                description="Summarize the target distribution.",
                inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                output_refs=["distribution_summary"],
            ),
            PlanStep(
                step_id="target_correlation",
                tool_family="stats",
                action="target_correlation",
                parameters={"target": request.target},
                description="Measure correlations between the target and other numeric columns.",
                inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                output_refs=["target_correlation"],
            ),
            PlanStep(
                step_id="anomaly_summary",
                tool_family="stats",
                action="anomaly_summary",
                parameters={
                    "target": request.target,
                    "time_column": profile.time_columns[0] if profile.time_columns else None,
                },
                description="Flag simple anomaly candidates for the target.",
                inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                output_refs=["anomaly_summary"],
            ),
        ]
    )

    if profile.time_columns:
        steps.append(
            PlanStep(
                step_id="time_series_diagnostics",
                tool_family="stats",
                action="time_series_diagnostics",
                parameters={"target": request.target, "time_column": profile.time_columns[0]},
                description="Compute simple time-series diagnostics for the target.",
                inputs=[_step_output_input("time_series_input", "overview_time_bucket_rows")],
                output_refs=["time_series_diagnostics"],
            )
        )
    candidate_dimensions = request.group_by or profile.dimension_columns
    comparison_dimension = [column for column in candidate_dimensions if column != request.target][:1]
    if comparison_dimension:
        steps.append(
            PlanStep(
                step_id="group_mean_comparison",
                tool_family="stats",
                action="group_mean_comparison",
                parameters={"target": request.target, "group_column": comparison_dimension[0]},
                description="Compare the target mean across the first available grouping dimension.",
                inputs=[_step_output_input("overview_source_input", "overview_source_rows")],
                output_refs=["group_mean_comparison"],
            )
        )

    return GraphTemplatePlan(
        template_id="exploratory_metric_overview_pipeline",
        steps=steps,
        final_output_ref="summary_metrics",
    )
