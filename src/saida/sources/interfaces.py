"""Formal source interfaces for SAIDA data ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from saida.core.contracts import Dataset, SourceContext


class SourceInterface(ABC):
    """Canonical interface for source adapters that load datasets into SAIDA."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the canonical source type identifier."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the canonical dataset name that the source will emit."""

    @abstractmethod
    def describe_source(self) -> dict[str, Any]:
        """Return source metadata before loading the dataset."""

    def load_context(self) -> SourceContext | None:
        """Return optional source context if available."""
        return None

    @abstractmethod
    def load(self) -> Dataset:
        """Load the source into SAIDA's canonical dataset contract."""


class SQLSourceInterface(SourceInterface):
    """Specialized interface for SQL-backed query sources."""

    @property
    @abstractmethod
    def query(self) -> str:
        """Return the SQL query associated with this source."""
