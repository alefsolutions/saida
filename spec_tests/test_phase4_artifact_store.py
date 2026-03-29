from __future__ import annotations

import pandas as pd
import pytest

from saida.core import Dataset, PlanInput
from saida.core.artifact_store import ArtifactStore
from saida.core.artifacts import FrameArtifact, ScalarArtifact
from saida.exceptions import PlanningError


def build_dataset() -> Dataset:
    return Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame({"team": ["Support", "Platform"], "row_count": [4, 3]}),
    )


def test_artifact_store_registers_plan_inputs_and_runtime_outputs() -> None:
    dataset = build_dataset()
    store = ArtifactStore()

    registered_inputs = store.register_plan_inputs(
        dataset,
        [PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
    )
    grouped = store.register_value(
        "grouped_support",
        dataset.data,
        role="intermediate",
        producer_step_id="group_breakdown",
        logical_shape="table",
    )
    total = store.register_value(
        "support_total",
        7,
        role="final",
        producer_step_id="row_count",
        logical_shape="count",
    )

    assert len(registered_inputs) == 1
    assert isinstance(store.get("primary_dataset"), FrameArtifact)
    assert isinstance(grouped, FrameArtifact)
    assert isinstance(total, ScalarArtifact)
    assert store.get("primary_dataset").role == "input"
    assert store.get("support_total").role == "final"
    assert store.list_ids() == ["primary_dataset", "grouped_support", "support_total"]


def test_artifact_store_rejects_duplicate_artifact_ids_and_unknown_lookups() -> None:
    dataset = build_dataset()
    store = ArtifactStore()

    store.register_plan_inputs(dataset, [PlanInput(input_id="primary_dataset", kind="dataset", ref="support")])

    with pytest.raises(PlanningError, match="already contains artifact id"):
        store.register_value("primary_dataset", dataset.data)

    with pytest.raises(PlanningError, match="does not contain artifact id"):
        store.get("missing_artifact")


def test_artifact_store_rejects_mismatched_or_unsupported_plan_inputs() -> None:
    dataset = build_dataset()

    mismatched_store = ArtifactStore()
    with pytest.raises(PlanningError, match="expected 'support'"):
        mismatched_store.register_plan_inputs(
            dataset,
            [PlanInput(input_id="primary_dataset", kind="dataset", ref="sales")],
        )

    unsupported_store = ArtifactStore()
    with pytest.raises(PlanningError, match="Unsupported plan input kind"):
        unsupported_store.register_plan_inputs(
            dataset,
            [PlanInput(input_id="context_blob", kind="context", ref="support.md")],
        )
