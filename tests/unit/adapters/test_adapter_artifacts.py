from __future__ import annotations

import pandas as pd

from saida.adapters import ComputeRequest, DuckDBAdapter, StatsModelsAdapter
from saida.core.artifacts import FrameArtifact


def test_duckdb_adapter_accepts_frame_artifact_without_dataset() -> None:
    adapter = DuckDBAdapter()
    frame_artifact = FrameArtifact(
        artifact_id="support_frame",
        value=pd.DataFrame({"team": ["Support", "Platform", "Support"]}),
        role="intermediate",
    )

    response = adapter.execute(
        ComputeRequest(
            method_id="row_count",
            resolved_inputs={"source_frame": frame_artifact},
            parameters={},
        )
    )

    assert response.metrics[0].name == "row_count"
    assert response.metrics[0].value == 3


def test_stats_adapter_accepts_frame_artifact_without_dataset() -> None:
    adapter = StatsModelsAdapter()
    frame_artifact = FrameArtifact(
        artifact_id="sales_frame",
        value=pd.DataFrame({"revenue": [100.0, 120.0, 90.0]}),
        role="intermediate",
    )

    response = adapter.execute(
        ComputeRequest(
            method_id="numeric_summary",
            resolved_inputs={"source_frame": frame_artifact},
            parameters={},
        )
    )

    assert response.tables[0].name == "numeric_summary"
    assert list(response.tables[0].dataframe["column"]) == ["revenue"]

