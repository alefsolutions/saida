from __future__ import annotations

import sqlite3

from saida import PromptAnalysisFrontend, Saida
from saida.sources import SQLiteSource

from tests.helpers.factories import build_basic_row_count_plan, build_support_dataset


def test_debug_schema_contract_preserves_verbose_execution_sections() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.execute_plan(dataset, build_basic_row_count_plan(dataset.name))

    payload = result.to_debug_response_dict()

    assert set(payload) == {
        "schema_version",
        "status",
        "request",
        "interpretation",
        "execution",
        "result",
        "tables",
        "summary",
        "history",
        "warnings",
        "errors",
        "meta",
    }
    assert "artifact_index" in payload["execution"]
    assert "terminal_output_ref" in payload["execution"]
    assert "graph_summary" in payload["execution"]
    assert "artifact_index" in payload["meta"]


def test_public_and_debug_schema_contracts_stay_intentionally_distinct() -> None:
    dataset = build_support_dataset()
    result = PromptAnalysisFrontend().analyze(dataset, "How many rows are in the dataset?")

    public_payload = result.to_public_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert "meta" not in public_payload
    assert "tables" not in public_payload
    assert "history" not in public_payload
    assert "meta" in debug_payload
    assert "tables" in debug_payload
    assert "history" in debug_payload


def test_debug_schema_contract_exposes_source_provenance_for_source_aware_prompt_runs(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
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
        connection.execute("insert into customers values ('C1', 'Australia')")
        connection.execute("insert into orders values ('O1', 'C1', 100.0)")
        connection.commit()
    finally:
        connection.close()

    source = SQLiteSource(database_path, "select * from orders", name="warehouse_sales")
    result = PromptAnalysisFrontend().analyze_source(source, "Show a table of total_sales by country")

    debug_payload = result.to_debug_response_dict()
    public_payload = result.to_public_response_dict()

    assert debug_payload["execution"]["source_provenance"]["source_type"] == "sqlite"
    assert debug_payload["execution"]["source_provenance"]["base_table"] == "orders"
    assert debug_payload["execution"]["source_provenance"]["required_tables"] == ["customers", "orders"]
    assert debug_payload["execution"]["source_provenance"]["join_count"] == 1
    assert "JOIN" in debug_payload["execution"]["source_provenance"]["generated_query"]
    assert debug_payload["meta"]["source_provenance"]["required_columns"] == ["total_sales", "country"]
    assert "source_provenance" not in public_payload["execution"]


