"""Formal compute interfaces for SAIDA execution backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from saida.core.contracts import Dataset, DatasetProfile, Metric, TableArtifact


@dataclass(slots=True)
class ComputeRequest:
    """Canonical compute request passed to a backend adapter."""

    method_id: str
    dataset: Dataset | None = None
    profile: DatasetProfile | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ComputeResponse:
    """Canonical compute response returned by a backend adapter."""

    metrics: list[Metric] = field(default_factory=list)
    tables: list[TableArtifact] = field(default_factory=list)


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
