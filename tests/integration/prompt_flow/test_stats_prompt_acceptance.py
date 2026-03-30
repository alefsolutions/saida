from __future__ import annotations

import pandas as pd
import pytest

from saida import PromptAnalysisFrontend
from saida.core.contracts import Dataset


@pytest.mark.parametrize(
    ("question", "expected_method_id", "expected_summary_snippet"),
    [
        ("Run a t-test on revenue by region", "t_test", "Welch t-test for revenue by region"),
        ("Run chi-square between team and segment", "chi_square", "Chi-square test for team and segment"),
        ("Run anova on revenue by team", "anova", "ANOVA for revenue by team"),
        ("Run Mann-Whitney on revenue by region", "mann_whitney", "Mann-Whitney test for revenue by region"),
    ],
)
def test_statistical_prompt_acceptance_for_explicit_test_requests(
    question: str,
    expected_method_id: str,
    expected_summary_snippet: str,
) -> None:
    dataframe = pd.DataFrame(
        {
            "team": ["Support", "Support", "Platform", "Platform", "Support", "Platform"] * 2,
            "segment": ["Retail", "Retail", "Wholesale", "Wholesale", "Retail", "Wholesale"] * 2,
            "region": ["North", "North", "South", "South", "North", "South"] * 2,
            "revenue": [100, 104, 98, 102, 101, 99, 135, 138, 132, 140, 136, 134],
            "cost": [70, 72, 69, 71, 70, 68, 88, 90, 87, 91, 89, 88],
            "units": [10, 11, 10, 12, 11, 10, 14, 15, 14, 15, 16, 14],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, question)

    assert result.response["status"] == "ok"
    assert result.response["execution"]["steps"][0]["method_id"] == expected_method_id
    assert result.response["result"]["logical_shape"] == "statistical_test"
    assert result.response["result"]["semantic_kind"] == "statistical_test"
    assert expected_summary_snippet in result.summary


