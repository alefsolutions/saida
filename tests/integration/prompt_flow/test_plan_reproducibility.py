from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from saida import PromptAnalysisFrontend
from saida.core.contracts import AnalysisPlan, AnalysisRequest, Dataset
from saida.plan_generation import build_default_prompt_family_catalog
from tests.helpers.factories import build_recurring_time_dataset, build_sales_dataset, build_support_dataset, json_safe
from tests.helpers.result_helpers import normalized_result_value


_UNSET = object()

_EXPLORATORY_METRIC_OVERVIEW_ACTIONS = (
    "filter_frame",
    "dataset_summary",
    "time_bucket_frame",
    "aggregate_frame",
    "missingness_summary",
    "numeric_summary",
    "distribution_summary",
    "target_correlation",
    "anomaly_summary",
    "time_series_diagnostics",
    "group_mean_comparison",
)

_METRIC_AGGREGATE_ACTIONS = ("filter_frame", "aggregate_value")


@dataclass(frozen=True, slots=True)
class ReproducibilityCase:
    family_id: str
    dataset_factory: Callable[[], Dataset]
    prompts: tuple[str, ...]
    expected_intent_name: str | None = None
    expected_task_type: str = "descriptive"
    expected_target: str | None = None
    expected_aggregation: str | None = None
    expected_group_by: tuple[str, ...] = ()
    expected_filters: dict[str, Any] | None = None
    expected_option_subset: dict[str, Any] = field(default_factory=dict)
    expected_step_actions: tuple[str, ...] = ()
    expected_primary_result_name: str = ""
    expected_primary_logical_shape: str | None = None
    expected_primary_value: Any = _UNSET


def _request_signature(request: AnalysisRequest) -> dict[str, Any]:
    options = {
        key: value
        for key, value in request.options.items()
        if key not in {"dataset", "nlp_backend", "llm_status", "candidate_capabilities"}
    }
    return {
        "prompt_family": request.prompt_family,
        "intent_name": request.intent_name,
        "task_type_hint": request.task_type_hint,
        "target": request.target,
        "aggregation": request.aggregation,
        "filters": request.filters,
        "group_by": list(request.group_by or []),
        "time_reference": request.time_reference,
        "options": options,
    }


def _plan_signature(plan: AnalysisPlan) -> dict[str, Any]:
    return {
        "task_type": plan.task_type,
        "warnings": list(plan.warnings),
        "steps": [
            {
                "step_id": step.step_id,
                "tool_family": step.tool_family,
                "action": step.action,
                "parameters": step.parameters,
            }
            for step in plan.steps
        ],
    }


def _result_signature(result: Any) -> dict[str, Any]:
    payload = result.to_debug_response_dict()
    return {
        "status": payload["status"],
        "result": payload["result"],
        "tables": payload["tables"],
        "warnings": payload["warnings"],
        "metric_lookup": payload["meta"].get("metric_lookup"),
    }


