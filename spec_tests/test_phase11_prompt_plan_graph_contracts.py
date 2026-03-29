from __future__ import annotations

from saida.plan_generation.frontend import PromptAnalysisFrontend
from saida.plan_generation.planning import AnalysisPlanner
from saida.core.contracts import AnalysisRequest

from .factories import build_support_dataset


def test_planner_emits_explicit_graph_contract_for_prompt_family_plan() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    profile = frontend.profile(build_support_dataset())
    request = AnalysisRequest(
        question="How many tickets are there?",
        prompt_family="row_count",
        task_type_hint="descriptive",
        aggregation="count",
    )

    plan = planner.build_plan(request, profile)

    assert plan.final_output_ref == "row_count"
    assert len(plan.steps) == 1
    assert plan.steps[0].method_id == "row_count"
    assert plan.steps[0].inputs[0].source_type == "plan_input"
    assert plan.steps[0].inputs[0].ref == "primary_dataset"
    assert plan.steps[0].output_refs == ["row_count"]
    assert plan.steps[0].outputs[0].output_id == "row_count"
    assert plan.steps[0].outputs[0].kind == "scalar"
    assert plan.steps[0].outputs[0].logical_shape == "scalar"
    assert plan.steps[0].expected_output == {
        "output_id": "row_count",
        "logical_shape": "scalar",
        "physical_shape": "scalar",
    }


def test_planner_emits_graph_contracts_for_multistep_prompt_plan() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    profile = frontend.profile(build_support_dataset())
    request = AnalysisRequest(
        question="Show resolution_hours",
        prompt_family="exploratory_metric_overview",
        task_type_hint="descriptive",
        target="resolution_hours",
    )

    plan = planner.build_plan(request, profile)

    assert plan.final_output_ref == "summary_metrics"
    assert len(plan.steps) > 3
    assert all(step.method_id for step in plan.steps)
    assert all(step.output_refs for step in plan.steps)
    assert all(step.outputs for step in plan.steps)
    assert all(step.inputs for step in plan.steps)
    assert plan.steps[0].outputs[0].kind == "frame"
    assert plan.steps[0].outputs[0].logical_shape == "table"
    assert plan.steps[-1].outputs[0].kind == "frame"
    assert plan.steps[-1].inputs[0].ref == "overview_source_rows"
