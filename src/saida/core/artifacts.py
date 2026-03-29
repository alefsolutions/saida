"""Typed execution artifacts for DAG-oriented SAIDA workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(slots=True)
class RuntimeArtifact:
    """Base runtime artifact carrying typed execution payloads."""

    artifact_id: str
    kind: str
    value: Any
    logical_shape: str | None = None
    physical_shape: str | None = None
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

    def schema(self) -> list[dict[str, str]]:
        return [{"name": column_name, "dtype": str(dtype)} for column_name, dtype in self.value.dtypes.items()]

    def serialize_value(self) -> list[dict[str, Any]]:
        return self.value.to_dict(orient="records")

    def dimensions(self) -> tuple[int, int]:
        return int(len(self.value)), int(len(self.value.columns))


@dataclass(slots=True)
class SeriesArtifact(RuntimeArtifact):
    """Vector artifact backed by a pandas Series."""

    value: pd.Series
    kind: str = field(default="series", init=False)
    physical_shape: str | None = "vector"

    def __post_init__(self) -> None:
        self.logical_shape = self.logical_shape or "series"

    def dtype(self) -> str:
        return str(self.value.dtype)

    def serialize_value(self) -> list[Any]:
        return self.value.tolist()

    def dimensions(self) -> tuple[int]:
        return (int(len(self.value)),)


@dataclass(slots=True)
class ScalarArtifact(RuntimeArtifact):
    """Scalar artifact for reduced values such as counts and aggregates."""

    kind: str = field(default="scalar", init=False)
    physical_shape: str | None = "scalar"

    def __post_init__(self) -> None:
        self.logical_shape = self.logical_shape or "scalar"

    def dtype(self) -> str:
        return type(self.value).__name__


@dataclass(slots=True)
class VerificationArtifact(RuntimeArtifact):
    """Structured verification artifact for yes or no style outputs."""

    value: dict[str, Any]
    kind: str = field(default="verification", init=False)
    logical_shape: str | None = "verification"
    physical_shape: str | None = "object"

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
    metadata: dict[str, Any] | None = None,
) -> RuntimeArtifact:
    """Create the appropriate runtime artifact for a concrete value."""

    payload_metadata = dict(metadata or {})
    if isinstance(value, pd.DataFrame):
        return FrameArtifact(
            artifact_id=artifact_id,
            value=value.copy(),
            logical_shape=logical_shape,
            physical_shape=physical_shape or "recordset",
            role=role,
            producer_step_id=producer_step_id,
            metadata=payload_metadata,
        )
    if isinstance(value, pd.Series):
        return SeriesArtifact(
            artifact_id=artifact_id,
            value=value.copy(),
            logical_shape=logical_shape,
            physical_shape=physical_shape or "vector",
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
        role=role,
        producer_step_id=producer_step_id,
        metadata=payload_metadata,
    )
