from __future__ import annotations

import pandas as pd

from saida.core.artifacts import (
    FrameArtifact,
    ScalarArtifact,
    SeriesArtifact,
    VerificationArtifact,
    artifact_from_value,
)


def test_frame_artifact_preserves_schema_and_record_serialization() -> None:
    artifact = FrameArtifact(
        artifact_id="grouped_sales",
        value=pd.DataFrame({"region": ["West", "East"], "revenue": [210.0, 420.0]}),
        role="final",
        producer_step_id="group_breakdown",
    )

    assert artifact.kind == "frame"
    assert artifact.logical_shape == "table"
    assert artifact.physical_shape == "recordset"
    assert artifact.schema() == [
        {"name": "region", "dtype": "object"},
        {"name": "revenue", "dtype": "float64"},
    ]
    assert artifact.serialize_value()[0] == {"region": "West", "revenue": 210.0}
    assert artifact.dimensions() == (2, 2)


def test_series_and_scalar_artifacts_expose_small_type_helpers() -> None:
    series_artifact = SeriesArtifact(
        artifact_id="top_regions",
        value=pd.Series(["West", "East"], name="region"),
        producer_step_id="top_regions",
    )
    scalar_artifact = ScalarArtifact(
        artifact_id="row_count",
        value=7,
        logical_shape="count",
        producer_step_id="row_count",
    )

    assert series_artifact.kind == "series"
    assert series_artifact.physical_shape == "vector"
    assert series_artifact.dtype() == "object"
    assert series_artifact.serialize_value() == ["West", "East"]
    assert scalar_artifact.kind == "scalar"
    assert scalar_artifact.dtype() == "int"
    assert scalar_artifact.to_execution_artifact_payload()["logical_shape"] == "count"


def test_verification_artifact_and_factory_select_expected_runtime_types() -> None:
    verification = artifact_from_value(
        "platform_exists",
        {"exists": True, "matching_row_count": 3},
        producer_step_id="row_existence",
    )
    frame = artifact_from_value("support_table", pd.DataFrame({"team": ["Support"]}))
    series = artifact_from_value("team_names", pd.Series(["Support", "Platform"]))
    scalar = artifact_from_value("revenue_sum", 630.0, logical_shape="aggregate")

    assert isinstance(verification, VerificationArtifact)
    assert verification.passed() is True
    assert isinstance(frame, FrameArtifact)
    assert isinstance(series, SeriesArtifact)
    assert isinstance(scalar, ScalarArtifact)
    assert scalar.logical_shape == "aggregate"
