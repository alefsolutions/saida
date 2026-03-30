from __future__ import annotations

import pytest

from saida import PromptAnalysisFrontend, Saida
from saida.core.contracts import AnalysisPlan, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError

from tests.helpers.factories import build_support_dataset


def test_prompt_frontend_returns_validator_clean_graph_bound_plan() -> None:
    frontend = PromptAnalysisFrontend()
    dataset = build_support_dataset()

    plan = frontend.plan(dataset, "How many rows?")

    assert plan.inputs[0].input_id == "primary_dataset"
    assert plan.final_output_ref == plan.steps[0].output_refs[0]
    assert plan.steps[0].inputs[0].ref == "primary_dataset"
    assert plan.steps[0].outputs[0].output_id == plan.steps[0].output_refs[0]


def test_engine_schedules_fan_out_and_fan_in_dependencies_deterministically() -> None:
    engine = Saida()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Exercise fan-out and fan-in dependency scheduling.",
        steps=[
            PlanStep(
                step_id="source_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                description="Produce a source count.",
                output_refs=["count_value"],
                outputs=[StepOutputSpec(output_id="count_value", kind="scalar", logical_shape="scalar")],
            ),
            PlanStep(
                step_id="left_summary",
                tool_family="stats",
                action="numeric_summary",
                method_id="numeric_summary",
                family="diagnostic_workflows",
                parameters={},
                description="Branch left from the source node.",
                inputs=[StepInputRef(input_id="source_count_input", source_type="step_output", ref="count_value")],
                output_refs=["left_table"],
                outputs=[StepOutputSpec(output_id="left_table", kind="frame", logical_shape="table")],
            ),
            PlanStep(
                step_id="right_summary",
                tool_family="stats",
                action="missingness_summary",
                method_id="missingness_summary",
                family="diagnostic_workflows",
                parameters={},
                description="Branch right from the source node.",
                inputs=[StepInputRef(input_id="source_count_input", source_type="step_output", ref="count_value")],
                output_refs=["right_table"],
                outputs=[StepOutputSpec(output_id="right_table", kind="frame", logical_shape="table")],
            ),
            PlanStep(
                step_id="fan_in",
                tool_family="stats",
                action="distribution_summary",
                method_id="distribution_summary",
                family="diagnostic_workflows",
                parameters={"target": "resolution_hours"},
                description="Depend on both branch outputs before scheduling.",
                inputs=[
                    StepInputRef(input_id="left_input", source_type="step_output", ref="left_table"),
                    StepInputRef(input_id="right_input", source_type="step_output", ref="right_table"),
                ],
                output_refs=["fan_in_table"],
                outputs=[StepOutputSpec(output_id="fan_in_table", kind="frame", logical_shape="table")],
            ),
        ],
    )

    dependencies = engine._build_execution_dependencies(plan)
    scheduled = engine._schedule_steps(plan)

    assert dependencies == {
        "source_count": set(),
        "left_summary": {"source_count"},
        "right_summary": {"source_count"},
        "fan_in": {"left_summary", "right_summary"},
    }
    assert [step.step_id for step in scheduled] == ["source_count", "left_summary", "right_summary", "fan_in"]


def test_engine_rejects_authored_plan_without_explicit_graph_contract_fields() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Legacy authored plan.",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count dataset rows without DAG metadata.",
            )
        ],
    )

    with pytest.raises(PlanningError, match="must declare at least one dataset_ref"):
        engine.execute_plan(dataset, plan)

