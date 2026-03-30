from __future__ import annotations

from saida import PromptAnalysisFrontend, Saida

from tests.helpers.factories import build_basic_row_count_plan, build_support_dataset


def test_response_modes_expose_compact_public_payload_and_verbose_debug_payload() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.execute_plan(dataset, build_basic_row_count_plan(dataset.name))

    public_payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert "artifact_index" not in public_payload["execution"]
    assert "meta" not in public_payload
    assert public_payload["result"]["value"] == 7
    assert debug_payload["execution"]["artifact_index"]["primary_dataset"]["summarized"] is True


def test_prompt_frontend_public_response_keeps_question_but_direct_plan_payload_can_omit_it() -> None:
    frontend = PromptAnalysisFrontend()
    dataset = build_support_dataset()

    prompted_result = frontend.analyze(dataset, "How many rows are in the dataset?")
    direct_result = Saida().execute_plan(
        dataset,
        build_basic_row_count_plan(dataset.name),
    )

    assert prompted_result.to_response_dict()["request"]["question"] == "How many rows are in the dataset?"
    assert "request" not in direct_result.to_response_dict() or "question" not in direct_result.to_response_dict().get("request", {})

