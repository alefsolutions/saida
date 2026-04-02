from __future__ import annotations

from saida import PromptAnalysisFrontend
from tests.helpers.relational_fixtures import (
    build_ambiguous_country_sqlite_source,
    build_commerce_sqlite_source,
    build_missing_join_path_sqlite_source,
    build_simple_sales_sqlite_source,
)


def test_frontend_prepare_source_analysis_builds_source_orchestration_metadata(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "warehouse.sqlite")
    frontend = PromptAnalysisFrontend()

    prepared = frontend.prepare_source_analysis(source, "Show a table of total_sales by country")

    assert prepared.planning_context.source_type == "sqlite"
    assert prepared.planning_context.metadata["planning_mode"] == "schema_discovery"
    assert prepared.materialization.mode == "relational_access_plan"
    assert prepared.materialization.access_plan is not None
    assert prepared.materialization.generated_query is not None
    assert "JOIN" in prepared.materialization.generated_query
    assert prepared.prompt_contract.source_materialization_request is not None
    assert prepared.prompt_contract.source_materialization_request["required_columns"] == ["total_sales", "country"]
    assert prepared.plan.metadata["source_orchestration"]["materialization"]["mode"] == "relational_access_plan"


def test_frontend_prepare_source_analysis_pushes_sort_and_limit_for_latest_rows(tmp_path) -> None:
    source = build_simple_sales_sqlite_source(tmp_path / "warehouse_latest.sqlite")
    frontend = PromptAnalysisFrontend()

    prepared = frontend.prepare_source_analysis(source, "Show the latest 2 rows")

    assert prepared.materialization.generated_query is not None
    assert 'ORDER BY "orders"."order_date" DESC' in prepared.materialization.generated_query
    assert "LIMIT 2" in prepared.materialization.generated_query
    assert prepared.materialization.dataset.metadata["access_plan"]["limit"] == 2


def test_frontend_prepare_source_analysis_pushes_safe_threshold_filters(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "warehouse_filtered.sqlite")
    frontend = PromptAnalysisFrontend()

    prepared = frontend.prepare_source_analysis(source, "How many rows have total_sales greater than 90?")

    assert prepared.materialization.generated_query is not None
    assert 'WHERE "orders"."total_sales" > 90.0' in prepared.materialization.generated_query
    assert prepared.materialization.dataset.metadata["access_plan"]["filters"] == [
        {"source_table": "orders", "source_column": "total_sales", "predicate": {"op": "gt", "value": 90.0}}
    ]


def test_frontend_analyze_source_runs_end_to_end_against_relational_sqlite(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "warehouse.sqlite")
    frontend = PromptAnalysisFrontend()

    result = frontend.analyze_source(source, "Show a table of total_sales by country")

    assert result.response["interpretation"]["prompt_family"] == "grouped_metric_table"
    assert result.response["result"]["value"] == [
        {"country": "Japan", "target_total": 80.0},
        {"country": "Germany", "target_total": 150.0},
        {"country": "Australia", "target_total": 220.0},
    ]
    assert any(event["stage"] == "source" for event in result.response["history"])


def test_frontend_analyze_source_can_join_order_items_and_products_on_richer_fixture(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "warehouse_products.sqlite")
    frontend = PromptAnalysisFrontend()

    result = frontend.analyze_source(source, "Show a table of line_total by product_category")

    assert result.response["status"] == "ok"
    assert result.response["result"]["value"] == [
        {"product_category": "Software", "target_total": 90.0},
        {"product_category": "Hardware", "target_total": 170.0},
        {"product_category": "Services", "target_total": 190.0},
    ]


def test_frontend_analyze_source_returns_clarification_for_ambiguous_relational_columns(tmp_path) -> None:
    source = build_ambiguous_country_sqlite_source(tmp_path / "warehouse_ambiguous.sqlite")
    frontend = PromptAnalysisFrontend()

    result = frontend.analyze_source(source, "List distinct country values")

    assert result.response["status"] == "clarify"
    assert result.plan.task_type == "clarification"
    assert "which table you mean" in result.summary
    assert result.response["request"]["question"] == "List distinct country values"
    assert any(
        warning.startswith("Source materialization was held for clarification")
        for warning in result.response["warnings"]
    )


def test_frontend_analyze_source_returns_clarification_for_missing_join_paths(tmp_path) -> None:
    source = build_missing_join_path_sqlite_source(tmp_path / "warehouse_missing_join.sqlite")
    frontend = PromptAnalysisFrontend()

    result = frontend.analyze_source(source, "Show a table of total_sales by supplier_name")

    assert result.response["status"] == "clarify"
    assert result.plan.task_type == "clarification"
    assert "analyzed together" in result.summary
    assert any(event["stage"] == "source" for event in result.response["history"])
