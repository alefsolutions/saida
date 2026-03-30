from __future__ import annotations

from saida import PromptAnalysisFrontend, Saida

from .factories import build_basic_row_count_plan, build_support_dataset


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

