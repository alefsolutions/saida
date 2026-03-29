from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, AnalysisResult, PlanInput, PlanStep
from saida.core.analytics_registry import get_analytics_registry
from .factories import build_sales_dataset, build_statistical_dataset, build_support_dataset, json_safe
from .result_helpers import normalized_result_value


@dataclass(frozen=True, slots=True)
class PlanMethodCase:
    case_id: str
    method_id: str
    tool_family: str
    family_id: str
    dataset_builder: Callable[[], object]
    parameters: dict[str, object]
    expected_result_shape: str
    task_type: str = "descriptive"


def _case(
    case_id: str,
    method_id: str,
    tool_family: str,
    family_id: str,
    dataset_builder: Callable[[], object],
    parameters: dict[str, object],
    expected_result_shape: str,
    task_type: str = "descriptive",
) -> PlanMethodCase:
    return PlanMethodCase(
        case_id=case_id,
        method_id=method_id,
        tool_family=tool_family,
        family_id=family_id,
        dataset_builder=dataset_builder,
        parameters=parameters,
        expected_result_shape=expected_result_shape,
        task_type=task_type,
    )


_ALL_METHOD_CASES: list[PlanMethodCase] = [
    _case("tabular_query", "tabular_query", "duckdb", "projection_field_selection", build_support_dataset, {"selected_columns": ["ticket_id", "priority"], "filters": {"reopened_flag": "yes"}, "sort_by": "created_at", "sort_direction": "asc", "page": 1, "page_size": 50}, "table"),
    _case("row_count", "row_count", "duckdb", "aggregation_grouping", build_support_dataset, {"filters": {"reopened_flag": "no"}}, "scalar"),
    _case("count_rows_by_group", "count_rows_by_group", "duckdb", "aggregation_grouping", build_support_dataset, {"group_by": ["team"]}, "table"),
    _case("aggregate_value", "aggregate_value", "duckdb", "aggregation_grouping", build_sales_dataset, {"target": "revenue", "aggregation": "sum"}, "scalar"),
    _case("group_breakdown", "group_breakdown", "duckdb", "aggregation_grouping", build_sales_dataset, {"target": "revenue", "group_by": ["region"], "aggregation": "sum"}, "table"),
    _case("grouped_tabular_query", "grouped_tabular_query", "duckdb", "aggregation_grouping", build_sales_dataset, {"group_by": ["region"], "target": "revenue", "aggregation": "sum", "sort_by": "revenue", "sort_direction": "desc", "page": 1, "page_size": 50}, "table"),
    _case("ranked_rows", "ranked_rows", "duckdb", "ranking", build_sales_dataset, {"target": "revenue", "ascending": False, "limit": 3}, "table"),
    _case("ranked_breakdown", "ranked_breakdown", "duckdb", "ranking", build_sales_dataset, {"target": "revenue", "group_by": ["region"], "aggregation": "sum", "ascending": False, "limit": 2}, "table"),
    _case("row_existence", "row_existence", "duckdb", "validation_verification", build_support_dataset, {"filters": {"team": "Platform"}}, "verification"),
    _case("time_value_exists", "time_value_exists", "duckdb", "validation_verification", build_support_dataset, {"time_column": "created_at", "expected_year": 2026}, "verification"),
    _case("null_check", "null_check", "duckdb", "validation_verification", build_support_dataset, {"target": "csat_score", "null_expectation": "has_nulls"}, "verification"),
    _case("threshold_check", "threshold_check", "duckdb", "validation_verification", build_support_dataset, {"target": "resolution_hours", "threshold_operator": "gt", "threshold_value": 7}, "verification"),
    _case("column_property_check", "column_property_check", "metadata", "validation_verification", build_support_dataset, {"target": "ticket_id", "expected_property": "identifier"}, "verification"),
    _case("column_presence_check", "column_presence_check", "metadata", "validation_verification", build_support_dataset, {"requested_column": "csat_score"}, "verification"),
    _case("column_count", "column_count", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "scalar"),
    _case("column_inventory", "column_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("column_type_inventory", "column_type_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("numeric_column_inventory", "numeric_column_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("numeric_column_count", "numeric_column_count", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "scalar"),
    _case("categorical_column_inventory", "categorical_column_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("categorical_column_count", "categorical_column_count", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "scalar"),
    _case("measure_inventory", "measure_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("measure_count", "measure_count", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "scalar"),
    _case("dimension_inventory", "dimension_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("dimension_count", "dimension_count", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "scalar"),
    _case("time_column_inventory", "time_column_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("time_column_count", "time_column_count", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "scalar"),
    _case("missing_value_inventory", "missing_value_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("identifier_inventory", "identifier_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("identifier_count", "identifier_count", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "scalar"),
    _case("high_cardinality_inventory", "high_cardinality_inventory", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "table"),
    _case("high_cardinality_count", "high_cardinality_count", "metadata", "schema_metadata_inspection", build_support_dataset, {}, "scalar"),
    _case("distinct_values", "distinct_values", "duckdb", "distinct_cardinality_analysis", build_support_dataset, {"target": "team"}, "table"),
    _case("distinct_value_count", "distinct_value_count", "duckdb", "distinct_cardinality_analysis", build_support_dataset, {"target": "team"}, "scalar"),
    _case("time_coverage", "time_coverage", "duckdb", "time_series_time_bucketing", build_sales_dataset, {"time_column": "posted_at", "mode": "years_present"}, "table"),
    _case("time_bucket_counts", "time_bucket_counts", "duckdb", "time_series_time_bucketing", build_support_dataset, {"time_column": "created_at", "bucket": "quarter"}, "table"),
    _case("time_bucket_breakdown", "time_bucket_breakdown", "duckdb", "time_series_time_bucketing", build_sales_dataset, {"target": "revenue", "time_column": "posted_at", "bucket": "month", "aggregation": "sum"}, "table"),
    _case("time_trend", "time_trend", "duckdb", "time_series_time_bucketing", build_sales_dataset, {"target": "revenue", "time_column": "posted_at", "aggregation": "sum"}, "table"),
    _case("period_comparison", "period_comparison", "duckdb", "period_comparison", build_sales_dataset, {"target": "revenue", "time_column": "posted_at", "time_reference": {"type": "month_name", "value": "march", "month": "3"}, "aggregation": "sum"}, "table"),
    _case("grouped_period_comparison", "grouped_period_comparison", "duckdb", "period_comparison", build_sales_dataset, {"target": "revenue", "group_by": ["region"], "time_column": "posted_at", "time_reference": {"type": "month_name", "value": "march", "month": "3"}, "aggregation": "sum"}, "table"),
    _case("top_movers", "top_movers", "duckdb", "period_comparison", build_sales_dataset, {"target": "revenue", "group_by": ["region"], "time_column": "posted_at", "time_reference": {"type": "month_name", "value": "march", "month": "3"}, "aggregation": "sum", "limit": 2}, "table"),
    _case("contribution_breakdown", "contribution_breakdown", "duckdb", "period_comparison", build_sales_dataset, {"target": "revenue", "group_by": ["region"], "time_column": "posted_at", "time_reference": {"type": "month_name", "value": "march", "month": "3"}, "aggregation": "sum"}, "table"),
    _case("significance_inference", "significance_inference", "stats", "statistical_inference", build_statistical_dataset, {"target": "revenue", "group_by": ["region"], "alpha": 0.05}, "table"),
    _case("t_test", "t_test", "stats", "statistical_inference", build_statistical_dataset, {"target": "revenue", "group_by": ["region"], "alpha": 0.05}, "table"),
    _case("chi_square", "chi_square", "stats", "statistical_inference", build_statistical_dataset, {"comparison_columns": ["team", "segment"], "alpha": 0.05}, "table"),
    _case("anova", "anova", "stats", "statistical_inference", build_statistical_dataset, {"target": "revenue", "group_by": ["team"], "alpha": 0.05}, "table"),
    _case("mann_whitney", "mann_whitney", "stats", "statistical_inference", build_statistical_dataset, {"target": "revenue", "group_by": ["region"], "alpha": 0.05}, "table"),
    _case("confidence_interval", "confidence_interval", "stats", "statistical_inference", build_statistical_dataset, {"target": "revenue", "confidence_level": 0.95}, "table"),
    _case("regression_significance", "regression_significance", "stats", "statistical_inference", build_statistical_dataset, {"target": "revenue", "feature_columns": ["cost", "units"], "alpha": 0.05}, "table"),
    _case("power_analysis", "power_analysis", "stats", "statistical_inference", build_statistical_dataset, {"target": "revenue", "group_by": ["region"], "alpha": 0.05}, "table"),
    _case("sample_size_estimate", "sample_size_estimate", "stats", "statistical_inference", build_statistical_dataset, {"target": "revenue", "group_by": ["region"], "alpha": 0.05, "desired_power": 0.9}, "table"),
    _case("dataset_summary", "dataset_summary", "duckdb", "diagnostic_workflows", build_sales_dataset, {"target": "revenue"}, "table"),
    _case("missingness_summary", "missingness_summary", "stats", "diagnostic_workflows", build_support_dataset, {}, "table"),
    _case("numeric_summary", "numeric_summary", "stats", "diagnostic_workflows", build_support_dataset, {}, "table"),
    _case("distribution_summary", "distribution_summary", "stats", "diagnostic_workflows", build_statistical_dataset, {"target": "revenue"}, "table"),
    _case("target_correlation", "target_correlation", "stats", "diagnostic_workflows", build_statistical_dataset, {"target": "revenue"}, "table"),
    _case("anomaly_summary", "anomaly_summary", "stats", "diagnostic_workflows", build_sales_dataset, {"target": "revenue", "time_column": "posted_at"}, "table"),
    _case("time_series_diagnostics", "time_series_diagnostics", "stats", "diagnostic_workflows", build_sales_dataset, {"target": "revenue", "time_column": "posted_at"}, "table"),
    _case("group_mean_comparison", "group_mean_comparison", "stats", "diagnostic_workflows", build_statistical_dataset, {"target": "revenue", "group_column": "region"}, "table"),
]


def _build_plan(case: PlanMethodCase, dataset_name: str) -> AnalysisPlan:
    return AnalysisPlan(
        task_type=case.task_type,
        rationale=f"Execute {case.method_id} deterministically for {case.case_id}.",
        dataset_refs=[dataset_name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset_name)],
        expected_result_shape=case.expected_result_shape,
        steps=[
            PlanStep(
                step_id=case.method_id,
                tool_family=case.tool_family,
                action=case.method_id,
                method_id=case.method_id,
                family=case.family_id,
                parameters=deepcopy(case.parameters),
                description=f"Execute {case.method_id}.",
                output_refs=[case.method_id],
            )
        ],
    )


def _execute_case(case: PlanMethodCase) -> AnalysisResult:
    engine = Saida()
    dataset = case.dataset_builder()
    plan = _build_plan(case, dataset.name)
    return engine.execute_plan(dataset, deepcopy(plan))


def test_plan_method_matrix_covers_every_supported_non_ml_method() -> None:
    registry = get_analytics_registry()
    covered_methods = {case.method_id for case in _ALL_METHOD_CASES}
    executable_methods = {
        method_id
        for method_id, method_spec in registry.methods.items()
        if method_spec.default_tool_family in {"duckdb", "metadata", "stats"}
    }

    assert covered_methods == executable_methods


def test_plan_method_matrix_covers_every_non_ml_family_with_methods() -> None:
    registry = get_analytics_registry()
    covered_families = {case.family_id for case in _ALL_METHOD_CASES}
    executable_families = {
        method_spec.family_id
        for method_spec in registry.methods.values()
        if method_spec.default_tool_family in {"duckdb", "metadata", "stats"}
    }

    assert covered_families == executable_families


@pytest.mark.parametrize("case", _ALL_METHOD_CASES, ids=[case.case_id for case in _ALL_METHOD_CASES])
def test_plan_method_matrix_validation_accepts_authored_plan(case: PlanMethodCase) -> None:
    engine = Saida()
    dataset = case.dataset_builder()
    profile = engine.profile(dataset)
    plan = _build_plan(case, dataset.name)

    engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


@pytest.mark.parametrize("case", _ALL_METHOD_CASES, ids=[case.case_id for case in _ALL_METHOD_CASES])
def test_plan_method_matrix_execute_plan_returns_analysis_result(case: PlanMethodCase) -> None:
    result = _execute_case(case)

    assert isinstance(result, AnalysisResult)
    assert result.response["status"] == "ok"
    assert result.plan.steps[0].method_id == case.method_id
    assert result.plan.steps[0].family == case.family_id


@pytest.mark.parametrize("case", _ALL_METHOD_CASES, ids=[case.case_id for case in _ALL_METHOD_CASES])
def test_plan_method_matrix_execute_plan_honors_expected_result_shape(case: PlanMethodCase) -> None:
    result = _execute_case(case)
    value = normalized_result_value(result.response["result"])

    assert result.response["execution"]["expected_result_shape"] == case.expected_result_shape
    assert result.plan.expected_result_shape == case.expected_result_shape
    if case.expected_result_shape == "scalar":
        assert not isinstance(value, list)
    elif case.expected_result_shape == "verification":
        assert isinstance(value, dict)
    else:
        assert isinstance(value, (list, dict))


@pytest.mark.parametrize("case", _ALL_METHOD_CASES, ids=[case.case_id for case in _ALL_METHOD_CASES])
def test_plan_method_matrix_execute_plan_is_deterministic(case: PlanMethodCase) -> None:
    engine = Saida()
    dataset = case.dataset_builder()
    plan = _build_plan(case, dataset.name)

    first = engine.execute_plan(dataset, deepcopy(plan))
    second = engine.execute_plan(dataset, deepcopy(plan))

    assert json_safe(first.response["result"]) == json_safe(second.response["result"])
    assert json_safe(first.response["execution"]) == json_safe(second.response["execution"])
