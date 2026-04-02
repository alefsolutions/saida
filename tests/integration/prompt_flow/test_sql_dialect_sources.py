from __future__ import annotations

import sqlite3

from saida import PromptAnalysisFrontend
from saida.sources import MySQLSource, PostgreSQLSource


def _build_relational_backend_database(database_path) -> None:
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


def test_frontend_analyze_source_runs_end_to_end_against_postgresql_source(tmp_path) -> None:
    database_path = tmp_path / "warehouse_postgresql.sqlite"
    _build_relational_backend_database(database_path)
    source = PostgreSQLSource(
        f"sqlite:///{database_path}",
        'SELECT * FROM "orders"',
        name="warehouse_sales",
    )

    result = PromptAnalysisFrontend().analyze_source(source, "Show a table of total_sales by country")
    payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert payload["status"] == "ok"
    assert payload["result"]["value"] == [
        {"country": "Japan", "target_total": 80.0},
        {"country": "Australia", "target_total": 220.0},
    ]
    assert debug_payload["execution"]["source_provenance"]["source_type"] == "postgresql"
    assert debug_payload["execution"]["source_provenance"]["join_count"] == 1


def test_frontend_analyze_source_runs_end_to_end_against_mysql_source(tmp_path) -> None:
    database_path = tmp_path / "warehouse_mysql.sqlite"
    _build_relational_backend_database(database_path)
    source = MySQLSource(
        f"sqlite:///{database_path}",
        "SELECT * FROM orders",
        name="warehouse_sales",
    )

    result = PromptAnalysisFrontend().analyze_source(source, "Show a table of total_sales by country")
    payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert payload["status"] == "ok"
    assert payload["result"]["value"] == [
        {"country": "Japan", "target_total": 80.0},
        {"country": "Australia", "target_total": 220.0},
    ]
    assert debug_payload["execution"]["source_provenance"]["source_type"] == "mysql"
    assert debug_payload["execution"]["source_provenance"]["join_count"] == 1

