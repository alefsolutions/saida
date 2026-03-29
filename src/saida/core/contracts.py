"""Core dataclass schemas for SAIDA."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
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
    prompt_family: str | None = None
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
class AnalysisInterpretation:
    question: str
    prompt_family: str | None = None
    intent_name: str | None = None
    task_type_hint: str | None = None
    target: str | None = None
    aggregation: str | None = None
    horizon: int | None = None
    filters: dict[str, Any] | None = None
    group_by: list[str] | None = None
    time_reference: dict[str, Any] | None = None
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_request(cls, request: AnalysisRequest) -> "AnalysisInterpretation":
        return cls(
            question=request.question,
            prompt_family=request.prompt_family,
            intent_name=request.intent_name,
            task_type_hint=request.task_type_hint,
            target=request.target,
            aggregation=request.aggregation,
            horizon=request.horizon,
            filters=deepcopy(request.filters),
            group_by=list(request.group_by or []) if request.group_by is not None else None,
            time_reference=deepcopy(request.time_reference),
            options=deepcopy(request.options),
        )

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "AnalysisInterpretation":
        return cls(
            question=str(snapshot.get("question") or "Execute analysis plan"),
            prompt_family=snapshot.get("prompt_family") if isinstance(snapshot.get("prompt_family"), str) else None,
            intent_name=snapshot.get("intent_name") if isinstance(snapshot.get("intent_name"), str) else None,
            task_type_hint=snapshot.get("task_type_hint") if isinstance(snapshot.get("task_type_hint"), str) else None,
            target=snapshot.get("target") if isinstance(snapshot.get("target"), str) else None,
            aggregation=snapshot.get("aggregation") if isinstance(snapshot.get("aggregation"), str) else None,
            horizon=snapshot.get("horizon") if isinstance(snapshot.get("horizon"), int) else None,
            filters=deepcopy(snapshot.get("filters")) if isinstance(snapshot.get("filters"), dict) else None,
            group_by=list(snapshot.get("group_by")) if isinstance(snapshot.get("group_by"), list) else None,
            time_reference=deepcopy(snapshot.get("time_reference")) if isinstance(snapshot.get("time_reference"), dict) else None,
            options=deepcopy(snapshot.get("options")) if isinstance(snapshot.get("options"), dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlanStep:
    step_id: str
    tool_family: str
    action: str
    parameters: dict[str, Any]
    description: str
    family: str | None = None
    method_id: str | None = None
    depends_on: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    expected_output: dict[str, Any] | None = None
    inputs: list["StepInputRef"] = field(default_factory=list)
    outputs: list["StepOutputSpec"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for the step."""
        return asdict(self)


@dataclass(slots=True)
class StepInputRef:
    input_id: str
    source_type: str
    ref: str
    alias: str | None = None
    required: bool = True
    expected_kind: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for the step input reference."""
        return asdict(self)


@dataclass(slots=True)
class StepOutputSpec:
    output_id: str
    kind: str
    logical_shape: str | None = None
    physical_shape: str | None = None
    is_primary: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for the step output specification."""
        return asdict(self)


@dataclass(slots=True)
class PlanInput:
    input_id: str
    kind: str
    ref: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for the plan input."""
        return asdict(self)


@dataclass(slots=True)
class AnalysisPlan:
    task_type: str
    rationale: str
    steps: list[PlanStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    plan_id: str | None = None
    version: str = "saida.plan.v2"
    dataset_refs: list[str] = field(default_factory=list)
    inputs: list[PlanInput] = field(default_factory=list)
    expected_result_name: str | None = None
    expected_result_shape: str | None = None
    final_output_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for the plan."""
        return asdict(self)


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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionTraceEvent:
    stage: str
    message: str
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class ExecutionArtifact:
    artifact_id: str
    kind: str
    value: Any
    logical_shape: str | None = None
    physical_shape: str | None = None
    producer_step_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for the execution artifact."""
        return asdict(self)


@dataclass(slots=True)
class NodeExecutionResult:
    step_id: str
    status: str
    consumed_inputs: list[str] = field(default_factory=list)
    produced_outputs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for the node execution result."""
        return asdict(self)


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
    node_results: list[NodeExecutionResult] = field(default_factory=list)
    artifact_index: dict[str, ExecutionArtifact] = field(default_factory=dict)
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
