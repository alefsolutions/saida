"""Core canonicalization, contracts, validation, routing, and result normalization."""

from saida.core.canonicalization import InputCanonicalizer, RequestNormalizer
from saida.core.context import SourceContextParser
from saida.core.contracts import (
    AnalysisPlan,
    AnalysisRequest,
    AnalysisResult,
    ColumnProfile,
    Dataset,
    DatasetProfile,
    ExecutionTraceEvent,
    ForecastAnalysisResult,
    ForecastResult,
    Metric,
    MLReadinessProfile,
    ModelSpec,
    ModelTrainingResult,
    PlanStep,
    PredictionResult,
    SourceContext,
    TableArtifact,
    TrainResult,
)
from saida.core.discovery import DatasetProfiler, SchemaDiscoveryService
from saida.core.planning import AnalysisPlanner, PlanBuilder
from saida.core.result_canonicalization import ResultBuilder, ResultCanonicalizer
from saida.core.routing import BackendRouter
from saida.core.validation import PlanValidator

__all__ = [
    "AnalysisPlan",
    "AnalysisPlanner",
    "AnalysisRequest",
    "AnalysisResult",
    "BackendRouter",
    "ColumnProfile",
    "Dataset",
    "DatasetProfiler",
    "DatasetProfile",
    "ExecutionTraceEvent",
    "ForecastAnalysisResult",
    "ForecastResult",
    "InputCanonicalizer",
    "Metric",
    "MLReadinessProfile",
    "ModelSpec",
    "ModelTrainingResult",
    "PlanBuilder",
    "PlanStep",
    "PlanValidator",
    "PredictionResult",
    "RequestNormalizer",
    "ResultBuilder",
    "ResultCanonicalizer",
    "SchemaDiscoveryService",
    "SourceContext",
    "SourceContextParser",
    "TableArtifact",
    "TrainResult",
]