_REPRODUCIBILITY_CASES = [
    ReproducibilityCase(
        family_id="exploratory_metric_overview",
        dataset_factory=build_sales_dataset,
        prompts=("Show revenue", "Display revenue", "Give me revenue"),
        expected_intent_name=None,
        expected_target="revenue",
        expected_step_actions=_EXPLORATORY_METRIC_OVERVIEW_ACTIONS,
        expected_primary_result_name="summary_metrics",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="metric_aggregate",
        dataset_factory=build_sales_dataset,
        prompts=("What is the average revenue?", "Give me the mean revenue", "What is revenue on average?"),
        expected_intent_name=None,
        expected_target="revenue",
        expected_aggregation="mean",
        expected_step_actions=_METRIC_AGGREGATE_ACTIONS,
        expected_primary_result_name="aggregate_value",
        expected_primary_logical_shape="scalar",
        expected_primary_value=105.0,
    ),
    ReproducibilityCase(
        family_id="column_inventory",
        dataset_factory=build_sales_dataset,
        prompts=(
            "What are the columns in the sales data?",
            "Which columns are in the sales data?",
            "Show the columns in the sales data",
        ),
        expected_intent_name="column_inventory",
        expected_step_actions=("column_inventory",),
        expected_primary_result_name="column_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="measure_inventory",
        dataset_factory=build_sales_dataset,
        prompts=("Available metrics?", "What are the available metrics?", "List the measure columns"),
        expected_intent_name="measure_inventory",
        expected_step_actions=("measure_inventory",),
        expected_primary_result_name="measure_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="dimension_inventory",
        dataset_factory=build_sales_dataset,
        prompts=("Available dimensions?", "What are the available dimensions?", "List the dimension columns"),
        expected_intent_name="dimension_inventory",
        expected_step_actions=("dimension_inventory",),
        expected_primary_result_name="dimension_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="column_type_inventory",
        dataset_factory=build_support_dataset,
        prompts=(
            "What are the data types of each field or column in the data?",
            "What is the schema of this data?",
            "Show the field types in the data",
        ),
        expected_intent_name="column_type_inventory",
        expected_step_actions=("column_type_inventory",),
        expected_primary_result_name="column_type_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="column_type_lookup",
        dataset_factory=build_support_dataset,
        prompts=(
            "What is the data type of the created_at field in dataset?",
            "What type is created_at?",
            "What is the type of created_at?",
        ),
        expected_intent_name="column_type_inventory",
        expected_target="created_at",
        expected_step_actions=("column_type_inventory",),
        expected_primary_result_name="column_type_inventory",
        expected_primary_logical_shape="table",
        expected_primary_value={
            "column_name": "created_at",
            "dtype": "datetime",
            "nullable": False,
            "null_count": 0,
            "null_ratio": 0.0,
            "unique_count": 7,
            "distinct_ratio": 1.0,
            "semantic_role": "time",
        },
    ),
    ReproducibilityCase(
        family_id="numeric_column_inventory",
        dataset_factory=build_support_dataset,
        prompts=("Which columns are numeric?", "What numeric columns are in the dataset?", "List the numeric fields"),
        expected_intent_name="numeric_column_inventory",
        expected_step_actions=("numeric_column_inventory",),
        expected_primary_result_name="numeric_column_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="categorical_column_inventory",
        dataset_factory=build_support_dataset,
        prompts=(
            "Which fields are categorical?",
            "What categorical columns are in the dataset?",
            "List the categorical fields",
        ),
        expected_intent_name="categorical_column_inventory",
        expected_step_actions=("categorical_column_inventory",),
        expected_primary_result_name="categorical_column_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="time_column_inventory",
        dataset_factory=build_support_dataset,
        prompts=("Which fields are dates?", "List the time columns", "Show the datetime fields"),
        expected_intent_name="time_column_inventory",
        expected_step_actions=("time_column_inventory",),
        expected_primary_result_name="time_column_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="missing_value_inventory",
        dataset_factory=build_support_dataset,
        prompts=(
            "Which columns have missing values?",
            "List columns with missing values",
            "Show columns with missing values",
        ),
        expected_intent_name="missing_value_inventory",
        expected_step_actions=("missing_value_inventory",),
        expected_primary_result_name="missing_value_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="identifier_inventory",
        dataset_factory=build_support_dataset,
        prompts=(
            "Which columns are likely identifiers?",
            "List likely identifier columns",
            "Show likely identifier columns",
        ),
        expected_intent_name="identifier_inventory",
        expected_step_actions=("identifier_inventory",),
        expected_primary_result_name="identifier_inventory",
        expected_primary_logical_shape="table",
    ),
        ReproducibilityCase(
            family_id="high_cardinality_inventory",
            dataset_factory=build_support_dataset,
            prompts=(
                "Which columns have many unique values?",
                "List columns with many unique values",
                "Which fields have many unique values?",
            ),
            expected_intent_name="high_cardinality_inventory",
            expected_step_actions=("high_cardinality_inventory",),
            expected_primary_result_name="high_cardinality_inventory",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="distinct_value_listing",
        dataset_factory=build_support_dataset,
        prompts=("Give me a list of all teams", "List all teams", "What are the different team categories in the data?"),
        expected_intent_name="distinct_values",
        expected_target="team",
        expected_step_actions=("distinct_values",),
        expected_primary_result_name="distinct_values",
        expected_primary_logical_shape="table",
    ),
    ReproducibilityCase(
        family_id="distinct_value_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many unique team values are there?",
            "How many different team types are there?",
            "How many distinct team categories are there?",
        ),
        expected_intent_name="distinct_value_count",
        expected_target="team",
        expected_step_actions=("distinct_frame", "row_count"),
        expected_primary_result_name="distinct_value_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=2,
    ),
    ReproducibilityCase(
        family_id="row_count",
        dataset_factory=build_sales_dataset,
        prompts=("How many data rows do we have?", "What is the row count?", "Count rows"),
        expected_intent_name="row_count",
        expected_aggregation="count",
        expected_step_actions=("row_count",),
        expected_primary_result_name="row_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=6,
    ),
    ReproducibilityCase(
        family_id="row_count",
        dataset_factory=build_recurring_time_dataset,
        prompts=(
            "How many rows are in Q1?",
            "Count rows for quarter 1",
            "What is the row count for the first quarter?",
        ),
        expected_intent_name="row_count",
        expected_aggregation="count",
        expected_filters={"created_at": {"op": "quarter_eq", "value": 1, "label": "q1"}},
        expected_step_actions=("row_count",),
        expected_primary_result_name="row_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=16,
    ),
    ReproducibilityCase(
        family_id="column_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many columns are in the dataset?",
            "How many fields does the dataset have?",
            "Total number of columns in the dataset",
        ),
        expected_intent_name="column_count",
        expected_step_actions=("column_count",),
        expected_primary_result_name="column_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=7,
    ),
    ReproducibilityCase(
        family_id="numeric_column_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many numeric columns are there?",
            "How many numeric fields are in the dataset?",
            "Total number of numeric columns",
        ),
        expected_intent_name="numeric_column_count",
        expected_step_actions=("numeric_column_count",),
        expected_primary_result_name="numeric_column_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=2,
    ),
    ReproducibilityCase(
        family_id="categorical_column_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many categorical columns are there?",
            "How many categorical fields are in the dataset?",
            "Total number of categorical columns",
        ),
        expected_intent_name="categorical_column_count",
        expected_step_actions=("categorical_column_count",),
        expected_primary_result_name="categorical_column_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=4,
    ),
    ReproducibilityCase(
        family_id="measure_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many measure columns are there?",
            "How many measures are in the dataset?",
            "How many metrics are in the dataset?",
        ),
        expected_intent_name="measure_count",
        expected_step_actions=("measure_count",),
        expected_primary_result_name="measure_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=2,
    ),
    ReproducibilityCase(
        family_id="dimension_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many dimension columns are there?",
            "How many dimensions are in the dataset?",
            "How many dimension columns are in the dataset?",
        ),
        expected_intent_name="dimension_count",
        expected_step_actions=("dimension_count",),
        expected_primary_result_name="dimension_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=4,
    ),
    ReproducibilityCase(
        family_id="time_column_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many time columns are there?",
            "How many datetime fields are there?",
            "Total number of date columns in the dataset",
        ),
        expected_intent_name="time_column_count",
        expected_step_actions=("time_column_count",),
        expected_primary_result_name="time_column_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=1,
    ),
    ReproducibilityCase(
        family_id="identifier_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many identifier columns are there?",
            "How many likely identifier columns are there?",
            "Total number of identifier columns",
        ),
        expected_intent_name="identifier_count",
        expected_step_actions=("identifier_count",),
        expected_primary_result_name="identifier_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=1,
    ),
    ReproducibilityCase(
        family_id="high_cardinality_count",
        dataset_factory=build_support_dataset,
        prompts=(
            "How many high-cardinality columns are there?",
            "How many columns have high cardinality?",
            "Total number of high-cardinality fields",
        ),
        expected_intent_name="high_cardinality_count",
        expected_step_actions=("high_cardinality_count",),
        expected_primary_result_name="high_cardinality_count",
        expected_primary_logical_shape="scalar",
        expected_primary_value=4,
    ),
]

