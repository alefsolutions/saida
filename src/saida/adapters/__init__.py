"""Backend adapters."""

from saida.adapters.duckdb_adapter import DuckDBAdapter, DuckDBComputeEngine
from saida.adapters.interfaces import ComputeInterface, ComputeRequest, ComputeResponse
from saida.adapters.metadata_adapter import MetadataComputeAdapter
from saida.adapters.ml_adapter import BaselineMlEngine, MlAdapter, DEFERRED_ML_MESSAGE
from saida.adapters.statsmodels_adapter import StatsComputeEngine, StatsModelsAdapter

__all__ = [
    "BaselineMlEngine",
    "ComputeInterface",
    "ComputeRequest",
    "ComputeResponse",
    "DEFERRED_ML_MESSAGE",
    "DuckDBAdapter",
    "DuckDBComputeEngine",
    "MetadataComputeAdapter",
    "MlAdapter",
    "StatsComputeEngine",
    "StatsModelsAdapter",
]
