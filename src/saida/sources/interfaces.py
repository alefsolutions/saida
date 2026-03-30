"""Formal source interfaces for SAIDA data ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from saida.core.contracts import Dataset, SourceContext
from saida.sources.relational_access import RelationalAccessPlan
from saida.sources.relational_schema import RelationalSchemaModel


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

    @abstractmethod
    def discover_schema(self) -> RelationalSchemaModel:
        """Return the canonical relational schema discovered for this SQL source."""

    @abstractmethod
    def plan_access(
        self,
        *,
        required_columns: list[str],
        preferred_base_table: str | None = None,
    ) -> RelationalAccessPlan:
        """Return a deterministic relational access plan for the requested fields."""

    @abstractmethod
    def render_access_query(self, access_plan: RelationalAccessPlan) -> str:
        """Render one relational access plan into executable SQL."""

    @abstractmethod
    def load_from_access_plan(self, access_plan: RelationalAccessPlan) -> Dataset:
        """Materialize one relational access plan into SAIDA's canonical dataset contract."""
