from __future__ import annotations

import pytest

from saida import PromptAnalysisFrontend, Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec

from .factories import build_sales_dataset, build_support_dataset


def test_phase25_prompt_frontend_emits_execution_ready_plans_without_runtime_binding_metadata() -> None:
    frontend = PromptAnalysisFrontend()
    dataset = build_support_dataset()

    plan = frontend.plan(dataset, "How many rows are in the dataset?")
    result = frontend.analyze(dataset, "How many rows are in the dataset?")

    assert plan.dataset_refs == [dataset.name]
    assert plan.inputs[0].input_id == "primary_dataset"
    assert plan.final_output_ref == "row_count"
    assert plan.plan_id is not None
    assert "contract_binding" not in result.response["execution"]
    assert "contract_binding" not in result.response["meta"]


def test_phase25_execute_plan_surfaces_invalid_graph_operation_errors() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Surface bad downstream graph operations instead of hiding them.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="bad_sort_rows",
        expected_result_shape="table",
        final_output_ref="bad_sort_rows",
        steps=[
            PlanStep(
                step_id="project_columns",
                tool_family="duckdb",
                action="select_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["posted_at", "revenue"]},
                description="Project only supported columns.",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["projected_rows"],
                outputs=[StepOutputSpec(output_id="projected_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "projected_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
            PlanStep(
                step_id="bad_sort",
                tool_family="duckdb",
                action="sort_frame",
                method_id="sort_frame",
                family="selection_filtering",
                parameters={"sort_by": "missing_column", "sort_direction": "desc"},
                description="Sort on a column that does not exist in the upstream frame.",
                inputs=[StepInputRef(input_id="frame_input", source_type="step_output", ref="projected_rows", expected_kind="frame")],
                output_refs=["bad_sort_rows"],
                outputs=[StepOutputSpec(output_id="bad_sort_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "bad_sort_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
        ],
    )

    with pytest.raises(Exception, match="missing_column|Binder Error|not found"):
        engine.execute_plan(dataset, plan)
