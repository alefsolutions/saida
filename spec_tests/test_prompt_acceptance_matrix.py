from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from saida import PromptAnalysisFrontend
from saida.core.contracts import Dataset
from .factories import build_support_dataset, json_safe
from .result_helpers import normalized_result_value
from .test_plan_reproducibility import ReproducibilityCase, _REPRODUCIBILITY_CASES, _UNSET


@dataclass(frozen=True, slots=True)
class PromptAcceptanceCase:
    case_id: str
    category: str
    variant_kind: str
    dataset_factory: Callable[[], Dataset]
    question: str
    expected_status: str
    expected_prompt_family: str | None
    expected_intent_name: str | None = None
    expected_task_type: str | None = None
    expected_target: str | None = None
    expected_aggregation: str | None = None
    expected_group_by: tuple[str, ...] = ()
    expected_filters: dict[str, Any] | None = None
    expected_option_subset: dict[str, Any] = field(default_factory=dict)
    expected_step_actions: tuple[str, ...] = ()
    expected_primary_result_name: str = ""
    expected_primary_logical_shape: str | None = None
    expected_primary_value: Any = _UNSET
    expected_summary_contains: str | None = None


@dataclass(frozen=True, slots=True)
class ClarificationPromptCase:
    case_id: str
    question: str
    expected_summary_contains: str


_PROMPT_FORMAT_VARIANTS: tuple[tuple[str, str, Callable[[str], str]], ...] = (
    ("normal-as-is", "normal", lambda prompt: prompt),
    ("edge-question-mark", "edge", lambda prompt: prompt if prompt.endswith("?") else f"{prompt}?"),
    ("edge-period", "edge", lambda prompt: prompt if prompt.endswith(".") else f"{prompt}."),
    ("extreme-uppercase", "extreme", lambda prompt: prompt.upper()),
    ("extreme-padded-whitespace", "extreme", lambda prompt: f"  {prompt}  "),
    ("extreme-newline-wrap", "extreme", lambda prompt: f"\n{prompt}\n"),
)

_NEGATIVE_PROMPT_CASES: tuple[ClarificationPromptCase, ...] = (
    ClarificationPromptCase(
        case_id="ambiguous-data-by-group",
        question="Show data by region",
        expected_summary_contains="Please clarify which metric you want to analyze.",
    ),
    ClarificationPromptCase(
        case_id="ambiguous-factor-analysis",
        question="Which factors significantly affect customer satisfaction?",
        expected_summary_contains="Please clarify which metric you want to analyze.",
    ),
)


def _assert_option_subset(options: dict[str, Any], expected_option_subset: dict[str, Any]) -> None:
    for key, expected_value in expected_option_subset.items():
        assert options.get(key) == expected_value


def _response_payload_signature(result: Any) -> dict[str, Any]:
    payload = result.to_response_dict()
    return {
        "status": payload["status"],
        "result": payload["result"],
        "tables": payload["tables"],
        "warnings": payload["warnings"],
        "metric_lookup": payload["meta"].get("metric_lookup"),
    }


def _canonical_group_by(value: list[str] | None) -> list[str]:
    return list(value or [])


def _canonical_filters(value: dict[str, Any] | None) -> dict[str, Any]:
    return value or {}


def _casefold_filter_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.casefold()
    if isinstance(value, list):
        return [_casefold_filter_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _casefold_filter_value(item) for key, item in value.items()}
    return value


def _build_supported_acceptance_cases() -> tuple[PromptAcceptanceCase, ...]:
    cases: list[PromptAcceptanceCase] = []
    for reproducibility_case in _REPRODUCIBILITY_CASES:
        base_prompt = reproducibility_case.prompts[0]
        for variant_id, variant_kind, formatter in _PROMPT_FORMAT_VARIANTS:
            cases.append(
                PromptAcceptanceCase(
                    case_id=f"true-positive__{reproducibility_case.family_id}__{variant_id}",
                    category="true_positive",
                    variant_kind=variant_kind,
                    dataset_factory=reproducibility_case.dataset_factory,
                    question=formatter(base_prompt),
                    expected_status="ok",
                    expected_prompt_family=reproducibility_case.family_id,
                    expected_intent_name=reproducibility_case.expected_intent_name,
                    expected_task_type=reproducibility_case.expected_task_type,
                    expected_target=reproducibility_case.expected_target,
                    expected_aggregation=reproducibility_case.expected_aggregation,
                    expected_group_by=reproducibility_case.expected_group_by,
                    expected_filters=reproducibility_case.expected_filters,
                    expected_option_subset=reproducibility_case.expected_option_subset,
                    expected_step_actions=reproducibility_case.expected_step_actions,
                    expected_primary_result_name=reproducibility_case.expected_primary_result_name,
                    expected_primary_logical_shape=reproducibility_case.expected_primary_logical_shape,
                    expected_primary_value=reproducibility_case.expected_primary_value,
                )
            )
    return tuple(cases)


def _build_negative_acceptance_cases() -> tuple[PromptAcceptanceCase, ...]:
    cases: list[PromptAcceptanceCase] = []
    for negative_case in _NEGATIVE_PROMPT_CASES:
        for variant_id, variant_kind, formatter in _PROMPT_FORMAT_VARIANTS:
            cases.append(
                PromptAcceptanceCase(
                    case_id=f"true-negative__{negative_case.case_id}__{variant_id}",
                    category="true_negative",
                    variant_kind=variant_kind,
                    dataset_factory=build_support_dataset,
                    question=formatter(negative_case.question),
                    expected_status="clarify",
                    expected_prompt_family=None,
                    expected_primary_result_name="empty_result",
                    expected_summary_contains=negative_case.expected_summary_contains,
                )
            )
    return tuple(cases)


