from __future__ import annotations

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError
from .factories import build_explicit_single_step_plan, build_support_dataset


def test_plan_validator_accepts_graph_style_plan_with_explicit_inputs_outputs_and_final_output() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count rows and expose the scalar as the final artifact.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="row_count_value",
        expected_result_shape="scalar",
        final_output_ref="row_count_value",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                description="Count all rows.",
                inputs=[
                    StepInputRef(
                        input_id="dataset_input",
                        source_type="plan_input",
                        ref="primary_dataset",
                        expected_kind="dataset",
                    )
                ],
                output_refs=["row_count_value"],
                outputs=[
                    StepOutputSpec(
                        output_id="row_count_value",
                        kind="scalar",
                        logical_shape="scalar",
                        physical_shape="scalar",
                    )
                ],
                expected_output={
                    "output_id": "row_count_value",
                    "logical_shape": "scalar",
                    "physical_shape": "scalar",
                },
            )
        ],
    )

    engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_unresolved_step_output_reference() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Reference a missing upstream artifact.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="numeric_summary",
        expected_result_shape="table",
        final_output_ref="numeric_summary",
        steps=[
            PlanStep(
                step_id="rank_regions",
                tool_family="stats",
                action="numeric_summary",
                method_id="numeric_summary",
                family="diagnostic_workflows",
                parameters={},
                description="Summarize numeric fields.",
                inputs=[StepInputRef(input_id="missing", source_type="step_output", ref="missing_output")],
                output_refs=["numeric_summary"],
                outputs=[StepOutputSpec(output_id="numeric_summary", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={
                    "output_id": "numeric_summary",
                    "logical_shape": "table",
                    "physical_shape": "recordset",
                },
            )
        ],
    )

    with pytest.raises(PlanningError, match="references unresolved prior output"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_duplicate_output_refs_across_steps() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Two steps cannot produce the same output ref.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="shared_output",
        expected_result_shape="scalar",
        final_output_ref="shared_output",
        steps=[
            PlanStep(
                step_id="first_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                description="Count rows first.",
                inputs=[
                    StepInputRef(
                        input_id="dataset_input",
                        source_type="plan_input",
                        ref="primary_dataset",
                        expected_kind="dataset",
                    )
                ],
                output_refs=["shared_output"],
                outputs=[StepOutputSpec(output_id="shared_output", kind="scalar", logical_shape="scalar", physical_shape="scalar")],
                expected_output={
                    "output_id": "shared_output",
                    "logical_shape": "scalar",
                    "physical_shape": "scalar",
                },
            ),
            PlanStep(
                step_id="second_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={"filters": {"reopened_flag": "no"}},
                description="Count filtered rows second.",
                inputs=[
                    StepInputRef(
                        input_id="dataset_input",
                        source_type="plan_input",
                        ref="primary_dataset",
                        expected_kind="dataset",
                    )
                ],
                output_refs=["shared_output"],
                outputs=[StepOutputSpec(output_id="shared_output", kind="scalar", logical_shape="scalar", physical_shape="scalar")],
                expected_output={
                    "output_id": "shared_output",
                    "logical_shape": "scalar",
                    "physical_shape": "scalar",
                },
            ),
        ],
    )

    with pytest.raises(PlanningError, match="duplicate output refs across steps"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_invalid_final_output_ref() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Declare a final output that is never produced.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={},
        description="Count rows.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )
    plan.final_output_ref = "missing_final"

    with pytest.raises(PlanningError, match="final_output_ref 'missing_final'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_plan_input_kind_mismatch_for_step_input() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Expecting the wrong input kind should fail.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="row_count",
        expected_result_shape="scalar",
        final_output_ref="row_count",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                description="Count rows.",
                inputs=[
                    StepInputRef(
                        input_id="dataset_input",
                        source_type="plan_input",
                        ref="primary_dataset",
                        expected_kind="frame",
                    )
                ],
                output_refs=["row_count"],
                outputs=[StepOutputSpec(output_id="row_count", kind="scalar", logical_shape="scalar", physical_shape="scalar")],
                expected_output={
                    "output_id": "row_count",
                    "logical_shape": "scalar",
                    "physical_shape": "scalar",
                },
            )
        ],
    )

    with pytest.raises(PlanningError, match="expects input kind 'frame'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)
