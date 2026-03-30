from __future__ import annotations

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, Dataset, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError


def test_phase18_executes_join_frame_across_two_upstream_artifacts() -> None:
    engine = Saida()
    dataset = Dataset(
        name="sales_join",
        source_type="pandas",
        data=_joinable_sales_dataframe(),
    )
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Split one dataset into two frames and join them back together.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="joined_rows",
        expected_result_shape="table",
        final_output_ref="joined_rows",
        steps=[
            _step(
                step_id="sales_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["order_id", "region", "revenue"]},
                inputs=[_input("primary_dataset", "plan_input", "primary_dataset", "dataset")],
                output_ref="sales_rows",
            ),
            _step(
                step_id="owner_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["order_id", "owner"]},
                inputs=[_input("primary_dataset", "plan_input", "primary_dataset", "dataset")],
                output_ref="owner_rows",
            ),
            _step(
                step_id="join_sales_owner",
                method_id="join_frame",
                family="joining",
                parameters={"on": "order_id", "how": "inner"},
                inputs=[
                    _input("left_frame", "step_output", "sales_rows", "frame"),
                    _input("right_frame", "step_output", "owner_rows", "frame"),
                ],
                output_ref="joined_rows",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "joined_rows"
    assert result.response["result"]["value"] == [
        {"order_id": 1, "region": "West", "revenue": 100.0, "owner": "Ava"},
        {"order_id": 2, "region": "East", "revenue": 120.0, "owner": "Ben"},
        {"order_id": 3, "region": "West", "revenue": 90.0, "owner": "Cara"},
    ]


def test_phase18_executes_union_frame_across_two_upstream_artifacts() -> None:
    engine = Saida()
    dataset = Dataset(
        name="sales_union",
        source_type="pandas",
        data=_joinable_sales_dataframe(),
    )
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Filter two compatible slices and union them for downstream use.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="unioned_rows",
        expected_result_shape="table",
        final_output_ref="unioned_rows",
        steps=[
            _step(
                step_id="west_rows",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "West"}},
                inputs=[_input("primary_dataset", "plan_input", "primary_dataset", "dataset")],
                output_ref="west_rows",
            ),
            _step(
                step_id="east_rows",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "East"}},
                inputs=[_input("primary_dataset", "plan_input", "primary_dataset", "dataset")],
                output_ref="east_rows",
            ),
            _step(
                step_id="project_west",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["order_id", "region"]},
                inputs=[_input("west_rows", "step_output", "west_rows", "frame")],
                output_ref="west_projected",
            ),
            _step(
                step_id="project_east",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["order_id", "region"]},
                inputs=[_input("east_rows", "step_output", "east_rows", "frame")],
                output_ref="east_projected",
            ),
            _step(
                step_id="union_regions",
                method_id="union_frame",
                family="joining",
                parameters={"distinct": False},
                inputs=[
                    _input("west_input", "step_output", "west_projected", "frame"),
                    _input("east_input", "step_output", "east_projected", "frame"),
                ],
                output_ref="unioned_rows",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "unioned_rows"
    assert result.response["result"]["value"] == [
        {"order_id": 1, "region": "West"},
        {"order_id": 3, "region": "West"},
        {"order_id": 2, "region": "East"},
    ]


def test_phase18_validation_rejects_join_frame_without_two_inputs() -> None:
    engine = Saida()
    dataset = Dataset(
        name="sales_invalid_join",
        source_type="pandas",
        data=_joinable_sales_dataframe(),
    )
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Invalid join plan.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="joined_rows",
        expected_result_shape="table",
        final_output_ref="joined_rows",
        steps=[
            _step(
                step_id="bad_join",
                method_id="join_frame",
                family="joining",
                parameters={"on": "order_id"},
                inputs=[_input("left_only", "plan_input", "primary_dataset", "dataset")],
                output_ref="joined_rows",
            ),
        ],
    )

    with pytest.raises(PlanningError, match="exactly two step inputs"):
        engine.execute_plan(dataset, plan)


def _joinable_sales_dataframe():
    import pandas as pd

    return pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "region": ["West", "East", "West"],
            "revenue": [100.0, 120.0, 90.0],
            "owner": ["Ava", "Ben", "Cara"],
        }
    )


def _step(
    *,
    step_id: str,
    method_id: str,
    family: str,
    parameters: dict[str, object],
    inputs: list[StepInputRef],
    output_ref: str,
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        tool_family="duckdb",
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