def _build_payload_reproducibility_cases() -> tuple[PromptAcceptanceCase, ...]:
    cases: list[PromptAcceptanceCase] = []
    for reproducibility_case in _REPRODUCIBILITY_CASES:
        cases.append(
            PromptAcceptanceCase(
                case_id=f"payload-reproducibility__{reproducibility_case.family_id}",
                category="payload_reproducibility",
                variant_kind="normal",
                dataset_factory=reproducibility_case.dataset_factory,
                question=reproducibility_case.prompts[0],
                expected_status="ok",
                expected_prompt_family=reproducibility_case.family_id,
                expected_primary_result_name=reproducibility_case.expected_primary_result_name,
            )
        )
    return tuple(cases)


_SUPPORTED_ACCEPTANCE_CASES = _build_supported_acceptance_cases()
_NEGATIVE_ACCEPTANCE_CASES = _build_negative_acceptance_cases()
_PROMPT_ACCEPTANCE_CASES = _SUPPORTED_ACCEPTANCE_CASES + _NEGATIVE_ACCEPTANCE_CASES
_PAYLOAD_REPRODUCIBILITY_CASES = _build_payload_reproducibility_cases()


@pytest.mark.parametrize("case", _PROMPT_ACCEPTANCE_CASES, ids=[case.case_id for case in _PROMPT_ACCEPTANCE_CASES])
def test_prompt_acceptance_matrix_request_and_plan(case: PromptAcceptanceCase) -> None:
    engine = PromptAnalysisFrontend()
    dataset = case.dataset_factory()
    profile = engine.profile(dataset)

    request, warnings = engine.canonicalizer.normalize(case.question, dataset, profile, dataset.context)

    if case.expected_status == "clarify":
        assert warnings
        assert request.options["analysis_outcome"] == "clarify"
        assert request.prompt_family is None
        assert case.expected_summary_contains is not None
        assert case.expected_summary_contains in request.options["llm_message"]
        return

    assert warnings == []
    assert request.options.get("analysis_outcome") != "clarify"
    assert request.prompt_family == case.expected_prompt_family
    assert request.intent_name == case.expected_intent_name
    assert request.task_type_hint == case.expected_task_type
    assert request.target == case.expected_target
    assert request.aggregation == case.expected_aggregation
    assert _canonical_group_by(request.group_by) == list(case.expected_group_by)
    assert json_safe(_casefold_filter_value(_canonical_filters(request.filters))) == json_safe(
        _casefold_filter_value(_canonical_filters(case.expected_filters))
    )
    _assert_option_subset(request.options, case.expected_option_subset)

    plan = engine.plan_builder.build_plan(request, profile, dataset.context)

    assert plan.task_type == case.expected_task_type
    assert tuple(step.action for step in plan.steps) == case.expected_step_actions


@pytest.mark.parametrize("case", _PROMPT_ACCEPTANCE_CASES, ids=[case.case_id for case in _PROMPT_ACCEPTANCE_CASES])
def test_prompt_acceptance_matrix_engine_response(case: PromptAcceptanceCase) -> None:
    engine = PromptAnalysisFrontend()
    dataset = case.dataset_factory()

    result = engine.analyze(dataset, case.question)
    payload = result.to_response_dict()

    assert payload["status"] == case.expected_status
    assert payload["interpretation"]["prompt_family"] == case.expected_prompt_family
    assert payload["result"]["name"] == case.expected_primary_result_name

    if case.expected_status == "clarify":
        assert case.expected_summary_contains is not None
        assert case.expected_summary_contains in result.summary
        return

    assert result.summary
    if case.expected_primary_logical_shape is not None:
        assert payload["result"]["logical_shape"] == case.expected_primary_logical_shape
    if case.expected_primary_value is not _UNSET:
        assert normalized_result_value(payload["result"]) == case.expected_primary_value


@pytest.mark.parametrize(
    "case",
    _PAYLOAD_REPRODUCIBILITY_CASES,
    ids=[case.case_id for case in _PAYLOAD_REPRODUCIBILITY_CASES],
)
def test_prompt_payload_reproducibility_across_format_variants(case: PromptAcceptanceCase) -> None:
    engine = PromptAnalysisFrontend()
    dataset = case.dataset_factory()

    baseline_signature: dict[str, Any] | None = None
    for _, _, formatter in _PROMPT_FORMAT_VARIANTS:
        result = engine.analyze(dataset, formatter(case.question))
        payload_signature = json_safe(_response_payload_signature(result))

        if baseline_signature is None:
            baseline_signature = payload_signature
        else:
            assert payload_signature == baseline_signature

    assert baseline_signature is not None
    assert baseline_signature["status"] == case.expected_status
    assert baseline_signature["result"]["name"] == case.expected_primary_result_name


def test_prompt_acceptance_matrix_expands_positive_negative_edge_and_extreme_coverage() -> None:
    assert len(_SUPPORTED_ACCEPTANCE_CASES) == len(_REPRODUCIBILITY_CASES) * len(_PROMPT_FORMAT_VARIANTS)
    assert len(_NEGATIVE_ACCEPTANCE_CASES) == len(_NEGATIVE_PROMPT_CASES) * len(_PROMPT_FORMAT_VARIANTS)
    assert len(_PROMPT_ACCEPTANCE_CASES) == len(_SUPPORTED_ACCEPTANCE_CASES) + len(_NEGATIVE_ACCEPTANCE_CASES)
    assert len(_PAYLOAD_REPRODUCIBILITY_CASES) == len(_REPRODUCIBILITY_CASES)
