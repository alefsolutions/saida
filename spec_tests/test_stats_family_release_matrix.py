from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import pytest

from saida import Saida
from .factories import build_explicit_single_step_plan, build_statistical_dataset


@dataclass(frozen=True, slots=True)
class StatisticalReleaseCase:
    case_id: str
    question: str
    method_id: str
    parameters: dict[str, object]
    expected_summary_snippet: str


_STATISTICAL_RELEASE_CASES = [
    StatisticalReleaseCase(
        "significance_inference",
        "Do regions differ in revenue?",
        "significance_inference",
        {"target": "revenue", "group_by": ["region"], "alpha": 0.05},
        "Welch t-test for revenue by region",
    ),
    StatisticalReleaseCase(
        "t_test",
        "Run a t-test on revenue by region",
        "t_test",
        {"target": "revenue", "group_by": ["region"], "alpha": 0.05},
        "Welch t-test for revenue by region",
    ),
    StatisticalReleaseCase(
        "chi_square",
        "Run chi-square between team and segment",
        "chi_square",
        {"comparison_columns": ["team", "segment"], "alpha": 0.05},
        "Chi-square test for team and segment",
    ),
    StatisticalReleaseCase(
        "anova",
        "Run anova on revenue by team",
        "anova",
        {"target": "revenue", "group_by": ["team"], "alpha": 0.05},
        "ANOVA for revenue by team",
    ),
    StatisticalReleaseCase(
        "mann_whitney",
        "Run Mann-Whitney on revenue by region",
        "mann_whitney",
        {"target": "revenue", "group_by": ["region"], "alpha": 0.05},
        "Mann-Whitney test for revenue by region",
    ),
    StatisticalReleaseCase(
        "confidence_interval",
        "What range are we 95% confident revenue falls in?",
        "confidence_interval",
        {"target": "revenue", "confidence_level": 0.95},
        "confidence interval for revenue",
    ),
    StatisticalReleaseCase(
        "regression_significance",
        "Does cost and units significantly affect revenue?",
        "regression_significance",
        {"target": "revenue", "feature_columns": ["cost", "units"], "alpha": 0.05},
        "Regression significance",
    ),
    StatisticalReleaseCase(
        "power_analysis",
        "Do we have enough data to detect a difference in revenue by region?",
        "power_analysis",
        {"target": "revenue", "group_by": ["region"], "alpha": 0.05},
        "Observed power",
    ),
    StatisticalReleaseCase(
        "sample_size_estimate",
        "How many rows per group do we need for revenue by region?",
        "sample_size_estimate",
        {"target": "revenue", "group_by": ["region"], "alpha": 0.05, "desired_power": 0.8},
        "Estimated sample size per group",
    ),
]


@pytest.mark.parametrize("case", _STATISTICAL_RELEASE_CASES, ids=[case.case_id for case in _STATISTICAL_RELEASE_CASES])
def test_statistical_release_matrix_direct_plans_return_statistical_test_results(case: StatisticalReleaseCase) -> None:
    engine = Saida()
    dataset = build_statistical_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="statistical",
        rationale=f"Execute {case.method_id} directly for release coverage.",
        step_id=case.method_id,
        tool_family="stats",
        method_id=case.method_id,
        family="statistical_inference",
        parameters=deepcopy(case.parameters),
        description=f"Execute {case.method_id}.",
        expected_result_name=case.method_id,
        expected_result_shape="table",
    )

    result = engine.execute_plan(dataset, plan)
    payload = result.to_response_dict()

    assert payload["status"] == "ok"
    assert payload["result"]["logical_shape"] == "statistical_test"
    assert payload["result"]["semantic_kind"] == "statistical_test"
    assert payload["result"]["dtype"] == "frame"
    assert case.expected_summary_snippet in result.summary

