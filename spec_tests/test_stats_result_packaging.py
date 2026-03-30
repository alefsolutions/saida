from __future__ import annotations

from saida import Saida
from .factories import build_explicit_single_step_plan, build_statistical_dataset


def test_statistical_result_packaging_exposes_statistical_shape_and_debug_lineage() -> None:
    engine = Saida()
    dataset = build_statistical_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="statistical",
        rationale="Package a confidence interval result for release coverage.",
        step_id="confidence_interval",
        tool_family="stats",
        method_id="confidence_interval",
        family="statistical_inference",
        parameters={"target": "revenue", "confidence_level": 0.95},
        description="Execute confidence interval.",
        expected_result_name="confidence_interval",
        expected_result_shape="table",
    )

    result = engine.execute_plan(dataset, plan)
    public_payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert public_payload["result"]["logical_shape"] == "statistical_test"
    assert public_payload["result"]["semantic_kind"] == "statistical_test"
    assert public_payload["result"]["shape"] == {"logical": "statistical_test", "physical": "recordset"}
    assert debug_payload["execution"]["terminal_output_ref"] == "confidence_interval"
    assert debug_payload["execution"]["terminal_lineage"]["producer_step_id"] == "confidence_interval"
    assert debug_payload["execution"]["terminal_output"]["semantic_kind"] == "statistical_test"

