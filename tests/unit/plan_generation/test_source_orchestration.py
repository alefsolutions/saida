from __future__ import annotations

from saida.plan_generation import (
    PreparedSourceAnalysis,
    PromptAnalysisFrontend,
    SourceClarification,
    SourceMaterializationResult,
    SourcePlanningContext,
)
from saida.plan_generation.source_orchestration import build_source_clarification
from tests.helpers.relational_fixtures import build_commerce_sqlite_source


def test_prepare_source_analysis_returns_explicit_contract_objects(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "warehouse.sqlite")
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
