"""SQL rendering helpers for deterministic relational access plans."""

from __future__ import annotations

from saida.exceptions import AdapterError
from saida.sources.relational_access import RelationalAccessPlan, RelationalJoinSpec, RelationalProjectionSpec


def render_relational_access_query(source_type: str, access_plan: RelationalAccessPlan) -> str:
    """Render a deterministic SQL query from a relational access plan."""
    if not access_plan.projections:
        raise AdapterError("Relational access plans must contain at least one projection to render SQL.")

    select_clause = ",\n    ".join(
        _render_projection(source_type, projection) for projection in access_plan.projections
    )
    from_clause = f"FROM {_quoted_table(source_type, access_plan.base_table)}"

    included_tables = {access_plan.base_table}
    rendered_joins: list[str] = []
    pending_joins = list(access_plan.joins)

    while pending_joins:
        progressed = False
        remaining: list[RelationalJoinSpec] = []
        for join_spec in pending_joins:
            if join_spec.left_table in included_tables and join_spec.right_table not in included_tables:
                rendered_joins.append(_render_join(source_type, join_spec, join_table=join_spec.right_table))
                included_tables.add(join_spec.right_table)
                progressed = True
            elif join_spec.right_table in included_tables and join_spec.left_table not in included_tables:
                rendered_joins.append(_render_join(source_type, join_spec, join_table=join_spec.left_table))
                included_tables.add(join_spec.left_table)
                progressed = True
            elif join_spec.left_table in included_tables and join_spec.right_table in included_tables:
                progressed = True
            else:
                remaining.append(join_spec)
        if not progressed:
            unresolved = ", ".join(join_spec.relationship_name for join_spec in pending_joins)
            raise AdapterError(f"Unable to render relational access query because joins could not be chained: {unresolved}")
        pending_joins = remaining

    join_block = ("\n" + "\n".join(rendered_joins)) if rendered_joins else ""
    return f"SELECT\n    {select_clause}\n{from_clause}{join_block}"


def _render_projection(source_type: str, projection: RelationalProjectionSpec) -> str:
    return (
        f"{_quoted_identifier(source_type, projection.source_table)}."
        f"{_quoted_identifier(source_type, projection.source_column)} AS "
        f"{_quoted_identifier(source_type, projection.output_name)}"
    )


def _render_join(source_type: str, join_spec: RelationalJoinSpec, *, join_table: str) -> str:
    predicates = " AND ".join(
        (
            f"{_quoted_identifier(source_type, join_spec.left_table)}."
            f"{_quoted_identifier(source_type, left_column)} = "
            f"{_quoted_identifier(source_type, join_spec.right_table)}."
            f"{_quoted_identifier(source_type, right_column)}"
        )
        for left_column, right_column in zip(join_spec.left_columns, join_spec.right_columns, strict=True)
    )
    return f"{join_spec.join_type.upper()} JOIN {_quoted_table(source_type, join_table)} ON {predicates}"


def _quoted_table(source_type: str, table_name: str) -> str:
    return _quoted_identifier(source_type, table_name)


def _quoted_identifier(source_type: str, identifier: str) -> str:
    quote = "`" if source_type == "mysql" else '"'
    escaped = identifier.replace(quote, quote * 2)
    return f"{quote}{escaped}{quote}"
