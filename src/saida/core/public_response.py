"""Helpers for compact public response serialization."""

from __future__ import annotations

from typing import Any

from saida.core.contracts import AnalysisInterpretation, AnalysisPlan


def is_synthetic_plan_question(plan: AnalysisPlan, request: AnalysisInterpretation) -> bool:
    """Return whether the request question is a synthetic execute-plan placeholder."""
    origin_question = plan.metadata.get("origin_question") if isinstance(plan.metadata, dict) else None
    if isinstance(origin_question, str) and origin_question == request.question:
        return False
    synthetic_prefixes = (
        "Execute analysis plan",
        f"Execute {plan.plan_id} plan" if plan.plan_id else "",
        f"Execute {plan.task_type} plan",
    )
    return any(prefix and request.question.startswith(prefix) for prefix in synthetic_prefixes)


def build_public_analysis_response(
    summary: str,
    llm_summary: str | None,
    plan: AnalysisPlan,
    request: AnalysisInterpretation,
    debug_response: dict[str, object],
) -> dict[str, object]:
    """Build the compact public-facing analysis response."""
    debug_execution = debug_response.get("execution")
    debug_result = debug_response.get("result")
    debug_summary = debug_response.get("summary")
    execution_payload = debug_execution if isinstance(debug_execution, dict) else {}
    result_payload = debug_result if isinstance(debug_result, dict) else {}
    summary_payload = debug_summary if isinstance(debug_summary, dict) else {}

    steps: list[dict[str, Any]] = []
    for step in execution_payload.get("steps", []):
        if not isinstance(step, dict):
            continue
        steps.append(
            {
                "step_id": step.get("step_id"),
                "tool_family": step.get("tool_family"),
                "method_id": step.get("method_id"),
                "action": step.get("action"),
                "description": step.get("description"),
            }
        )

    public_request: dict[str, object] = {}
    if llm_summary is not None:
        public_request["llm_summary"] = llm_summary
    if request.question and not is_synthetic_plan_question(plan, request):
        public_request["question"] = request.question

    public_response: dict[str, object] = {
        "schema_version": debug_response.get("schema_version", "saida.response.v2"),
        "status": debug_response.get("status", "ok"),
        "interpretation": {
            "prompt_family": request.prompt_family,
            "intent_name": request.intent_name,
            "task_type": plan.task_type,
        },
        "execution": {
            "plan_id": execution_payload.get("plan_id"),
            "plan_version": execution_payload.get("plan_version"),
            "step_count": execution_payload.get("step_count"),
            "expected_result_name": execution_payload.get("expected_result_name"),
            "expected_result_shape": execution_payload.get("expected_result_shape"),
            "steps": steps,
        },
        "result": {
            "name": result_payload.get("name"),
            "logical_shape": result_payload.get("logical_shape"),
            "physical_shape": result_payload.get("physical_shape"),
            "semantic_kind": result_payload.get("semantic_kind"),
            "shape": {
                "logical": result_payload.get("logical_shape"),
                "physical": result_payload.get("physical_shape"),
            },
            "dtype": result_payload.get("dtype"),
            "value": result_payload.get("value"),
        },
        "summary": {
            "summary": summary_payload.get("summary", summary),
            "deterministic_summary": summary_payload.get("deterministic_summary"),
            "llm_summary": summary_payload.get("llm_summary"),
            "summary_source": summary_payload.get("summary_source"),
        },
        "warnings": list(debug_response.get("warnings") or []),
    }
    if public_request:
        public_response["request"] = public_request
    return public_response
