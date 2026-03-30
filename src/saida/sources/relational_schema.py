"""Canonical relational schema models for SQL-backed source adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class RelationalColumnModel:
    """Canonical column metadata discovered from a relational source."""

    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    default: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelationalTableModel:
    """Canonical table metadata discovered from a relational source."""

    name: str
    columns: list[RelationalColumnModel] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelationalRelationshipModel:
    """Canonical relationship metadata between two relational tables."""

    name: str
    left_table: str
    left_columns: list[str]
    right_table: str
    right_columns: list[str]
    relationship_type: str = "many_to_one"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelationalSchemaModel:
    """Canonical relational schema graph for one SQL-backed source."""

    source_type: str
    source_name: str
    tables: list[RelationalTableModel] = field(default_factory=list)
    relationships: list[RelationalRelationshipModel] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

