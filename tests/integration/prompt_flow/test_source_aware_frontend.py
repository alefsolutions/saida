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
