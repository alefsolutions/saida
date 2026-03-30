from __future__ import annotations

import pytest

from saida import Saida
from saida.core import PlanValidator
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError
from tests.helpers.factories import build_explicit_single_step_plan, build_sales_dataset, build_support_dataset


def test_plan_validator_accepts_valid_row_count_plan_with_runtime_context() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Count support rows.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={"filters": {"reopened_flag": "no"}},
        description="Count support rows where reopened_flag is no.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )

    engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_unknown_target_column_with_profile_context() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Aggregate a missing column.",
        step_id="aggregate_value",
        tool_family="duckdb",
        method_id="aggregate_value",
        family="aggregation_grouping",
        parameters={"target": "missing_sales", "aggregation": "sum"},
        description="Aggregate a missing metric.",
        expected_result_name="aggregate_value",
        expected_result_shape="scalar",
    )

    with pytest.raises(PlanningError, match="unknown target column"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_missing_required_aggregation_parameter() -> None:
    validator = PlanValidator()
    dataset = build_sales_dataset()
    engine = Saida()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Aggregate revenue without an aggregation method.",
        step_id="aggregate_value",
        tool_family="duckdb",
        method_id="aggregate_value",
        family="aggregation_grouping",
        parameters={"target": "revenue"},
        description="Aggregate revenue.",
        expected_result_name="aggregate_value",
        expected_result_shape="scalar",
    )

    with pytest.raises(PlanningError, match="requires an aggregation parameter"):
        validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_unknown_selected_columns_with_profile_context() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Select a missing field.",
        step_id="tabular_query",
        tool_family="duckdb",
        method_id="tabular_query",
        family="projection_field_selection",
        parameters={"selected_columns": ["ticket_id", "missing_field"]},
        description="Return explicit fields.",
        expected_result_name="tabular_query",
        expected_result_shape="table",
    )

    with pytest.raises(PlanningError, match="unknown selected columns"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_backend_method_mismatch_before_execution() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Route a row count to the stats backend.",
        step_id="row_count",
        tool_family="stats",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={},
        description="Incorrectly route row count to stats.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )

    with pytest.raises(PlanningError, match="does not support method 'row_count'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_incompatible_step_expected_output() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    validator = PlanValidator()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Declare the wrong step output shape.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={},
        description="Count rows.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )
    plan.steps[0].expected_output["logical_shape"] = "table"

    with pytest.raises(PlanningError, match="expects logical_shape 'table'"):
        validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_dataset_ref_mismatch() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Use the wrong dataset ref.",
        dataset_refs=["sales"],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="sales")],
        expected_result_name="row_count",
        expected_result_shape="scalar",
        final_output_ref="row_count",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count support rows.",
                family="aggregation_grouping",
                method_id="row_count",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["row_count"],
                outputs=[StepOutputSpec(output_id="row_count", kind="scalar", logical_shape="scalar", physical_shape="scalar")],
                expected_output={"output_id": "row_count", "logical_shape": "scalar", "physical_shape": "scalar"},
            )
        ],
    )

    with pytest.raises(PlanningError, match="do not include the provided dataset 'support'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_incompatible_plan_result_shape() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Expect a verification result from a row count.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={},
        description="Count rows.",
        expected_result_name="row_count",
        expected_result_shape="verification",
    )

    with pytest.raises(PlanningError, match="expects result shape 'verification'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_unsupported_method_parameter() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Attach a non-contract parameter to row_count.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={"filters": {"reopened_flag": "no"}, "mystery_flag": True},
        description="Count rows with an unsupported extra parameter.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )

    with pytest.raises(PlanningError, match="unsupported parameters"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_invalid_group_by_parameter_shape() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Use a malformed group_by payload.",
        step_id="group_breakdown",
        tool_family="duckdb",
        method_id="group_breakdown",
        family="aggregation_grouping",
        parameters={"target": "resolution_hours", "group_by": "priority", "aggregation": "mean"},
        description="Aggregate by a malformed group_by parameter.",
        expected_result_name="group_breakdown",
        expected_result_shape="table",
    )

    with pytest.raises(PlanningError, match="parameter 'group_by' must be a list of non-empty strings"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_invalid_limit_parameter_value() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Use an invalid pagination limit.",
        step_id="ranked_rows",
        tool_family="duckdb",
        method_id="ranked_rows",
        family="ranking",
        parameters={"target": "resolution_hours", "limit": 0},
        description="Rank rows with an invalid limit.",
        expected_result_name="ranked_rows",
        expected_result_shape="table",
    )

    with pytest.raises(PlanningError, match="parameter 'limit' must be >= 1"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)

