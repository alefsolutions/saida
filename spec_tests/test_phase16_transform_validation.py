from __future__ import annotations

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError

from .factories import build_sales_dataset


def test_phase16_validator_accepts_explicit_transform_chain_plan() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Filter, project, sort, and limit rows through explicit transform nodes.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="limited_rows",
        expected_result_shape="table",
        final_output_ref="limited_rows",
        steps=[
            PlanStep(
                step_id="filter_west",
                tool_family="duckdb",
                action="filter_frame",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "West"}},
                description="Filter rows to West only.",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["west_rows"],
                outputs=[StepOutputSpec(output_id="west_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "west_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
            PlanStep(
                step_id="project_columns",
                tool_family="duckdb",
                action="select_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["posted_at", "revenue"]},
                description="Project the final columns.",
                inputs=[StepInputRef(input_id="frame_input", source_type="step_output", ref="west_rows", expected_kind="frame")],
                output_refs=["projected_rows"],
                outputs=[StepOutputSpec(output_id="projected_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "projected_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
            PlanStep(
                step_id="limit_rows",
                tool_family="duckdb",
                action="limit_frame",
                method_id="limit_frame",
                family="selection_filtering",
                parameters={"limit": 2, "sort_by": "posted_at", "sort_direction": "desc"},
                description="Return the latest two rows.",
                inputs=[StepInputRef(input_id="frame_input", source_type="step_output", ref="projected_rows", expected_kind="frame")],
                output_refs=["limited_rows"],
                outputs=[StepOutputSpec(output_id="limited_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "limited_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
        ],
    )

    engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_phase16_validator_rejects_missing_selected_columns_for_select_columns() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Missing projection columns should fail validation.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="projected_rows",
        expected_result_shape="table",
        final_output_ref="projected_rows",
        steps=[
            PlanStep(
                step_id="project_columns",
                tool_family="duckdb",
                action="select_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={},
                description="Missing selected_columns.",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["projected_rows"],
                outputs=[StepOutputSpec(output_id="projected_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "projected_rows", "logical_shape": "table", "physical_shape": "recordset"},
            )
        ],
    )

    with pytest.raises(PlanningError, match="selected_columns"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_phase16_validator_rejects_missing_expression_for_derive_column() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Missing derive expression should fail validation.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="derived_rows",
        expected_result_shape="table",
        final_output_ref="derived_rows",
        steps=[
            PlanStep(
                step_id="derive_value",
                tool_family="duckdb",
                action="derive_column",
                method_id="derive_column",
                family="transformation",
                parameters={"target": "revenue_twice"},
                description="Missing expression.",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["derived_rows"],
                outputs=[StepOutputSpec(output_id="derived_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "derived_rows", "logical_shape": "table", "physical_shape": "recordset"},
            )
        ],
    )

    with pytest.raises(PlanningError, match="expression"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)
