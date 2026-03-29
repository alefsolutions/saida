from __future__ import annotations

from saida import PromptAnalysisFrontend
from saida.core.contracts import AnalysisRequest
from saida.plan_generation.planning import AnalysisPlanner

from .factories import build_sales_dataset, build_support_dataset
from .result_helpers import normalized_result_value


def test_phase17_planner_builds_distinct_count_as_graph_template() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    profile = frontend.profile(build_support_dataset())
    request = AnalysisRequest(
        question="How many unique team values are there?",
        prompt_family="distinct_value_count",
        intent_name="distinct_value_count",
        task_type_hint="descriptive",
        target="team",
    )

    plan = planner.build_plan(request, profile)

    assert [step.action for step in plan.steps] == ["distinct_frame", "row_count"]
    assert plan.final_output_ref == "distinct_value_count"
    assert plan.steps[1].inputs[0].ref == "distinct_values"


def test_phase17_planner_builds_group_ranking_as_graph_template() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    profile = frontend.profile(build_sales_dataset())
    request = AnalysisRequest(
        question="Show top 2 revenue by region",
        prompt_family="group_ranking",
        intent_name="group_ranking",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
        options={"ranking_limit": 2, "ranking_direction": "desc"},
    )

    plan = planner.build_plan(request, profile)

    assert [step.action for step in plan.steps] == ["group_frame", "aggregate_frame", "rank_frame"]
    assert plan.final_output_ref == "ranked_breakdown"
    assert plan.steps[-1].parameters["sort_by"] == "target_total"


def test_phase17_prompt_analysis_preserves_public_group_ranking_output() -> None:
    frontend = PromptAnalysisFrontend()
    dataset = build_sales_dataset()

    result = frontend.analyze(dataset, "Show top 2 revenue by region")

    assert result.response["interpretation"]["prompt_family"] == "group_ranking"
    assert [step["action"] for step in result.response["execution"]["steps"]] == ["group_frame", "aggregate_frame", "rank_frame"]
    assert result.response["result"]["name"] == "ranked_breakdown"
    assert normalized_result_value(result.response["result"])[0] == {
        "rank": 1,
        "region": "East",
        "target_total": 330.0,
    }
