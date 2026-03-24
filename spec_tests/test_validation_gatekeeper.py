from __future__ import annotations

import pytest

from saida import Saida
from saida.core import PlanValidator
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep
from saida.exceptions import PlanningError
from .factories import build_sales_dataset, build_support_dataset


def test_plan_validator_accepts_valid_row_count_plan_with_runtime_context() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count support rows.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="row_count",
        expected_result_shape="scalar",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={"filters": {"reopened_flag": "no"}},
                description="Count support rows where reopened_flag is no.",
                family="aggregation_grouping",
                method_id="row_count",
                output_refs=["row_count"],
                expected_output={"logical_shape": "scalar"},
            )
        ],
    )

    engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_unknown_target_column_with_profile_context() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Aggregate a missing column.",
        steps=[
            PlanStep(
                step_id="aggregate_value",
                tool_family="duckdb",
                action="aggregate_value",
                parameters={"target": "missing_sales", "aggregation": "sum"},
                description="Aggregate a missing metric.",
                family="aggregation_grouping",
                method_id="aggregate_value",
            )
        ],
    )

    with pytest.raises(PlanningError, match="unknown target column"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_missing_required_aggregation_parameter() -> None:
    validator = PlanValidator()
    dataset = build_sales_dataset()
    engine = Saida()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Aggregate revenue without an aggregation method.",
        steps=[
            PlanStep(
                step_id="aggregate_value",
                tool_family="duckdb",
                action="aggregate_value",
                parameters={"target": "revenue"},
                description="Aggregate revenue.",
                family="aggregation_grouping",
                method_id="aggregate_value",
            )
        ],
    )

    with pytest.raises(PlanningError, match="requires an aggregation parameter"):
        validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_unknown_selected_columns_with_profile_context() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Select a missing field.",
        steps=[
            PlanStep(
                step_id="tabular_query",
                tool_family="duckdb",
                action="tabular_query",
                parameters={"selected_columns": ["ticket_id", "missing_field"]},
                description="Return explicit fields.",
                family="projection_field_selection",
                method_id="tabular_query",
                expected_output={"logical_shape": "recordset"},
            )
        ],
    )

    with pytest.raises(PlanningError, match="unknown selected columns"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_backend_method_mismatch_before_execution() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Route a row count to the stats backend.",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="stats",
                action="row_count",
                parameters={},
                description="Incorrectly route row count to stats.",
                family="aggregation_grouping",
                method_id="row_count",
            )
        ],
    )

    with pytest.raises(PlanningError, match="does not support method 'row_count'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_incompatible_step_expected_output() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    validator = PlanValidator()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Declare the wrong step output shape.",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count rows.",
                family="aggregation_grouping",
                method_id="row_count",
                expected_output={"logical_shape": "table"},
            )
        ],
    )

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
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count support rows.",
                family="aggregation_grouping",
                method_id="row_count",
            )
        ],
    )

    with pytest.raises(PlanningError, match="do not include the provided dataset 'support'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_incompatible_plan_result_shape() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Expect a verification result from a row count.",
        expected_result_shape="verification",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count rows.",
                family="aggregation_grouping",
                method_id="row_count",
            )
        ],
    )

    with pytest.raises(PlanningError, match="expects result shape 'verification'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)
