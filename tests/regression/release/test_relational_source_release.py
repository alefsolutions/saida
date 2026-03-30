from __future__ import annotations

import sqlite3

from saida import PromptAnalysisFrontend, Saida
from saida.sources import SQLiteSource

from tests.helpers.factories import build_explicit_single_step_plan


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

    return SQLiteSource(database_path, 'SELECT * FROM "orders"', name="warehouse_sales")


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

    return SQLiteSource(database_path, 'SELECT * FROM "customers"', name="warehouse_sales")


def test_relational_source_release_prompt_flow_materializes_and_executes(tmp_path) -> None:
    source = _build_relational_sqlite_source(tmp_path / "warehouse.sqlite")

    result = PromptAnalysisFrontend().analyze_source(source, "Show a table of total_sales by country")
    payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert payload["status"] == "ok"
    assert payload["interpretation"]["prompt_family"] == "grouped_metric_table"
    assert payload["result"]["value"] == [
        {"country": "Japan", "target_total": 80.0},
        {"country": "Australia", "target_total": 220.0},
    ]
    assert debug_payload["execution"]["source_provenance"]["required_tables"] == ["customers", "orders"]
    assert debug_payload["execution"]["source_provenance"]["join_count"] == 1


def test_relational_source_release_direct_plan_executes_against_materialized_dataset(tmp_path) -> None:
    source = _build_relational_sqlite_source(tmp_path / "warehouse_direct.sqlite")
    dataset = source.load_for_columns(
        required_columns=["country", "total_sales"],
        preferred_base_table="orders",
    )
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Aggregate materialized relational sales by country.",
        step_id="grouped_totals",
        tool_family="duckdb",
        method_id="aggregate_frame",
        family="transformation",
        parameters={"target": "total_sales", "aggregation": "sum", "group_by": ["country"]},
        description="Aggregate relational sales totals by country.",
        expected_result_name="grouped_totals",
        expected_result_shape="table",
    )

    result = Saida().execute_plan(dataset, plan)
    payload = result.to_response_dict()

    assert dataset.metadata["materialization_mode"] == "relational_access_plan"
    assert payload["result"]["logical_shape"] == "table"
    assert payload["result"]["value"] == [
        {"country": "Australia", "aggregate_value": 220.0},
        {"country": "Japan", "aggregate_value": 80.0},
    ]


def test_relational_source_release_ambiguous_prompt_returns_clarification(tmp_path) -> None:
    source = _build_ambiguous_country_source(tmp_path / "warehouse_ambiguous.sqlite")

    result = PromptAnalysisFrontend().analyze_source(source, "List distinct country values")
    payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert payload["status"] == "clarify"
    assert result.plan.task_type == "clarification"
    assert "which table you mean" in payload["summary"]["summary"]
    assert "source_provenance" not in payload["execution"]
    assert debug_payload["execution"]["source_provenance"]["clarification"]["reason"] == "ambiguous_relational_column"
