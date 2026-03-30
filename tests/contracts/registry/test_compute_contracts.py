from __future__ import annotations

import pandas as pd
import pytest

from saida.adapters.interfaces import ComputeRequest, ComputeResponse
from saida.core.artifacts import FrameArtifact, ScalarArtifact
from saida.exceptions import PlanningError


def test_compute_request_supports_resolved_inputs_and_value_helpers() -> None:
    dataset_artifact = FrameArtifact(
        artifact_id="primary_dataset",
        value=pd.DataFrame({"revenue": [100.0, 120.0]}),
        role="input",
    )
    request = ComputeRequest(
        method_id="row_count",
        resolved_inputs={"primary_dataset": dataset_artifact},
    )

    assert request.has_resolved_input("primary_dataset") is True
    assert request.get_resolved_input("primary_dataset").artifact_id == "primary_dataset"
    assert list(request.get_resolved_value("primary_dataset").columns) == ["revenue"]


def test_compute_request_raises_for_missing_resolved_input() -> None:
    request = ComputeRequest(method_id="row_count")

    with pytest.raises(PlanningError, match="resolved input 'missing_input'"):
        request.get_resolved_input("missing_input")


def test_compute_response_supports_runtime_artifact_outputs() -> None:
    response = ComputeResponse(
        produced_artifacts=[
            ScalarArtifact(
                artifact_id="row_count",
                value=7,
                logical_shape="count",
                producer_step_id="row_count",
            )
        ]
    )

    assert response.produced_artifacts[0].artifact_id == "row_count"
    assert response.produced_artifacts[0].kind == "scalar"