_REPRODUCIBILITY_CASES.extend(
    [
        ReproducibilityCase(
            family_id="representation_ranking",
            dataset_factory=build_support_dataset,
            prompts=("Which team has the most tickets?", "What team is most represented?", "Which team has the highest count?"),
            expected_intent_name="representation_ranking",
            expected_target="team",
            expected_aggregation="count",
            expected_group_by=("team",),
            expected_option_subset={"ranking_direction": "desc", "ranking_limit": 1},
        expected_step_actions=("group_frame", "aggregate_frame", "sort_frame", "limit_frame"),
            expected_primary_result_name="count_rows_by_group",
            expected_primary_logical_shape="table",
            expected_primary_value={"team": "Support", "row_count": 4},
        ),
        ReproducibilityCase(
            family_id="row_ranking",
            dataset_factory=build_support_dataset,
            prompts=(
                "Return top 2 resolution_hours values",
                "Show top 2 resolution_hours values",
                "List the top 2 resolution_hours values",
            ),
            expected_intent_name="row_ranking",
            expected_target="resolution_hours",
            expected_option_subset={"ranking_direction": "desc", "ranking_limit": 2},
            expected_step_actions=("filter_frame", "rank_frame"),
            expected_primary_result_name="ranked_rows",
            expected_primary_logical_shape="table",
        ),
        ReproducibilityCase(
            family_id="group_ranking",
            dataset_factory=build_sales_dataset,
            prompts=("Return top 2 revenue by region", "Show top 2 revenue by region", "List the top 2 revenue by region"),
            expected_intent_name="group_ranking",
            expected_target="revenue",
            expected_group_by=("region",),
            expected_option_subset={"ranking_direction": "desc", "ranking_limit": 2},
            expected_step_actions=("group_frame", "aggregate_frame", "rank_frame"),
            expected_primary_result_name="ranked_breakdown",
            expected_primary_logical_shape="table",
        ),
        ReproducibilityCase(
            family_id="column_presence_check",
            dataset_factory=build_support_dataset,
            prompts=(
                "Does the dataset have a created_at column?",
                "Is there a created_at field?",
                "Does this data include a created_at column?",
            ),
            expected_intent_name="existence_check",
            expected_option_subset={"existence_mode": "column_presence_check", "requested_column": "created_at"},
            expected_step_actions=("column_presence_check",),
            expected_primary_result_name="column_presence_check",
            expected_primary_logical_shape="verification",
        ),
        ReproducibilityCase(
            family_id="column_property_check",
            dataset_factory=build_sales_dataset,
            prompts=("Is region a dimension?", "Is region a grouping column?", "Is region a dimension column?"),
            expected_intent_name="existence_check",
            expected_target="region",
            expected_option_subset={"existence_mode": "column_property_check", "expected_property": "dimension"},
            expected_step_actions=("column_property_check",),
            expected_primary_result_name="column_property_check",
            expected_primary_logical_shape="verification",
        ),
        ReproducibilityCase(
            family_id="null_verification",
            dataset_factory=build_support_dataset,
            prompts=(
                "Does csat_score have missing values?",
                "Does csat_score have null values?",
                "Does csat_score contain missing values?",
            ),
            expected_intent_name="existence_check",
            expected_target="csat_score",
            expected_option_subset={"existence_mode": "null_check", "null_expectation": "has_nulls"},
            expected_step_actions=("null_check",),
            expected_primary_result_name="null_check",
            expected_primary_logical_shape="verification",
        ),
        ReproducibilityCase(
            family_id="threshold_verification",
            dataset_factory=build_support_dataset,
            prompts=("Are any resolution_hours above 7?", "Is resolution_hours above 7 anywhere?", "Are any resolution_hours over 7?"),
            expected_intent_name="existence_check",
            expected_target="resolution_hours",
            expected_option_subset={"existence_mode": "threshold_check", "threshold_operator": "gt", "threshold_value": 7.0},
            expected_step_actions=("threshold_check",),
            expected_primary_result_name="threshold_check",
            expected_primary_logical_shape="verification",
        ),
        ReproducibilityCase(
            family_id="time_value_verification",
            dataset_factory=build_support_dataset,
            prompts=(
                "The created_at column shows dates in 2026?",
                "Are there dates in 2026 in created_at?",
                "Does created_at include dates in 2026?",
            ),
            expected_intent_name="existence_check",
            expected_target="created_at",
            expected_filters={"created_at": {"op": "year_eq", "value": 2026}},
            expected_option_subset={"existence_mode": "time_value", "expected_year": 2026},
            expected_step_actions=("time_value_exists",),
            expected_primary_result_name="time_value_exists",
            expected_primary_logical_shape="verification",
        ),
        ReproducibilityCase(
            family_id="row_existence_check",
            dataset_factory=build_sales_dataset,
            prompts=("Is West in the region column?", "Are there any West values in region?", "Are there any region values equal to West?"),
            expected_intent_name="existence_check",
            expected_filters={"region": "West"},
            expected_option_subset={"existence_mode": "filtered_rows"},
            expected_step_actions=("row_existence",),
            expected_primary_result_name="row_existence",
            expected_primary_logical_shape="verification",
        ),
        ReproducibilityCase(
            family_id="time_coverage",
            dataset_factory=build_sales_dataset,
            prompts=(
                "What date range does the sales data cover?",
                "What is the date range of the sales data?",
                "From when to when does the sales data run?",
            ),
            expected_intent_name="time_coverage",
            expected_option_subset={"time_coverage_mode": "date_range"},
            expected_step_actions=("time_coverage",),
            expected_primary_result_name="time_coverage",
            expected_primary_logical_shape="table",
        ),
        ReproducibilityCase(
            family_id="time_bucket_counts",
            dataset_factory=build_support_dataset,
            prompts=("How many tickets were created by quarter?", "Count tickets by quarter", "Show ticket counts by quarter"),
            expected_intent_name="time_bucket_counts",
            expected_option_subset={"time_bucket": "quarter"},
            expected_step_actions=("time_bucket_frame", "aggregate_frame"),
            expected_primary_result_name="time_bucket_counts",
            expected_primary_logical_shape="table",
        ),
        ReproducibilityCase(
            family_id="time_bucket_breakdown",
            dataset_factory=build_sales_dataset,
            prompts=("Show revenue by month", "Display revenue by month", "Give me revenue by month"),
            expected_intent_name="time_bucket_breakdown",
            expected_target="revenue",
            expected_option_subset={"time_bucket": "month"},
            expected_step_actions=("time_bucket_frame", "aggregate_frame"),
            expected_primary_result_name="time_bucket_breakdown",
            expected_primary_logical_shape="table",
        ),
        ReproducibilityCase(
            family_id="time_period_comparison",
            dataset_factory=build_sales_dataset,
            prompts=(
                "Compare revenue this quarter to last quarter",
                "Show revenue for this quarter versus last quarter",
                "Compare revenue for this quarter versus last quarter",
            ),
            expected_intent_name="time_period_comparison",
            expected_target="revenue",
            expected_option_subset={"time_bucket": "quarter"},
            expected_step_actions=("time_bucket_frame", "period_comparison"),
            expected_primary_result_name="period_comparison",
            expected_primary_logical_shape="timeseries",
        ),
        ReproducibilityCase(
            family_id="grouped_entity_count",
            dataset_factory=build_support_dataset,
            prompts=("Give me the total tickets per team.", "For each team, give me the total tickets.", "Count tickets by team"),
            expected_intent_name="grouped_tabular_query",
            expected_aggregation="count",
            expected_group_by=("team",),
            expected_step_actions=("group_frame", "aggregate_frame", "sort_frame"),
            expected_primary_result_name="grouped_tabular_query",
            expected_primary_logical_shape="table",
        ),
        ReproducibilityCase(
            family_id="grouped_metric_table",
            dataset_factory=build_sales_dataset,
            prompts=(
                "Show total revenue by region in a table",
                "Give me a table of revenue by region",
                "Return a grouped table of revenue by region",
            ),
            expected_intent_name="grouped_tabular_query",
            expected_target="revenue",
            expected_aggregation="sum",
            expected_group_by=("region",),
            expected_option_subset={"selected_columns": ["revenue", "region"]},
            expected_step_actions=("group_frame", "aggregate_frame", "sort_frame"),
            expected_primary_result_name="grouped_tabular_query",
            expected_primary_logical_shape="table",
        ),
        ReproducibilityCase(
            family_id="tabular_record_retrieval",
            dataset_factory=build_support_dataset,
            prompts=(
                "Show ticket_id and priority rows sorted by created_at",
                "Display ticket_id and priority records ordered by created_at",
                "Return ticket_id and priority row data sorted by created_at",
            ),
            expected_intent_name="tabular_query",
            expected_target=None,
            expected_option_subset={
                "selected_columns": ["ticket_id", "priority", "created_at"],
                "sort_by": "created_at",
                "sort_direction": "asc",
            },
            expected_step_actions=("filter_frame", "sort_frame", "select_columns", "tabular_query"),
            expected_primary_result_name="tabular_query",
            expected_primary_logical_shape="recordset",
        ),
    ]
)

