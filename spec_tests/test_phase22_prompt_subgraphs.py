from __future__ import annotations

from saida import PromptAnalysisFrontend
from saida.core.contracts import AnalysisRequest
from saida.plan_generation.planning import AnalysisPlanner

from .factories import build_sales_dataset, build_support_dataset


def test_phase22_planner_builds_metric_aggregate_as_filter_then_reduce_graph() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    profile = frontend.profile(build_sales_dataset())
    request = AnalysisRequest(
        question="What is the average revenue?",
        prompt_family="metric_aggregate",
        task_type_hint="descriptive",
        target="revenue",
        aggregation="mean",
    )

    plan = planner.build_plan(request, profile)

    assert [step.action for step in plan.steps] == ["filter_frame", "aggregate_value"]
    assert plan.steps[1].inputs[0].ref == "metric_aggregate_source"
    assert plan.final_output_ref == "aggregate_value"


def test_phase22_planner_builds_time_bucket_counts_as_graph_subplan() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    profile = frontend.profile(build_support_dataset())
    request = AnalysisRequest(
        question="Count tickets by quarter",
        prompt_family="time_bucket_counts",
        task_type_hint="descriptive",
        options={"time_bucket": "quarter"},
    )

    plan = planner.build_plan(request, profile)

    assert [step.action for step in plan.steps] == ["time_bucket_frame", "aggregate_frame"]
    assert plan.steps[1].parameters["group_by"] == ["quarter"]
    assert plan.final_output_ref == "time_bucket_counts"


def test_phase22_planner_builds_time_period_comparison_from_bucketed_artifact() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    profile = frontend.profile(build_sales_dataset())
    request = AnalysisRequest(
        question="Compare revenue this quarter to last quarter",
        prompt_family="time_period_comparison",
        task_type_hint="descriptive",
        target="revenue",
        time_reference={"type": "relative_period", "value": "this_quarter"},
        options={"time_bucket": "quarter"},
    )

    plan = planner.build_plan(request, profile)

    assert [step.action for step in plan.steps] == ["time_bucket_frame", "period_comparison"]
    assert plan.steps[1].inputs[0].ref == "bucketed_rows"
    assert plan.final_output_ref == "period_comparison"


def test_phase22_frontend_emits_graph_native_row_ranking_steps() -> None:
    frontend = PromptAnalysisFrontend()
    dataset = build_support_dataset()

    result = frontend.analyze(dataset, "Show top 2 resolution_hours values")

    assert result.response["interpretation"]["prompt_family"] == "row_ranking"
    assert [step["action"] for step in result.response["execution"]["steps"]] == ["filter_frame", "rank_frame"]
    assert result.response["execution"]["final_output_ref"] == "ranked_rows"


def test_phase22_frontend_keeps_exploratory_overview_on_shared_source_graph() -> None:
    frontend = PromptAnalysisFrontend()
    dataset = build_sales_dataset()

    result = frontend.analyze(dataset, "Show revenue")

    actions = [step["action"] for step in result.response["execution"]["steps"]]

    assert result.response["interpretation"]["prompt_family"] == "exploratory_metric_overview"
    assert actions[:4] == ["filter_frame", "dataset_summary", "time_bucket_frame", "aggregate_frame"]
    assert "numeric_summary" in actions
    assert result.response["execution"]["final_output_ref"] == "summary_metrics"
