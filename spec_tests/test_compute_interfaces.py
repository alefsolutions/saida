from __future__ import annotations

import pytest

from saida.adapters import ComputeInterface, ComputeRequest, DuckDBAdapter, MetadataComputeAdapter, MlAdapter, StatsModelsAdapter
from saida.core import BackendRouter
from saida.sources import DatasetProfiler
from saida.exceptions import ModelTrainingError
from .factories import build_support_dataset


def test_duckdb_adapter_implements_compute_interface_and_executes_row_count() -> None:
    adapter = DuckDBAdapter()
    dataset = build_support_dataset()

    response = adapter.execute(ComputeRequest(method_id="row_count", dataset=dataset, parameters={}))

    assert isinstance(adapter, ComputeInterface)
    assert adapter.tool_family == "duckdb"
    assert adapter.supports_method("row_count") is True
    assert response.metrics[0].name == "row_count"
    assert response.metrics[0].value == len(dataset.data)


def test_metadata_adapter_implements_compute_interface_and_executes_column_count() -> None:
    adapter = MetadataComputeAdapter()
    dataset = build_support_dataset()
    profile = DatasetProfiler().profile(dataset)

    response = adapter.execute(ComputeRequest(method_id="column_count", profile=profile))

    assert isinstance(adapter, ComputeInterface)
    assert adapter.tool_family == "metadata"
    assert adapter.supports_method("column_count") is True
    assert response.tables[0].name == "column_count"
    assert int(response.tables[0].dataframe.iloc[0]["column_count"]) == profile.column_count


def test_statsmodels_adapter_implements_compute_interface_and_executes_numeric_summary() -> None:
    adapter = StatsModelsAdapter()
    dataset = build_support_dataset()

    response = adapter.execute(ComputeRequest(method_id="numeric_summary", dataset=dataset))

    assert isinstance(adapter, ComputeInterface)
    assert adapter.tool_family == "stats"
    assert adapter.supports_method("numeric_summary") is True
    assert response.tables[0].name == "numeric_summary"


def test_backend_router_routes_registered_compute_interfaces() -> None:
    router = BackendRouter(
        duckdb_adapter=DuckDBAdapter(),
        metadata_adapter=MetadataComputeAdapter(),
        stats_adapter=StatsModelsAdapter(),
        ml_adapter=MlAdapter(),
    )

    assert router.route("duckdb").tool_family == "duckdb"
    assert router.route("metadata").tool_family == "metadata"
    assert router.route("stats").tool_family == "stats"
    assert router.route("ml").tool_family == "ml"


def test_ml_adapter_exposes_forecast_compute_placeholder() -> None:
    adapter = MlAdapter()

    with pytest.raises(ModelTrainingError, match="Forecasting"):
        adapter.execute(ComputeRequest(method_id="forecast", parameters={"target": "revenue", "horizon": 3}))
