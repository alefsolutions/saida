from __future__ import annotations

from saida import PromptAnalysisFrontend, Saida

from tests.helpers.factories import build_basic_row_count_plan, build_support_dataset


def test_public_schema_contract_for_direct_plan_execution() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.execute_plan(dataset, build_basic_row_count_plan(dataset.name))

    payload = result.to_public_response_dict()

    assert set(payload) == {"schema_version", "status", "interpretation", "execution", "result", "summary", "warnings"}
    assert payload["schema_version"] == "saida.response.v2"
    assert set(payload["interpretation"]) == {"prompt_family", "intent_name", "task_type"}
    assert set(payload["execution"]) == {
        "plan_id",
        "plan_version",
        "step_count",
        "expected_result_name",
        "expected_result_shape",
        "steps",
    }
    assert set(payload["result"]) == {"name", "logical_shape", "physical_shape", "semantic_kind", "shape", "dtype", "value"}
    assert set(payload["summary"]) == {"summary", "deterministic_summary", "llm_summary", "summary_source"}
    assert "request" not in payload
    assert "meta" not in payload
    assert "tables" not in payload
    assert "history" not in payload
    assert "errors" not in payload


def test_public_schema_contract_for_prompt_execution_keeps_only_question_request() -> None:
    dataset = build_support_dataset()
    result = PromptAnalysisFrontend().analyze(dataset, "How many rows are in the dataset?")

    payload = result.to_public_response_dict()

    assert set(payload["request"]) == {"question"}
    assert payload["request"]["question"] == "How many rows are in the dataset?"
    assert "dataset" not in payload["request"]


