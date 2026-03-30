from __future__ import annotations

import pandas as pd

from saida.adapters import ComputeRequest, MetadataComputeAdapter
from saida.core.artifacts import artifact_from_value
from saida.sources import DatasetProfiler
from tests.helpers.factories import build_support_dataset


def test_phase19_metadata_adapter_profiles_resolved_frame_artifact() -> None:
    adapter = MetadataComputeAdapter()
    narrowed_frame = pd.DataFrame({"ticket_id": ["T1", "T2"], "priority": ["Low", "High"]})

    response = adapter.execute(
        ComputeRequest(
            method_id="column_inventory",
            resolved_inputs={"prepared_frame": artifact_from_value("narrowed_frame", narrowed_frame)},
            declared_output_refs=["narrowed_columns"],
        )
    )

    assert response.tables[0].name == "column_inventory"
    assert response.tables[0].dataframe["column_name"].tolist() == ["ticket_id", "priority"]
    assert response.produced_artifacts[0].artifact_id == "narrowed_columns"
    assert response.produced_artifacts[0].kind == "frame"


def test_phase19_metadata_adapter_prefers_resolved_frame_over_root_profile() -> None:
    adapter = MetadataComputeAdapter()
    dataset = build_support_dataset()
    profile = DatasetProfiler().profile(dataset)
    narrowed_frame = pd.DataFrame({"ticket_id": ["T1", "T2"], "priority": ["Low", "High"]})

    response = adapter.execute(
        ComputeRequest(
            method_id="column_count",
            profile=profile,
            resolved_inputs={"prepared_frame": artifact_from_value("narrowed_frame", narrowed_frame)},
            declared_output_refs=["narrowed_count"],
        )
    )

    assert int(response.tables[0].dataframe.iloc[0]["column_count"]) == 2
    assert response.produced_artifacts[0].artifact_id == "narrowed_count"
    assert response.produced_artifacts[0].kind == "scalar"
    assert response.produced_artifacts[0].value == 2


def test_phase19_metadata_adapter_emits_verification_artifact_for_column_presence() -> None:
    adapter = MetadataComputeAdapter()
    narrowed_frame = pd.DataFrame({"priority": ["Low", "High"]})

    response = adapter.execute(
        ComputeRequest(
            method_id="column_presence_check",
            resolved_inputs={"prepared_frame": artifact_from_value("narrowed_frame", narrowed_frame)},
            parameters={"requested_column": "priority"},
            declared_output_refs=["priority_exists"],
        )
    )

    assert response.tables[0].name == "column_presence_check"
    assert response.produced_artifacts[0].artifact_id == "priority_exists"
    assert response.produced_artifacts[0].kind == "verification"
    assert response.produced_artifacts[0].value["exists"] is True

