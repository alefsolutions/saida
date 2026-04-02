from __future__ import annotations

from saida.plan_generation import (
    PreparedSourceAnalysis,
    PromptAnalysisFrontend,
    SourceClarification,
    SourceMaterializationResult,
    SourcePlanningContext,
)
from saida.plan_generation.source_orchestration import build_source_clarification
from tests.helpers.relational_fixtures import (
    build_ambiguous_country_sqlite_source,
    build_commerce_sqlite_source,
    build_missing_join_path_sqlite_source,
)


def test_prepare_source_analysis_returns_explicit_contract_objects(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "warehouse.sqlite")
    frontend = PromptAnalysisFrontend()

    prepared = frontend.prepare_source_analysis(source, "Show a table of total_sales by country")

    assert isinstance(prepared, PreparedSourceAnalysis)
    assert isinstance(prepared.planning_context, SourcePlanningContext)
    assert isinstance(prepared.materialization, SourceMaterializationResult)
    assert prepared.plan.metadata["source_orchestration"]["planning_context"]["source_type"] == "sqlite"
    assert prepared.plan.metadata["source_orchestration"]["materialization"]["mode"] == "relational_access_plan"


def test_build_source_clarification_classifies_ambiguous_relational_columns(tmp_path) -> None:
    source = build_ambiguous_country_sqlite_source(tmp_path / "ambiguous_country.sqlite")
    clarification = build_source_clarification(
        Exception("Requested column 'country' is ambiguous across tables: customers, shipments."),
        source_name="warehouse_sales",
        source_type="sqlite",
        source_materialization_request={"required_columns": ["country"]},
        schema_model=source.discover_schema().to_dict(),
    )

    assert isinstance(clarification, SourceClarification)
    assert clarification.reason == "ambiguous_relational_column"
    assert "which table you mean" in clarification.message
    assert "'country'" in clarification.message
    assert clarification.candidate_tables == ["customers", "shipments"]
    assert clarification.suggested_qualified_fields == ["customers.country", "shipments.country"]


def test_build_source_clarification_classifies_missing_join_paths(tmp_path) -> None:
    source = build_missing_join_path_sqlite_source(tmp_path / "missing_join.sqlite")
    clarification = build_source_clarification(
        Exception("No relational join path exists between base table 'orders' and required table 'suppliers'."),
        source_name="warehouse_sales",
        source_type="sqlite",
        source_materialization_request={"required_columns": ["order_id", "supplier_name"]},
        schema_model=source.discover_schema().to_dict(),
    )

    assert clarification.reason == "missing_relational_join_path"
    assert "analyzed together" in clarification.message
    assert "order_id, supplier_name" in clarification.message
    assert clarification.candidate_tables == ["orders", "suppliers"]
    assert "orders.order_id" in clarification.suggested_qualified_fields
    assert "suppliers.supplier_name" in clarification.suggested_qualified_fields


def test_build_source_clarification_suggests_similar_columns_for_unknown_field(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "unknown_field.sqlite")
    clarification = build_source_clarification(
        Exception("Requested column 'contrie' was not found in the relational schema."),
        source_name="warehouse_sales",
        source_type="sqlite",
        source_materialization_request={"required_columns": ["contrie"]},
        schema_model=source.discover_schema().to_dict(),
    )

    assert clarification.reason == "unknown_relational_column"
    assert "Similar columns include" in clarification.message
    assert "country" in clarification.candidate_columns
