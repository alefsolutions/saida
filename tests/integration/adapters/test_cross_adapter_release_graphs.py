from __future__ import annotations

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError

from tests.helpers.factories import build_sales_dataset, build_support_dataset


def test_release_cross_adapter_join_then_stats_summary() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Join two projected support artifacts and summarize the joined frame in stats.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="joined_numeric_summary",
        expected_result_shape="table",
        final_output_ref="joined_numeric_summary",
        steps=[
            _frame_step(
                step_id="left_projection",
                tool_family="duckdb",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["ticket_id", "resolution_hours"]},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="left_rows",
            ),
            _frame_step(
                step_id="right_projection",
                tool_family="duckdb",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["ticket_id", "priority"]},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="right_rows",
            ),
            _frame_step(
                step_id="join_rows",
                tool_family="duckdb",
                method_id="join_frame",
                family="joining",
                parameters={"on": "ticket_id", "how": "inner"},
                inputs=[
                    _input("left_frame", "step_output", "left_rows", "frame"),
                    _input("right_frame", "step_output", "right_rows", "frame"),
                ],
                output_ref="joined_rows",
            ),
            _frame_step(
                step_id="numeric_summary",
                tool_family="stats",
                method_id="numeric_summary",
                family="diagnostic_workflows",
                parameters={},
                inputs=[_input("prepared_frame", "step_output", "joined_rows", "frame")],
                output_ref="joined_numeric_summary",
                semantic_kind="statistical_test",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["execution"]["step_count"] == 4
    assert result.response["execution"]["terminal_output_ref"] == "joined_numeric_summary"
    assert result.response["result"]["name"] == "joined_numeric_summary"
    assert result.response["result"]["logical_shape"] == "table"
    assert result.response["result"]["value"][0]["column"] == "resolution_hours"


def test_release_cross_adapter_union_then_metadata_inventory() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Union projected support slices and inspect the merged frame in metadata.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="union_column_inventory",
        expected_result_shape="table",
        final_output_ref="union_column_inventory",
        steps=[
            _frame_step(
                step_id="support_slice",
                tool_family="duckdb",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"team": "Support"}},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="support_rows",
            ),
            _frame_step(
                step_id="platform_slice",
                tool_family="duckdb",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"team": "Platform"}},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="platform_rows",
            ),
            _frame_step(
                step_id="project_support",
                tool_family="duckdb",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["ticket_id", "team", "priority"]},
                inputs=[_input("source_frame", "step_output", "support_rows", "frame")],
                output_ref="support_projected",
            ),
            _frame_step(
                step_id="project_platform",
                tool_family="duckdb",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["ticket_id", "team", "priority"]},
                inputs=[_input("source_frame", "step_output", "platform_rows", "frame")],
                output_ref="platform_projected",
            ),
            _frame_step(
                step_id="union_rows",
                tool_family="duckdb",
                method_id="union_frame",
                family="joining",
                parameters={"distinct": False},
                inputs=[
                    _input("left_frame", "step_output", "support_projected", "frame"),
                    _input("right_frame", "step_output", "platform_projected", "frame"),
                ],
                output_ref="unioned_rows",
            ),
            _frame_step(
                step_id="column_inventory",
                tool_family="metadata",
                method_id="column_inventory",
                family="schema_metadata_inspection",
                parameters={},
                inputs=[_input("prepared_frame", "step_output", "unioned_rows", "frame")],
                output_ref="union_column_inventory",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["execution"]["step_count"] == 6
    assert result.response["result"]["name"] == "union_column_inventory"
    assert result.response["result"]["value"] == [
        {"column_name": "ticket_id"},
        {"column_name": "team"},
        {"column_name": "priority"},
    ]


def test_release_validation_rejects_multi_input_into_non_merge_transform() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Reject invalid fan-in into a non-merge transform.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="bad_sort_rows",
        expected_result_shape="table",
        final_output_ref="bad_sort_rows",
        steps=[
            _frame_step(
                step_id="west_rows",
                tool_family="duckdb",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "West"}},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="west_rows",
            ),
            _frame_step(
                step_id="east_rows",
                tool_family="duckdb",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "East"}},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="east_rows",
            ),
            PlanStep(
                step_id="bad_sort",
                tool_family="duckdb",
                action="sort_frame",
                method_id="sort_frame",
                family="selection_filtering",
                parameters={"sort_by": "revenue", "sort_direction": "desc"},
                description="Invalidly feed two upstream frames into sort_frame.",
                inputs=[
                    _input("left_frame", "step_output", "west_rows", "frame"),
                    _input("right_frame", "step_output", "east_rows", "frame"),
                ],
                output_refs=["bad_sort_rows"],
                outputs=[StepOutputSpec(output_id="bad_sort_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "bad_sort_rows", "logical_shape": "table", "physical_shape": "recordset"},
            ),
        ],
    )

    with pytest.raises(PlanningError, match="multiple upstream artifacts"):
        engine.execute_plan(dataset, plan)


def test_release_terminal_output_ref_honors_requested_branch_in_branched_graph() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Branch a filtered frame into grouped and statistical outputs, but keep the grouped table terminal.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="grouped_totals",
        expected_result_shape="table",
        final_output_ref="grouped_totals",
        steps=[
            _frame_step(
                step_id="filter_frame",
                tool_family="duckdb",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "West"}},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="west_rows",
            ),
            _frame_step(
                step_id="group_rows",
                tool_family="duckdb",
                method_id="group_frame",
                family="transformation",
                parameters={"group_by": ["segment"]},
                inputs=[_input("source_frame", "step_output", "west_rows", "frame")],
                output_ref="grouped_rows",
            ),
            _frame_step(
                step_id="grouped_totals",
                tool_family="duckdb",
                method_id="aggregate_frame",
                family="transformation",
                parameters={"target": "revenue", "aggregation": "sum", "value_label": "target_total"},
                inputs=[_input("grouped_rows_input", "step_output", "grouped_rows", "frame")],
                output_ref="grouped_totals",
            ),
            _frame_step(
                step_id="distribution_summary",
                tool_family="stats",
                method_id="distribution_summary",
                family="diagnostic_workflows",
                parameters={"target": "revenue"},
                inputs=[_input("prepared_frame", "step_output", "west_rows", "frame")],
                output_ref="distribution_rows",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["execution"]["terminal_output_ref"] == "grouped_totals"
    assert result.response["result"]["name"] == "grouped_totals"
    assert result.response["result"]["value"] == [{"segment": "SMB", "target_total": 300.0}]
    assert "distribution_rows" in result.response["execution"]["secondary_outputs"][0]["name"]


def _frame_step(
    *,
    step_id: str,
    tool_family: str,
    method_id: str,
    family: str,
    parameters: dict[str, object],
    inputs: list[StepInputRef],
    output_ref: str,
    semantic_kind: str | None = None,
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
        outputs=[
            StepOutputSpec(
                output_id=output_ref,
                kind="frame",
                logical_shape="table",
                physical_shape="recordset",
                semantic_kind=semantic_kind,
            )
        ],
        expected_output={"output_id": output_ref, "logical_shape": "table", "physical_shape": "recordset"},
    )


def _input(input_id: str, source_type: str, ref: str, expected_kind: str) -> StepInputRef:
    return StepInputRef(input_id=input_id, source_type=source_type, ref=ref, expected_kind=expected_kind)

