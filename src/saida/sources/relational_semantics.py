"""Deterministic semantic heuristics for relational source planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from saida.sources.relational_schema import RelationalRelationshipModel, RelationalSchemaModel, RelationalTableModel


@dataclass(slots=True)
class RelationalTableSemantics:
    """Semantic role and heuristic signals for one relational table."""

    table_name: str
    role: str
    outgoing_relationship_count: int
    incoming_relationship_count: int
    foreign_key_column_count: int
    numeric_like_column_count: int
    non_key_column_count: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_relational_table_semantics(schema: RelationalSchemaModel) -> dict[str, RelationalTableSemantics]:
    """Infer deterministic fact/dimension/bridge/view roles for one relational schema."""
    semantics: dict[str, RelationalTableSemantics] = {}

    outgoing_lookup: dict[str, list[RelationalRelationshipModel]] = {}
    incoming_lookup: dict[str, list[RelationalRelationshipModel]] = {}
    for relationship in schema.relationships:
        outgoing_lookup.setdefault(relationship.left_table, []).append(relationship)
        incoming_lookup.setdefault(relationship.right_table, []).append(relationship)

    for table in schema.tables:
        outgoing = outgoing_lookup.get(table.name, [])
        incoming = incoming_lookup.get(table.name, [])
        foreign_key_columns = {
            column_name
            for relationship in outgoing
            for column_name in relationship.left_columns
        }
        numeric_like_columns = sum(1 for column in table.columns if _is_numeric_like(column.data_type))
        non_key_columns = [
            column.name
            for column in table.columns
            if column.name not in set(table.primary_key) | foreign_key_columns
        ]
        reasons: list[str] = []

        if table.is_view:
            role = "view"
            reasons.append("view relation discovered through source introspection")
        elif len(foreign_key_columns) >= 2 and numeric_like_columns <= 1 and len(non_key_columns) <= 2:
            role = "bridge"
            reasons.append("multiple foreign-key columns with very low standalone attribute count")
        elif numeric_like_columns >= 1 and outgoing:
            role = "fact"
            reasons.append("numeric measures combined with outgoing foreign-key relationships")
        elif incoming or not numeric_like_columns:
            role = "dimension"
            if incoming:
                reasons.append("referenced by other tables as a lookup or parent relation")
            if not numeric_like_columns:
                reasons.append("few or no numeric measures")
        else:
            role = "unknown"
            reasons.append("did not strongly match fact, dimension, or bridge heuristics")

        semantics[table.name] = RelationalTableSemantics(
            table_name=table.name,
            role=role,
            outgoing_relationship_count=len(outgoing),
            incoming_relationship_count=len(incoming),
            foreign_key_column_count=len(foreign_key_columns),
            numeric_like_column_count=numeric_like_columns,
            non_key_column_count=len(non_key_columns),
            reasons=reasons,
        )

    return semantics


def _is_numeric_like(data_type: str) -> bool:
    normalized = data_type.lower()
    return any(token in normalized for token in ("int", "numeric", "decimal", "real", "float", "double"))