_REPRODUCIBILITY_CASES.extend(
    [
        ReproducibilityCase(
            family_id="significance_inference",
            dataset_factory=build_sales_dataset,
            prompts=(
                "Do regions differ in revenue?",
                "Is there a significant difference in revenue by region?",
                "Do regions differ significantly in revenue?",
            ),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="revenue",
            expected_group_by=("region",),
            expected_option_subset={"statistical_test": "significance_inference"},
            expected_step_actions=("significance_inference",),
            expected_primary_result_name="significance_inference",
            expected_primary_logical_shape="statistical_test",
        ),
        ReproducibilityCase(
            family_id="confidence_interval",
            dataset_factory=build_sales_dataset,
            prompts=(
                "What range are we 95% confident revenue falls in?",
                "Show the 95% confidence interval for revenue",
                "What confidence range do we have for revenue?",
            ),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="revenue",
            expected_option_subset={"statistical_test": "confidence_interval", "confidence_level": 0.95},
            expected_step_actions=("confidence_interval",),
            expected_primary_result_name="confidence_interval",
            expected_primary_logical_shape="statistical_test",
        ),
        ReproducibilityCase(
            family_id="power_analysis",
            dataset_factory=build_sales_dataset,
            prompts=(
                "Do we have enough data to detect a difference in revenue by region?",
                "Show the power analysis for revenue by region",
                "Estimate statistical power for revenue by region",
            ),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="revenue",
            expected_group_by=("region",),
            expected_option_subset={"statistical_test": "power_analysis", "desired_power": 0.8},
            expected_step_actions=("power_analysis",),
            expected_primary_result_name="power_analysis",
            expected_primary_logical_shape="statistical_test",
        ),
        ReproducibilityCase(
            family_id="sample_size_estimate",
            dataset_factory=build_sales_dataset,
            prompts=(
                "Estimate sample size for revenue by region",
                "Estimate required sample size for revenue by region",
                "What required sample size do we need for revenue by region?",
            ),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="revenue",
            expected_group_by=("region",),
            expected_option_subset={"statistical_test": "sample_size_estimate", "desired_power": 0.8},
            expected_step_actions=("sample_size_estimate",),
            expected_primary_result_name="sample_size_estimate",
            expected_primary_logical_shape="statistical_test",
        ),
        ReproducibilityCase(
            family_id="t_test",
            dataset_factory=build_sales_dataset,
            prompts=("Run t-test on revenue by region", "Perform a t-test on revenue by region", "Use a t-test for revenue by region"),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="revenue",
            expected_group_by=("region",),
            expected_option_subset={"statistical_test": "t_test"},
            expected_step_actions=("t_test",),
            expected_primary_result_name="t_test",
            expected_primary_logical_shape="statistical_test",
        ),
        ReproducibilityCase(
            family_id="anova",
            dataset_factory=build_sales_dataset,
            prompts=("Run anova on revenue by region", "Perform anova on revenue by region", "Use anova for revenue by region"),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="revenue",
            expected_group_by=("region",),
            expected_option_subset={"statistical_test": "anova"},
            expected_step_actions=("anova",),
            expected_primary_result_name="anova",
            expected_primary_logical_shape="statistical_test",
        ),
        ReproducibilityCase(
            family_id="mann_whitney",
            dataset_factory=build_sales_dataset,
            prompts=(
                "Run mann-whitney on revenue by region",
                "Perform mann-whitney on revenue by region",
                "Use mann-whitney for revenue by region",
            ),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="revenue",
            expected_group_by=("region",),
            expected_option_subset={"statistical_test": "mann_whitney"},
            expected_step_actions=("mann_whitney",),
            expected_primary_result_name="mann_whitney",
            expected_primary_logical_shape="statistical_test",
        ),
        ReproducibilityCase(
            family_id="regression_significance",
            dataset_factory=build_support_dataset,
            prompts=(
                "Does resolution_hours significantly affect csat_score?",
                "Does resolution_hours significantly influence csat_score?",
                "Test whether resolution_hours significantly affects csat_score",
            ),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="csat_score",
            expected_option_subset={"statistical_test": "regression_significance", "feature_columns": ["resolution_hours"]},
            expected_step_actions=("regression_significance",),
            expected_primary_result_name="regression_significance",
            expected_primary_logical_shape="statistical_test",
        ),
        ReproducibilityCase(
            family_id="chi_square",
            dataset_factory=build_support_dataset,
            prompts=(
                "Run chi-square between team and priority",
                "Run chi square between team and priority",
                "Chi-square test for team and priority",
            ),
            expected_intent_name=None,
            expected_task_type="statistical",
            expected_target="team",
            expected_group_by=("priority",),
            expected_option_subset={"statistical_test": "chi_square", "comparison_columns": ["team", "priority"]},
            expected_step_actions=("chi_square",),
            expected_primary_result_name="chi_square",
            expected_primary_logical_shape="statistical_test",
        ),
    ]
)


