"""Core canonicalization, contracts, validation, routing, and result normalization."""

from saida.core.capability_registry import (
    CapabilityEdge,
    CapabilityNode,
    CapabilityRegistry,
    build_default_capability_registry,
    get_capability_registry,
)
from saida.core.canonicalization import InputCanonicalizer, RequestNormalizer
from saida.core.capability_contract import get_capability_contract
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
from saida.core.prompt_family_catalog import (
    PromptFamilyCatalog,
    PromptFamilySpec,
    build_default_prompt_family_catalog,
    derive_prompt_family,
    get_prompt_family_catalog,
)
from saida.core.prompt_capability_contract import (
    CapabilityActivation,
    DataFeasibilityCheck,
    PromptCapabilityContract,
    ResolvedParameter,
    ValidationIssue,
    build_prompt_capability_contract,
    derive_contract_status,
)
from saida.core.result_canonicalization import ResultBuilder, ResultCanonicalizer
from saida.core.routing import BackendRouter
from saida.core.validation import PlanValidator

__all__ = [
    "AnalysisPlan",
    "AnalysisPlanner",
    "AnalysisRequest",
    "AnalysisResult",
    "BackendRouter",
    "build_default_capability_registry",
    "build_default_prompt_family_catalog",
    "build_prompt_capability_contract",
    "CapabilityActivation",
    "CapabilityEdge",
    "CapabilityNode",
    "CapabilityRegistry",
    "ColumnProfile",
    "DataFeasibilityCheck",
    "Dataset",
    "DatasetProfiler",
    "DatasetProfile",
    "derive_contract_status",
    "ExecutionTraceEvent",
    "ForecastAnalysisResult",
    "ForecastResult",
    "get_capability_contract",
    "get_capability_registry",
    "get_prompt_family_catalog",
    "InputCanonicalizer",
    "Metric",
    "MLReadinessProfile",
    "ModelSpec",
    "ModelTrainingResult",
    "PlanBuilder",
    "PlanStep",
    "PlanValidator",
    "PredictionResult",
    "PromptCapabilityContract",
    "PromptFamilyCatalog",
    "PromptFamilySpec",
    "RequestNormalizer",
    "ResolvedParameter",
    "ResultBuilder",
    "ResultCanonicalizer",
    "SchemaDiscoveryService",
    "SourceContext",
    "SourceContextParser",
    "TableArtifact",
    "TrainResult",
    "ValidationIssue",
    "derive_prompt_family",
]
