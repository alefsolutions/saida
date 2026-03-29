from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, Dataset, PlanStep
from .factories import build_explicit_single_step_plan, build_sales_dataset, build_statistical_dataset, build_support_dataset


@dataclass(frozen=True, slots=True)
class FamilyContractCase:
    case_id: str
    family_id: str
    dataset_builder: Callable[[], Dataset]
    plan_builder: Callable[[str], AnalysisPlan]
    expected_result_shape: str


def _plan_for_projection(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Return selected support fields.",
        step_id="tabular_query",
        tool_family="duckdb",
        method_id="tabular_query",
        family="projection_field_selection",
        parameters={
            "selected_columns": ["ticket_id", "team"],
            "sort_by": "ticket_id",
            "sort_direction": "asc",
            "page": 1,
            "page_size": 50,
        },
        description="Return selected support fields.",
        expected_result_name="tabular_query",
        expected_result_shape="table",
    )


def _plan_for_aggregation(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Count reopened support rows.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={"filters": {"reopened_flag": "yes"}},
        description="Count reopened support rows.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )


def _plan_for_ranking(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Rank regions by summed revenue.",
        step_id="ranked_breakdown",
        tool_family="duckdb",
        method_id="ranked_breakdown",
        family="ranking",
        parameters={
            "target": "revenue",
            "group_by": ["region"],
            "aggregation": "sum",
            "ascending": False,
            "limit": 2,
        },
        description="Rank regions by summed revenue.",
        expected_result_name="ranked_breakdown",
        expected_result_shape="table",
    )


def _plan_for_verification(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Verify support rows exist for Platform.",
        step_id="row_existence",
        tool_family="duckdb",
        method_id="row_existence",
        family="validation_verification",
        parameters={"filters": {"team": "Platform"}},
        description="Verify support rows exist for Platform.",
        expected_result_name="row_existence",
        expected_result_shape="verification",
    )


def _plan_for_schema_metadata(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Count dataset columns.",
        step_id="column_count",
        tool_family="metadata",
        method_id="column_count",
        family="schema_metadata_inspection",
        parameters={},
        description="Count dataset columns.",
        expected_result_name="column_count",
        expected_result_shape="scalar",
    )


def _plan_for_distinct(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Count distinct teams.",
        step_id="distinct_value_count",
        tool_family="duckdb",
        method_id="distinct_value_count",
        family="distinct_cardinality_analysis",
        parameters={"target": "team"},
        description="Count distinct teams.",
        expected_result_name="team_distinct_count",
        expected_result_shape="scalar",
    )


def _plan_for_time_series(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Break revenue down by month.",
        step_id="time_bucket_breakdown",
        tool_family="duckdb",
        method_id="time_bucket_breakdown",
        family="time_series_time_bucketing",
        parameters={
            "target": "revenue",
            "time_column": "posted_at",
            "bucket": "month",
            "aggregation": "sum",
        },
        description="Break revenue down by month.",
        expected_result_name="time_bucket_breakdown",
        expected_result_shape="table",
    )


def _plan_for_period_comparison(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="diagnostic",
        rationale="Compare March revenue to its prior period.",
        step_id="period_comparison",
        tool_family="duckdb",
        method_id="period_comparison",
        family="period_comparison",
        parameters={
            "target": "revenue",
            "time_column": "posted_at",
            "time_reference": {"type": "month_name", "value": "march", "month": "3"},
            "aggregation": "sum",
        },
        description="Compare March revenue to its prior period.",
        expected_result_name="period_comparison",
        expected_result_shape="table",
    )


def _plan_for_statistical(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="statistical",
        rationale="Compute a confidence interval for revenue.",
        step_id="confidence_interval",
        tool_family="stats",
        method_id="confidence_interval",
        family="statistical_inference",
        parameters={"target": "revenue", "confidence_level": 0.95},
        description="Compute a confidence interval for revenue.",
        expected_result_name="confidence_interval",
        expected_result_shape="table",
    )


def _plan_for_diagnostic(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="diagnostic",
        rationale="Summarize support numeric columns.",
        step_id="numeric_summary",
        tool_family="stats",
        method_id="numeric_summary",
        family="diagnostic_workflows",
        parameters={},
        description="Summarize support numeric columns.",
        expected_result_name="numeric_summary",
        expected_result_shape="table",
    )


_FAMILY_CASES = [
    FamilyContractCase("projection", "projection_field_selection", build_support_dataset, _plan_for_projection, "table"),
    FamilyContractCase("aggregation", "aggregation_grouping", build_support_dataset, _plan_for_aggregation, "scalar"),
    FamilyContractCase("ranking", "ranking", build_sales_dataset, _plan_for_ranking, "table"),
    FamilyContractCase("verification", "validation_verification", build_support_dataset, _plan_for_verification, "verification"),
    FamilyContractCase("schema_metadata", "schema_metadata_inspection", build_support_dataset, _plan_for_schema_metadata, "scalar"),
    FamilyContractCase("distinct", "distinct_cardinality_analysis", build_support_dataset, _plan_for_distinct, "scalar"),
    FamilyContractCase("time_series", "time_series_time_bucketing", build_sales_dataset, _plan_for_time_series, "table"),
    FamilyContractCase("period_comparison", "period_comparison", build_sales_dataset, _plan_for_period_comparison, "table"),
    FamilyContractCase("statistical", "statistical_inference", build_statistical_dataset, _plan_for_statistical, "table"),
    FamilyContractCase("diagnostic", "diagnostic_workflows", build_support_dataset, _plan_for_diagnostic, "table"),
]


@pytest.mark.parametrize("case", _FAMILY_CASES, ids=[case.case_id for case in _FAMILY_CASES])
def test_plan_execution_family_contracts_return_canonical_analysis_result(case: FamilyContractCase) -> None:
    engine = Saida()
    dataset = case.dataset_builder()
    plan = case.plan_builder(dataset.name)

    result = engine.execute_plan(dataset, deepcopy(plan))
    payload = result.to_response_dict()

    assert payload["schema_version"] == "saida.response.v2"
    assert payload["status"] == "ok"
    assert payload["execution"]["plan_id"] == result.plan.plan_id
    assert payload["execution"]["expected_result_shape"] == case.expected_result_shape
    assert payload["result"]["name"] in {result.plan.expected_result_name, result.plan.final_output_ref}
    assert payload["result"]["physical_shape"] is not None
    assert payload["summary"]["summary"] == result.summary
    assert payload["summary"]["deterministic_summary"] == result.deterministic_summary
    assert payload["summary"]["summary_source"] in {"deterministic", "llm"}


@pytest.mark.parametrize("case", _FAMILY_CASES, ids=[case.case_id for case in _FAMILY_CASES])
def test_plan_execution_family_contracts_keep_plan_metadata_authoritative(case: FamilyContractCase) -> None:
    engine = Saida()
    dataset = case.dataset_builder()
    plan = case.plan_builder(dataset.name)

    result = engine.execute_plan(dataset, deepcopy(plan))

    assert result.plan.expected_result_shape == case.expected_result_shape
    assert result.plan.steps[0].family == case.family_id
    assert result.response["interpretation"]["task_type"] == plan.task_type
    assert result.response["execution"]["steps"][0]["family"] == case.family_id
    assert result.response["interpretation"]["options"]["plan_execution"] is True
    assert result.response["execution"]["expected_result_name"] == plan.expected_result_name
