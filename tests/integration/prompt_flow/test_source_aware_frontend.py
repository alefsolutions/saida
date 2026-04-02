from __future__ import annotations

import sqlite3

from saida import PromptAnalysisFrontend
from saida.sources import SQLiteSource


def _build_relational_sqlite_source(database_path) -> SQLiteSource:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute("create table customers (customer_id text primary key, country text, region text)")
        connection.execute(
            "create table orders ("
            "order_id text primary key, "
            "customer_id text not null, "
            "order_date text, "
            "total_sales real, "
            "foreign key(customer_id) references customers(customer_id)"
            ")"
        )
        connection.execute("insert into customers values ('C1', 'Australia', 'Oceania')")
        connection.execute("insert into customers values ('C2', 'Japan', 'Asia')")
        connection.execute("insert into orders values ('O1', 'C1', '2026-01-01', 100.0)")
        connection.execute("insert into orders values ('O2', 'C1', '2026-01-02', 120.0)")
        connection.execute("insert into orders values ('O3', 'C2', '2026-01-03', 80.0)")
        connection.commit()
    finally:
        connection.close()

    return SQLiteSource(database_path, "select * from orders", name="warehouse_sales")


def _build_ambiguous_country_source(database_path) -> SQLiteSource:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute("create table customers (customer_id text primary key, country text)")
        connection.execute("create table shipments (shipment_id text primary key, country text)")
        connection.execute("insert into customers values ('C1', 'Australia')")
        connection.execute("insert into shipments values ('S1', 'Japan')")
        connection.commit()
    finally:
        connection.close()

    return SQLiteSource(database_path, "select * from customers", name="warehouse_sales")


def _build_missing_join_path_source(database_path) -> SQLiteSource:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute("create table customers (customer_id text primary key, country text)")
        connection.execute(
            "create table orders ("
            "order_id text primary key, "
            "customer_id text not null, "
            "total_sales real, "
            "foreign key(customer_id) references customers(customer_id)"
            ")"
        )
        connection.execute("create table suppliers (supplier_id text primary key, supplier_name text)")
        connection.execute("insert into customers values ('C1', 'Australia')")
        connection.execute("insert into orders values ('O1', 'C1', 100.0)")
        connection.execute("insert into suppliers values ('S1', 'Contoso')")
        connection.commit()
    finally:
        connection.close()

    return SQLiteSource(database_path, "select * from orders", name="warehouse_sales")


def test_frontend_prepare_source_analysis_builds_source_orchestration_metadata(tmp_path) -> None:
    source = _build_relational_sqlite_source(tmp_path / "warehouse.sqlite")
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
    source = _build_relational_sqlite_source(tmp_path / "warehouse_latest.sqlite")
    frontend = PromptAnalysisFrontend()

    prepared = frontend.prepare_source_analysis(source, "Show the latest 2 rows")

    assert prepared.materialization.generated_query is not None
    assert 'ORDER BY "orders"."order_date" DESC' in prepared.materialization.generated_query
    assert "LIMIT 2" in prepared.materialization.generated_query
    assert prepared.materialization.dataset.metadata["access_plan"]["limit"] == 2


def test_frontend_prepare_source_analysis_pushes_safe_threshold_filters(tmp_path) -> None:
    source = _build_relational_sqlite_source(tmp_path / "warehouse_filtered.sqlite")
    frontend = PromptAnalysisFrontend()

    prepared = frontend.prepare_source_analysis(source, "How many rows have total_sales greater than 90?")

    assert prepared.materialization.generated_query is not None
    assert 'WHERE "orders"."total_sales" > 90.0' in prepared.materialization.generated_query
    assert prepared.materialization.dataset.metadata["access_plan"]["filters"] == [
        {"source_table": "orders", "source_column": "total_sales", "predicate": {"op": "gt", "value": 90.0}}
    ]


def test_frontend_analyze_source_runs_end_to_end_against_relational_sqlite(tmp_path) -> None:
    source = _build_relational_sqlite_source(tmp_path / "warehouse.sqlite")
    frontend = PromptAnalysisFrontend()

    result = frontend.analyze_source(source, "Show a table of total_sales by country")

    assert result.response["interpretation"]["prompt_family"] == "grouped_metric_table"
    assert result.response["result"]["value"] == [
        {"country": "Japan", "target_total": 80.0},
        {"country": "Australia", "target_total": 220.0},
    ]
    assert any(event["stage"] == "source" for event in result.response["history"])


def test_frontend_analyze_source_returns_clarification_for_ambiguous_relational_columns(tmp_path) -> None:
    source = _build_ambiguous_country_source(tmp_path / "warehouse_ambiguous.sqlite")
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
    source = _build_missing_join_path_source(tmp_path / "warehouse_missing_join.sqlite")
    frontend = PromptAnalysisFrontend()

    result = frontend.analyze_source(source, "Show a table of total_sales by supplier_name")

    assert result.response["status"] == "clarify"
    assert result.plan.task_type == "clarification"
    assert "analyzed together" in result.summary
    assert any(event["stage"] == "source" for event in result.response["history"])
