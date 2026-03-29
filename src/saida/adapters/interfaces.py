"""Formal compute interfaces for SAIDA execution backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from saida.core.artifacts import RuntimeArtifact
from saida.core.contracts import Dataset, DatasetProfile, Metric, TableArtifact
from saida.exceptions import PlanningError


@dataclass(slots=True)
class ComputeRequest:
    """Canonical compute request passed to a backend adapter."""

    method_id: str
    dataset: Dataset | None = None
    profile: DatasetProfile | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    resolved_inputs: dict[str, RuntimeArtifact] = field(default_factory=dict)
    declared_output_refs: list[str] = field(default_factory=list)
    artifact_store: object | None = None

    def has_resolved_input(self, input_id: str) -> bool:
        """Return whether a resolved runtime artifact is available for the given input id."""
        return input_id in self.resolved_inputs

    def get_resolved_input(self, input_id: str) -> RuntimeArtifact:
        """Return one resolved runtime artifact or raise a planning error."""
        artifact = self.resolved_inputs.get(input_id)
        if artifact is None:
            raise PlanningError(f"Compute request does not contain resolved input {input_id!r}.")
        return artifact

    def get_resolved_value(self, input_id: str) -> Any:
        """Return the raw value for a resolved runtime artifact."""
        return self.get_resolved_input(input_id).value

    def primary_output_ref(self) -> str | None:
        """Return the primary declared output ref for this request when available."""
        return self.declared_output_refs[0] if self.declared_output_refs else None


@dataclass(slots=True)
class ComputeResponse:
    """Canonical compute response returned by a backend adapter."""

    metrics: list[Metric] = field(default_factory=list)
    tables: list[TableArtifact] = field(default_factory=list)
    produced_artifacts: list[RuntimeArtifact] = field(default_factory=list)


class ComputeInterface(ABC):
    """Formal interface implemented by compute backends."""

    @property
    @abstractmethod
    def tool_family(self) -> str:
        """Return the canonical tool family for this adapter."""

    @abstractmethod
    def supported_methods(self) -> tuple[str, ...]:
        """Return the method ids supported by this compute adapter."""

    def supports_method(self, method_id: str) -> bool:
        """Return whether the adapter supports the requested method."""
        return method_id in set(self.supported_methods())

    @abstractmethod
    def execute(self, request: ComputeRequest) -> ComputeResponse:
        """Execute one canonical compute request."""
