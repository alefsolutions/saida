from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

import pytest
import pandas as pd

from saida import Saida
from saida.adapters.interfaces import ComputeRequest
from saida.adapters.ml_adapter import MlAdapter
from saida.core.analytics_registry import get_analytics_registry
from saida.core.contracts import AnalysisPlan, Dataset, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import ModelTrainingError
from tests.helpers.factories import build_explicit_single_step_plan, build_sales_dataset, build_statistical_dataset, build_support_dataset


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


def _plan_for_selection_filtering(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Filter West sales rows.",
        step_id="filter_frame",
        tool_family="duckdb",
        method_id="filter_frame",
        family="selection_filtering",
        parameters={"filters": {"region": "West"}},
        description="Filter West sales rows.",
        expected_result_name="filter_frame",
        expected_result_shape="table",
    )


def _plan_for_transformation(dataset_name: str) -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Add a doubled revenue column.",
        step_id="derive_column",
        tool_family="duckdb",
        method_id="derive_column",
        family="transformation",
        parameters={"target": "revenue_twice", "expression": {"op": "multiply", "source": "revenue", "value": 2}},
        description="Add a doubled revenue column.",
        expected_result_name="derive_column",
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


def _build_join_dataset() -> Dataset:
    return Dataset(
        name="joinable_support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3"],
                "team": ["Support", "Platform", "Support"],
                "priority": ["Low", "High", "Medium"],
                "channel": ["Email", "Phone", "Chat"],
            }
        ),
    )


def _plan_for_joining(dataset_name: str) -> AnalysisPlan:
    return AnalysisPlan(
        task_type="descriptive",
        rationale="Join projected support rows by ticket id.",
        dataset_refs=[dataset_name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset_name)],
        expected_result_name="joined_rows",
        expected_result_shape="table",
        final_output_ref="joined_rows",
        steps=[
            PlanStep(
                step_id="left_projection",
                tool_family="duckdb",
                action="select_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["ticket_id", "team"]},
                description="Project ticket ids and teams.",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["left_rows"],
                outputs=[StepOutputSpec(output_id="left_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "left_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
            PlanStep(
                step_id="right_projection",
                tool_family="duckdb",
                action="select_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["ticket_id", "channel"]},
                description="Project ticket ids and channels.",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["right_rows"],
                outputs=[StepOutputSpec(output_id="right_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "right_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
            PlanStep(
                step_id="join_frame",
                tool_family="duckdb",
                action="join_frame",
                method_id="join_frame",
                family="joining",
                parameters={"on": "ticket_id", "how": "inner"},
                description="Join the projected frames.",
                inputs=[
                    StepInputRef(input_id="left_frame", source_type="step_output", ref="left_rows", expected_kind="frame"),
                    StepInputRef(input_id="right_frame", source_type="step_output", ref="right_rows", expected_kind="frame"),
                ],
                output_refs=["joined_rows"],
                outputs=[StepOutputSpec(output_id="joined_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "joined_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
        ],
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
    FamilyContractCase("selection_filtering", "selection_filtering", build_sales_dataset, _plan_for_selection_filtering, "table"),
    FamilyContractCase("transformation", "transformation", build_sales_dataset, _plan_for_transformation, "table"),
    FamilyContractCase("aggregation", "aggregation_grouping", build_support_dataset, _plan_for_aggregation, "scalar"),
    FamilyContractCase("joining", "joining", _build_join_dataset, _plan_for_joining, "table"),
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
    assert any(step.family == case.family_id for step in result.plan.steps)
    assert result.response["interpretation"]["task_type"] == plan.task_type
    assert any(step["family"] == case.family_id for step in result.response["execution"]["steps"])
    assert result.response["interpretation"]["options"]["plan_execution"] is True
    assert result.response["execution"]["expected_result_name"] == plan.expected_result_name


def test_plan_execution_family_contracts_cover_every_registry_family_with_methods() -> None:
    registry = get_analytics_registry()
    covered_families = {case.family_id for case in _FAMILY_CASES} | {"predictive_forecasting"}
    executable_families = {family_id for family_id, family in registry.families.items() if family.method_ids}

    assert covered_families == executable_families


def test_predictive_forecasting_family_keeps_clear_placeholder_behavior() -> None:
    dataset = build_sales_dataset()

    with pytest.raises(ModelTrainingError, match="Forecasting.*not implemented yet"):
        MlAdapter().execute(ComputeRequest(method_id="forecast", dataset=dataset, parameters={"target": "revenue", "horizon": 3}))

