from __future__ import annotations

from saida import PromptAnalysisFrontend
from saida.core.contracts import AnalysisRequest
from saida.plan_generation import build_default_graph_template_catalog
from saida.plan_generation.graph_templates import (
    build_grouped_table_template,
    build_time_period_comparison_template,
)
from saida.plan_generation.planning import AnalysisPlanner

from .factories import build_sales_dataset, build_support_dataset


def test_phase23_graph_template_catalog_exposes_reusable_pipelines() -> None:
    catalog = build_default_graph_template_catalog()

    assert set(catalog) >= {
        "grouped_table_pipeline",
        "group_ranking_pipeline",
        "time_bucket_breakdown_pipeline",
        "time_period_comparison_pipeline",
        "row_ranking_pipeline",
        "metric_aggregate_pipeline",
        "exploratory_metric_overview_pipeline",
    }
    assert catalog["grouped_table_pipeline"].supported_prompt_families == (
        "grouped_entity_count",
        "grouped_metric_table",
    )


def test_phase23_template_builder_produces_grouped_pipeline_steps() -> None:
    request = AnalysisRequest(
        question="Show top 2 revenue by region",
        prompt_family="grouped_metric_table",
        target="revenue",
        group_by=["region"],
        aggregation="sum",
        options={"sort_direction": "desc", "limit": 2},
    )

    template = build_grouped_table_template(
        request,
        aggregation="sum",
        value_label="target_total",
        final_output_ref="grouped_tabular_query",
    )

    assert template.template_id == "grouped_table_pipeline"
    assert [step.action for step in template.steps] == ["group_frame", "aggregate_frame", "sort_frame", "limit_frame"]
    assert template.steps[1].inputs[0].ref == "grouped_source_rows"
    assert template.final_output_ref == "grouped_tabular_query"


def test_phase23_planner_tags_grouped_metric_plan_with_template_id() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    request = AnalysisRequest(
        question="Show top 2 revenue by region",
        prompt_family="grouped_metric_table",
        intent_name="grouped_tabular_query",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
        aggregation="sum",
        options={"sort_direction": "desc", "limit": 2},
    )

    plan = planner.build_plan(request, frontend.profile(build_sales_dataset()))

    assert plan.metadata["graph_template_id"] == "grouped_table_pipeline"
    assert [step.action for step in plan.steps] == ["group_frame", "aggregate_frame", "sort_frame", "limit_frame"]


def test_phase23_planner_tags_time_period_comparison_with_template_id() -> None:
    planner = AnalysisPlanner()
    frontend = PromptAnalysisFrontend()
    support = build_support_dataset()
    request = AnalysisRequest(
        question="Compare average resolution hours month over month",
        prompt_family="time_period_comparison",
        intent_name="time_period_comparison",
        task_type_hint="descriptive",
        target="resolution_hours",
        time_reference={"type": "relative_period", "value": "this_month"},
        aggregation="mean",
        options={"time_bucket": "month"},
    )

    plan = planner.build_plan(request, frontend.profile(support))

    assert plan.metadata["graph_template_id"] == "time_period_comparison_pipeline"
    assert plan.final_output_ref == "period_comparison"
    assert [step.action for step in plan.steps] == ["time_bucket_frame", "period_comparison"]


def test_phase23_time_period_template_uses_bucketed_rows_output() -> None:
    frontend = PromptAnalysisFrontend()
    support = build_support_dataset()
    request = AnalysisRequest(
        question="Compare average resolution hours month over month",
        prompt_family="time_period_comparison",
        target="resolution_hours",
        time_reference={"type": "relative_period", "value": "this_month"},
        aggregation="mean",
        options={"time_bucket": "month"},
    )

    template = build_time_period_comparison_template(request, frontend.profile(support))

    assert template.template_id == "time_period_comparison_pipeline"
    assert template.steps[1].inputs[0].ref == "bucketed_rows"
    assert template.final_output_ref == "period_comparison"
