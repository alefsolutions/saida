from __future__ import annotations

from saida import PromptAnalysisFrontend
from saida.sources import MySQLSource, PostgreSQLSource
from tests.helpers.relational_fixtures import build_commerce_sql_query_source


def test_frontend_analyze_source_runs_end_to_end_against_postgresql_source(tmp_path) -> None:
    source = build_commerce_sql_query_source(PostgreSQLSource, tmp_path / "warehouse_postgresql.sqlite")

    result = PromptAnalysisFrontend().analyze_source(source, "Show a table of total_sales by country")
    payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert payload["status"] == "ok"
    assert payload["result"]["value"] == [
        {"country": "Japan", "target_total": 80.0},
        {"country": "Germany", "target_total": 150.0},
        {"country": "Australia", "target_total": 220.0},
    ]
    assert debug_payload["execution"]["source_provenance"]["source_type"] == "postgresql"
    assert debug_payload["execution"]["source_provenance"]["join_count"] == 1


def test_frontend_analyze_source_runs_end_to_end_against_mysql_source(tmp_path) -> None:
    source = build_commerce_sql_query_source(MySQLSource, tmp_path / "warehouse_mysql.sqlite")

    result = PromptAnalysisFrontend().analyze_source(source, "Show a table of total_sales by country")
    payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert payload["status"] == "ok"
    assert payload["result"]["value"] == [
        {"country": "Japan", "target_total": 80.0},
        {"country": "Germany", "target_total": 150.0},
        {"country": "Australia", "target_total": 220.0},
    ]
    assert debug_payload["execution"]["source_provenance"]["source_type"] == "mysql"
    assert debug_payload["execution"]["source_provenance"]["join_count"] == 1
