from __future__ import annotations

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError
from .factories import build_support_dataset


def test_plan_validator_accepts_graph_style_plan_with_explicit_inputs_outputs_and_final_output() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count rows and expose the scalar as the final artifact.",
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
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
                outputs=[StepOutputSpec(output_id="row_count_value", kind="scalar", logical_shape="count")],
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
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
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
        steps=[
            PlanStep(
                step_id="first_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                description="Count rows first.",
                output_refs=["shared_output"],
            ),
            PlanStep(
                step_id="second_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={"filters": {"reopened_flag": "no"}},
                description="Count filtered rows second.",
                output_refs=["shared_output"],
            ),
        ],
    )

    with pytest.raises(PlanningError, match="duplicate output refs across steps"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_invalid_final_output_ref() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Declare a final output that is never produced.",
        final_output_ref="missing_final",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                description="Count rows.",
                output_refs=["row_count"],
            )
        ],
    )

    with pytest.raises(PlanningError, match="final_output_ref 'missing_final'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_plan_validator_rejects_plan_input_kind_mismatch_for_step_input() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Expecting the wrong input kind should fail.",
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
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
            )
        ],
    )

    with pytest.raises(PlanningError, match="expects input kind 'frame'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)
