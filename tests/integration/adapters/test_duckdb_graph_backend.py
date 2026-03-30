from __future__ import annotations

from saida.adapters import ComputeRequest, DuckDBAdapter
from saida.core.artifacts import artifact_from_value

from tests.helpers.factories import build_sales_dataset


def test_phase18_duckdb_filter_frame_emits_native_frame_artifact() -> None:
    adapter = DuckDBAdapter()
    dataset = build_sales_dataset()

    response = adapter.execute(
        ComputeRequest(
            method_id="filter_frame",
            dataset=dataset,
            parameters={"filters": {"region": "West"}},
            declared_output_refs=["west_rows"],
        )
    )

    assert response.tables[0].name == "filter_frame"
    assert len(response.produced_artifacts) == 1
    assert response.produced_artifacts[0].artifact_id == "west_rows"
    assert response.produced_artifacts[0].kind == "frame"
    assert response.produced_artifacts[0].serialize_value() == response.tables[0].dataframe.to_dict(orient="records")


def test_phase18_duckdb_row_count_emits_native_scalar_artifact() -> None:
    adapter = DuckDBAdapter()
    dataset = build_sales_dataset()

    response = adapter.execute(
        ComputeRequest(
            method_id="row_count",
            dataset=dataset,
            parameters={"filters": {"region": "East"}},
            declared_output_refs=["east_count"],
        )
    )

    assert response.metrics[0].name == "row_count"
    assert response.metrics[0].value == 3
    assert len(response.produced_artifacts) == 1
    assert response.produced_artifacts[0].artifact_id == "east_count"
    assert response.produced_artifacts[0].kind == "scalar"
    assert response.produced_artifacts[0].value == 3


def test_phase18_duckdb_prefers_resolved_frame_artifact_inputs() -> None:
    adapter = DuckDBAdapter()
    dataset = build_sales_dataset()
    west_rows = dataset.data.loc[dataset.data["region"] == "West", ["posted_at", "revenue"]].reset_index(drop=True)

    response = adapter.execute(
        ComputeRequest(
            method_id="limit_frame",
            parameters={"limit": 1, "sort_by": "posted_at", "sort_direction": "desc"},
            resolved_inputs={"source_frame": artifact_from_value("west_rows", west_rows)},
            declared_output_refs=["latest_west_row"],
        )
    )

    assert response.produced_artifacts[0].artifact_id == "latest_west_row"
    assert response.tables[0].dataframe.to_dict(orient="records") == [{"posted_at": "2026-02-01", "revenue": 110.0}]

