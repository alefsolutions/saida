"""Typed execution artifacts for DAG-oriented SAIDA workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

SEMANTIC_TABLE_NAME_KINDS = {
    "group_breakdown": "grouped_table",
    "grouped_tabular_query": "grouped_table",
    "count_rows_by_group": "grouped_table",
    "group_row_counts": "grouped_table",
    "ranked_breakdown": "ranked_table",
    "ranked_rows": "ranked_table",
    "time_bucket_counts": "time_series",
    "time_bucket_breakdown": "time_series",
    "time_trend": "time_series",
    "time_coverage": "time_series",
    "period_comparison": "time_series",
    "grouped_period_comparison": "time_series",
    "top_movers": "time_series",
    "contribution_breakdown": "time_series",
    "t_test": "statistical_test",
    "chi_square_test": "statistical_test",
    "anova_test": "statistical_test",
    "mann_whitney_test": "statistical_test",
    "confidence_interval": "statistical_test",
    "regression_significance": "statistical_test",
    "significance_test": "statistical_test",
    "power_analysis": "statistical_test",
    "sample_size_estimate": "statistical_test",
}


def infer_semantic_kind(
    *,
    kind: str,
    logical_shape: str | None = None,
    metadata: dict[str, Any] | None = None,
    value: Any | None = None,
) -> str | None:
    """Infer a richer semantic artifact kind from shape, metadata, and payload."""

    payload_metadata = dict(metadata or {})
    explicit_semantic = payload_metadata.get("semantic_kind")
    if isinstance(explicit_semantic, str) and explicit_semantic.strip():
        return explicit_semantic

    if logical_shape == "statistical_test":
        return "statistical_test"
    if logical_shape == "verification":
        return "verification_result"
    if logical_shape in {"timeseries", "time_series"}:
        return "time_series"

    table_name = payload_metadata.get("table_name")
    if isinstance(table_name, str) and table_name in SEMANTIC_TABLE_NAME_KINDS:
        return SEMANTIC_TABLE_NAME_KINDS[table_name]

    if kind == "verification":
        return "verification_result"

    if kind == "series":
        return "prediction_series" if payload_metadata.get("prediction_series") else "series"

    if kind == "frame":
        if isinstance(value, pd.DataFrame):
            if "rank" in value.columns or isinstance(payload_metadata.get("rank_column"), str):
                return "ranked_table"
            if payload_metadata.get("group_by"):
                return "grouped_table"
            if payload_metadata.get("bucket") or payload_metadata.get("bucket_column") or payload_metadata.get("time_column"):
                return "time_series"
            if payload_metadata.get("feature_matrix"):
                return "feature_matrix"
        return "table"

    if kind == "scalar":
        return "scalar"

    return None


@dataclass(slots=True)
class RuntimeArtifact:
    """Base runtime artifact carrying typed execution payloads."""

    artifact_id: str
    kind: str
    value: Any
    logical_shape: str | None = None
    physical_shape: str | None = None
    semantic_kind: str | None = None
    role: str = "intermediate"
    producer_step_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_execution_artifact_payload(self) -> dict[str, Any]:
        """Return a compact execution-artifact style payload."""
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "logical_shape": self.logical_shape,
            "physical_shape": self.physical_shape,
            "semantic_kind": self.semantic_kind,
            "role": self.role,
            "producer_step_id": self.producer_step_id,
            "metadata": dict(self.metadata),
            "value": self.serialize_value(),
        }

    def serialize_value(self) -> Any:
        """Serialize the runtime value to a JSON-friendly structure."""
        return self.value


@dataclass(slots=True)
class FrameArtifact(RuntimeArtifact):
    """Tabular artifact backed by a pandas DataFrame."""

    value: pd.DataFrame
    kind: str = field(default="frame", init=False)
    physical_shape: str | None = "recordset"

    def __post_init__(self) -> None:
        self.logical_shape = self.logical_shape or "table"
        self.semantic_kind = self.semantic_kind or infer_semantic_kind(
            kind=self.kind,
            logical_shape=self.logical_shape,
            metadata=self.metadata,
            value=self.value,
        )

    def schema(self) -> list[dict[str, str]]:
        return [{"name": column_name, "dtype": str(dtype)} for column_name, dtype in self.value.dtypes.items()]

    def serialize_value(self) -> list[dict[str, Any]]:
        return self.value.to_dict(orient="records")

    def dimensions(self) -> tuple[int, int]:
        return int(len(self.value)), int(len(self.value.columns))


@dataclass(slots=True)
class GroupedTableArtifact(FrameArtifact):
    """Frame artifact semantically representing grouped tabular output."""

    semantic_kind: str | None = field(default="grouped_table")


@dataclass(slots=True)
class RankedTableArtifact(FrameArtifact):
    """Frame artifact semantically representing ranked tabular output."""

    semantic_kind: str | None = field(default="ranked_table")


@dataclass(slots=True)
class TimeSeriesArtifact(FrameArtifact):
    """Frame artifact semantically representing time-ordered output."""

    semantic_kind: str | None = field(default="time_series")


@dataclass(slots=True)
class StatisticalTestArtifact(FrameArtifact):
    """Frame artifact semantically representing a statistical test result."""

    semantic_kind: str | None = field(default="statistical_test")


@dataclass(slots=True)
class FeatureMatrixArtifact(FrameArtifact):
    """Frame artifact semantically representing a feature matrix."""

    semantic_kind: str | None = field(default="feature_matrix")


@dataclass(slots=True)
class SeriesArtifact(RuntimeArtifact):
    """Vector artifact backed by a pandas Series."""

    value: pd.Series
    kind: str = field(default="series", init=False)
    physical_shape: str | None = "vector"

    def __post_init__(self) -> None:
        self.logical_shape = self.logical_shape or "series"
        self.semantic_kind = self.semantic_kind or infer_semantic_kind(
            kind=self.kind,
            logical_shape=self.logical_shape,
            metadata=self.metadata,
            value=self.value,
        )

    def dtype(self) -> str:
        return str(self.value.dtype)

    def serialize_value(self) -> list[Any]:
        return self.value.tolist()

    def dimensions(self) -> tuple[int]:
        return (int(len(self.value)),)


@dataclass(slots=True)
class PredictionSeriesArtifact(SeriesArtifact):
    """Series artifact semantically representing model predictions."""

    semantic_kind: str | None = field(default="prediction_series")


@dataclass(slots=True)
class ScalarArtifact(RuntimeArtifact):
    """Scalar artifact for reduced values such as counts and aggregates."""

    kind: str = field(default="scalar", init=False)
    physical_shape: str | None = "scalar"

    def __post_init__(self) -> None:
        self.logical_shape = self.logical_shape or "scalar"
        self.semantic_kind = self.semantic_kind or infer_semantic_kind(
            kind=self.kind,
            logical_shape=self.logical_shape,
            metadata=self.metadata,
            value=self.value,
        )

    def dtype(self) -> str:
        return type(self.value).__name__


@dataclass(slots=True)
class VerificationArtifact(RuntimeArtifact):
    """Structured verification artifact for yes or no style outputs."""

    value: dict[str, Any]
    kind: str = field(default="verification", init=False)
    logical_shape: str | None = "verification"
    physical_shape: str | None = "object"
    semantic_kind: str | None = "verification_result"

    def passed(self) -> bool | None:
        exists = self.value.get("exists")
        return bool(exists) if isinstance(exists, bool) else None


def artifact_from_value(
    artifact_id: str,
    value: Any,
    *,
    role: str = "intermediate",
    producer_step_id: str | None = None,
    logical_shape: str | None = None,
    physical_shape: str | None = None,
    semantic_kind: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeArtifact:
    """Create the appropriate runtime artifact for a concrete value."""

    payload_metadata = dict(metadata or {})
    resolved_semantic_kind = semantic_kind or infer_semantic_kind(
        kind="frame" if isinstance(value, pd.DataFrame) else "series" if isinstance(value, pd.Series) else "verification" if isinstance(value, dict) else "scalar",
        logical_shape=logical_shape,
        metadata=payload_metadata,
        value=value,
    )
    if resolved_semantic_kind is not None:
        payload_metadata.setdefault("semantic_kind", resolved_semantic_kind)

    if isinstance(value, pd.DataFrame):
        frame_class: type[FrameArtifact] = FrameArtifact
        if resolved_semantic_kind == "grouped_table":
            frame_class = GroupedTableArtifact
        elif resolved_semantic_kind == "ranked_table":
            frame_class = RankedTableArtifact
        elif resolved_semantic_kind == "time_series":
            frame_class = TimeSeriesArtifact
        elif resolved_semantic_kind == "statistical_test":
            frame_class = StatisticalTestArtifact
        elif resolved_semantic_kind == "feature_matrix":
            frame_class = FeatureMatrixArtifact
        return frame_class(
            artifact_id=artifact_id,
            value=value.copy(),
            logical_shape=logical_shape,
            physical_shape=physical_shape or "recordset",
            semantic_kind=resolved_semantic_kind,
            role=role,
            producer_step_id=producer_step_id,
            metadata=payload_metadata,
        )
    if isinstance(value, pd.Series):
        series_class: type[SeriesArtifact] = PredictionSeriesArtifact if resolved_semantic_kind == "prediction_series" else SeriesArtifact
        return series_class(
            artifact_id=artifact_id,
            value=value.copy(),
            logical_shape=logical_shape,
            physical_shape=physical_shape or "vector",
            semantic_kind=resolved_semantic_kind,
            role=role,
            producer_step_id=producer_step_id,
            metadata=payload_metadata,
        )
    if isinstance(value, dict) and any(key in value for key in ("exists", "matching_row_count", "matches_expectation")):
        return VerificationArtifact(
            artifact_id=artifact_id,
            value=dict(value),
            role=role,
            producer_step_id=producer_step_id,
            metadata=payload_metadata,
        )
    return ScalarArtifact(
        artifact_id=artifact_id,
        value=value,
        logical_shape=logical_shape,
        physical_shape=physical_shape or "scalar",
        semantic_kind=resolved_semantic_kind,
        role=role,
        producer_step_id=producer_step_id,
        metadata=payload_metadata,
    )
