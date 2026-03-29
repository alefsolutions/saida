from __future__ import annotations

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from .factories import build_sales_dataset, build_support_dataset


def test_phase19_executes_duckdb_filter_into_stats_numeric_summary() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Filter a frame in DuckDB and summarize it in stats.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="west_numeric_summary",
        expected_result_shape="table",
        final_output_ref="west_numeric_summary",
        steps=[
            _step(
                step_id="filter_west",
                tool_family="duckdb",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "West"}},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="west_rows",
            ),
            _step(
                step_id="numeric_summary",
                tool_family="stats",
                method_id="numeric_summary",
                family="diagnostic_workflows",
                parameters={},
                inputs=[_input("prepared_frame", "step_output", "west_rows", "frame")],
                output_ref="west_numeric_summary",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "west_numeric_summary"
    assert result.response["result"]["value"][0]["column"] == "revenue"
    assert float(result.response["result"]["value"][0]["mean"]) == 100.0


def test_phase19_executes_duckdb_select_into_metadata_inventory() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Project columns in DuckDB and inspect the transformed frame in metadata.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="selected_column_inventory",
        expected_result_shape="table",
        final_output_ref="selected_column_inventory",
        steps=[
            _step(
                step_id="project_columns",
                tool_family="duckdb",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["ticket_id", "priority"]},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="selected_rows",
            ),
            _step(
                step_id="column_inventory",
                tool_family="metadata",
                method_id="column_inventory",
                family="schema_metadata_inspection",
                parameters={},
                inputs=[_input("prepared_frame", "step_output", "selected_rows", "frame")],
                output_ref="selected_column_inventory",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "selected_column_inventory"
    assert result.response["result"]["value"] == [
        {"column_name": "ticket_id"},
        {"column_name": "priority"},
    ]


def _step(
    *,
    step_id: str,
    tool_family: str,
    method_id: str,
    family: str,
    parameters: dict[str, object],
    inputs: list[StepInputRef],
    output_ref: str,
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        tool_family=tool_family,
        action=method_id,
        method_id=method_id,
        family=family,
        parameters=parameters,
        description=f"Execute {method_id}.",
        inputs=inputs,
        output_refs=[output_ref],
        outputs=[StepOutputSpec(output_id=output_ref, kind="frame", logical_shape="table", physical_shape="recordset")],
        expected_output={"output_id": output_ref, "logical_shape": "table", "physical_shape": "recordset"},
    )


def _input(input_id: str, source_type: str, ref: str, expected_kind: str) -> StepInputRef:
    return StepInputRef(input_id=input_id, source_type=source_type, ref=ref, expected_kind=expected_kind)
