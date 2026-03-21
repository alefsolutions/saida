"""Core dataclass schemas for SAIDA."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(slots=True)
class SourceContext:
    raw_markdown: str
    source_summary: str | None = None
    table_descriptions: dict[str, str] = field(default_factory=dict)
    field_descriptions: dict[str, str] = field(default_factory=dict)
    metric_definitions: dict[str, str] = field(default_factory=dict)
    business_rules: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    trusted_date_fields: list[str] = field(default_factory=list)
    preferred_identifiers: list[str] = field(default_factory=list)
    freshness_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Dataset:
    name: str
    source_type: str
    data: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)
    context: SourceContext | None = None


@dataclass(slots=True)
class ColumnProfile:
    name: str
    inferred_type: str
    nullable: bool
    null_ratio: float
    unique_count: int | None
    distinct_ratio: float | None
    sample_values: list[Any] = field(default_factory=list)
    is_identifier_candidate: bool = False
    is_dimension_candidate: bool = False
    is_measure_candidate: bool = False
    is_time_candidate: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MLReadinessProfile:
    candidate_targets: list[str] = field(default_factory=list)
    candidate_features: list[str] = field(default_factory=list)
    forecasting_ready: bool = False
    regression_ready: bool = False
    classification_ready: bool = False
    detected_time_column: str | None = None
    readiness_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DatasetProfile:
    dataset_name: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile] = field(default_factory=list)
    measure_columns: list[str] = field(default_factory=list)
    dimension_columns: list[str] = field(default_factory=list)
    time_columns: list[str] = field(default_factory=list)
    identifier_columns: list[str] = field(default_factory=list)
    duplicate_row_count: int | None = None
    warnings: list[str] = field(default_factory=list)
    ml_readiness: MLReadinessProfile | None = None


@dataclass(slots=True)
class AnalysisRequest:
    question: str
    intent_name: str | None = None
    task_type_hint: str | None = None
    target: str | None = None
    aggregation: str | None = None
    horizon: int | None = None
    filters: dict[str, Any] | None = None
    group_by: list[str] | None = None
    time_reference: dict[str, Any] | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlanStep:
    step_id: str
    tool_family: str
    action: str
    parameters: dict[str, Any]
    description: str


@dataclass(slots=True)
class AnalysisPlan:
    task_type: str
    rationale: str
    steps: list[PlanStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Metric:
    name: str
    value: Any
    unit: str | None = None
    description: str | None = None


@dataclass(slots=True)
class TableArtifact:
    name: str
    description: str | None
    dataframe: pd.DataFrame


@dataclass(slots=True)
class ExecutionTraceEvent:
    stage: str
    message: str
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class ModelSpec:
    problem_type: str
    target: str
    feature_columns: list[str] | None = None
    model_name: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelTrainingResult:
    model_name: str
    problem_type: str
    target: str
    feature_columns: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    artifact_path: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PredictionResult:
    model_name: str
    problem_type: str
    predictions: list[Any] = field(default_factory=list)
    confidence: list[float] | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ForecastResult:
    target: str
    horizon: int
    forecast_values: list[float] = field(default_factory=list)
    lower_bounds: list[float] | None = None
    upper_bounds: list[float] | None = None
    metrics: dict[str, float] | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AnalysisResult:
    summary: str
    deterministic_summary: str | None
    llm_summary: str | None
    summary_source: str
    metrics: list[Metric]
    tables: list[TableArtifact]
    warnings: list[str]
    plan: AnalysisPlan
    trace: list[ExecutionTraceEvent]
    artifacts: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)

    def to_response_dict(self) -> dict[str, Any]:
        """Return a JSON-safe analytical response contract."""
        return deepcopy(self.response)


@dataclass(slots=True)
class TrainResult:
    summary: str
    training: ModelTrainingResult
    trace: list[ExecutionTraceEvent] = field(default_factory=list)


@dataclass(slots=True)
class ForecastAnalysisResult:
    summary: str
    forecast: ForecastResult
    trace: list[ExecutionTraceEvent] = field(default_factory=list)