def _assert_option_subset(options: dict[str, Any], expected_option_subset: dict[str, Any]) -> None:
    for key, expected_value in expected_option_subset.items():
        assert options.get(key) == expected_value


@pytest.mark.parametrize("case", _REPRODUCIBILITY_CASES, ids=[case.family_id for case in _REPRODUCIBILITY_CASES])
def test_prompt_family_paraphrases_reproduce_same_request_plan_and_result(case: ReproducibilityCase) -> None:
    engine = PromptAnalysisFrontend()
    dataset = case.dataset_factory()
    profile = engine.profile(dataset)

    baseline_request_signature: dict[str, Any] | None = None
    baseline_plan_signature: dict[str, Any] | None = None
    baseline_result_signature: dict[str, Any] | None = None

    for prompt in case.prompts:
        request, warnings = engine.canonicalizer.normalize(prompt, dataset, profile, dataset.context)
        plan = engine.plan_builder.build_plan(request, profile, dataset.context)
        result = engine.analyze(dataset, prompt)

        assert warnings == []

        request_signature = json_safe(_request_signature(request))
        plan_signature = json_safe(_plan_signature(plan))
        result_signature = json_safe(_result_signature(result))

        if baseline_request_signature is None:
            baseline_request_signature = request_signature
            baseline_plan_signature = plan_signature
            baseline_result_signature = result_signature
        else:
            assert request_signature == baseline_request_signature
            assert plan_signature == baseline_plan_signature
            assert result_signature == baseline_result_signature

    assert baseline_request_signature is not None
    assert baseline_plan_signature is not None
    assert baseline_result_signature is not None

    assert baseline_request_signature["prompt_family"] == case.family_id
    assert baseline_request_signature["intent_name"] == case.expected_intent_name
    assert baseline_request_signature["task_type_hint"] == case.expected_task_type
    assert baseline_request_signature["target"] == case.expected_target
    assert baseline_request_signature["aggregation"] == case.expected_aggregation
    assert baseline_request_signature["filters"] == case.expected_filters
    assert baseline_request_signature["group_by"] == list(case.expected_group_by)
    _assert_option_subset(baseline_request_signature["options"], case.expected_option_subset)

    assert baseline_plan_signature["task_type"] == case.expected_task_type
    assert [step["action"] for step in baseline_plan_signature["steps"]] == list(case.expected_step_actions)

    assert baseline_result_signature["result"]["name"] == case.expected_primary_result_name
    if case.expected_primary_logical_shape is not None:
        assert baseline_result_signature["result"]["logical_shape"] == case.expected_primary_logical_shape
    if case.expected_primary_value is not _UNSET:
        assert normalized_result_value(baseline_result_signature["result"]) == case.expected_primary_value


def test_plan_reproducibility_suite_covers_every_prompt_family() -> None:
    catalog = build_default_prompt_family_catalog()
    covered_family_ids = {case.family_id for case in _REPRODUCIBILITY_CASES}
    catalog_family_ids = set(catalog.families)

    missing_families = sorted(catalog_family_ids - covered_family_ids)
    extra_families = sorted(covered_family_ids - catalog_family_ids)

    assert covered_family_ids == catalog_family_ids, (
        f"Prompt family reproducibility coverage drifted. Missing={missing_families}, extra={extra_families}"
    )

