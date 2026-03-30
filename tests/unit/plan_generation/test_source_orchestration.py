from __future__ import annotations

import sqlite3

from saida.plan_generation import (
    PreparedSourceAnalysis,
    PromptAnalysisFrontend,
    SourceClarification,
    SourceMaterializationResult,
    SourcePlanningContext,
)
from saida.plan_generation.source_orchestration import build_source_clarification
from saida.sources import SQLiteSource


def _build_relational_sqlite_source(database_path) -> SQLiteSource:
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
    return SQLiteSource(database_path, "select * from orders", name="warehouse_sales")


def test_prepare_source_analysis_returns_explicit_contract_objects(tmp_path) -> None:
    source = _build_relational_sqlite_source(tmp_path / "warehouse.sqlite")
    frontend = PromptAnalysisFrontend()

    prepared = frontend.prepare_source_analysis(source, "Show a table of total_sales by country")

    assert isinstance(prepared, PreparedSourceAnalysis)
    assert isinstance(prepared.planning_context, SourcePlanningContext)
    assert isinstance(prepared.materialization, SourceMaterializationResult)
    assert prepared.plan.metadata["source_orchestration"]["planning_context"]["source_type"] == "sqlite"
    assert prepared.plan.metadata["source_orchestration"]["materialization"]["mode"] == "relational_access_plan"


def test_build_source_clarification_classifies_ambiguous_relational_columns() -> None:
    clarification = build_source_clarification(
        Exception("Requested column 'country' is ambiguous across tables: customers, shipments."),
        source_name="warehouse_sales",
        source_type="sqlite",
        source_materialization_request={"required_columns": ["country"]},
    )

    assert isinstance(clarification, SourceClarification)
    assert clarification.reason == "ambiguous_relational_column"
    assert "which table you mean" in clarification.message
    assert "'country'" in clarification.message


def test_build_source_clarification_classifies_missing_join_paths() -> None:
    clarification = build_source_clarification(
        Exception("No relational join path exists between base table 'orders' and required table 'suppliers'."),
        source_name="warehouse_sales",
        source_type="sqlite",
        source_materialization_request={"required_columns": ["order_id", "supplier_name"]},
    )

    assert clarification.reason == "missing_relational_join_path"
    assert "analyzed together" in clarification.message
    assert "order_id, supplier_name" in clarification.message
