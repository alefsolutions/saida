from __future__ import annotations

import pandas as pd

from saida.adapters import ComputeRequest, StatsModelsAdapter
from saida.core.artifacts import artifact_from_value
from tests.helpers.factories import build_sales_dataset


def test_phase19_stats_adapter_prefers_resolved_frame_artifact_over_root_dataset() -> None:
    adapter = StatsModelsAdapter()
    dataset = build_sales_dataset()
    west_only = pd.DataFrame({"revenue": [100.0, 90.0, 110.0]})

    response = adapter.execute(
        ComputeRequest(
            method_id="numeric_summary",
            dataset=dataset,
            resolved_inputs={"prepared_frame": artifact_from_value("west_only", west_only)},
            declared_output_refs=["west_numeric_summary"],
        )
    )

    assert response.tables[0].name == "numeric_summary"
    assert float(response.tables[0].dataframe.iloc[0]["mean"]) == 100.0
    assert response.produced_artifacts[0].artifact_id == "west_numeric_summary"
    assert response.produced_artifacts[0].kind == "frame"


def test_phase19_stats_adapter_emits_native_artifact_for_distribution_summary() -> None:
    adapter = StatsModelsAdapter()
    frame = pd.DataFrame({"revenue": [100.0, 120.0, 90.0]})

    response = adapter.execute(
        ComputeRequest(
            method_id="distribution_summary",
            resolved_inputs={"prepared_frame": artifact_from_value("sales_frame", frame)},
            parameters={"target": "revenue"},
            declared_output_refs=["distribution_result"],
        )
    )

    assert response.tables[0].name == "distribution_summary"
    assert response.produced_artifacts[0].artifact_id == "distribution_result"
    assert response.produced_artifacts[0].kind == "frame"

