"""SQL rendering helpers for deterministic relational access plans."""

from __future__ import annotations

from typing import Any

from saida.exceptions import AdapterError
from saida.sources.sql.relational_access import (
    RelationalAccessPlan,
    RelationalFilterSpec,
    RelationalJoinSpec,
    RelationalOrderSpec,
    RelationalProjectionSpec,
)


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

    where_predicates = [
        predicate
        for filter_spec in access_plan.filters
        if (predicate := _render_filter_predicate(source_type, filter_spec)) is not None
    ]
    where_clause = ""
    if where_predicates:
        where_clause = "\nWHERE " + "\n  AND ".join(where_predicates)

    order_clause = ""
    if access_plan.order_by:
        order_clause = "\nORDER BY " + ", ".join(
            _render_order_by(source_type, order_spec) for order_spec in access_plan.order_by
        )

    limit_clause = f"\nLIMIT {int(access_plan.limit)}" if access_plan.limit is not None else ""
    offset_clause = f"\nOFFSET {int(access_plan.offset)}" if access_plan.offset is not None else ""
    join_block = ("\n" + "\n".join(rendered_joins)) if rendered_joins else ""
    return f"SELECT\n    {select_clause}\n{from_clause}{join_block}{where_clause}{order_clause}{limit_clause}{offset_clause}"


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


def _render_filter_predicate(source_type: str, filter_spec: RelationalFilterSpec) -> str | None:
    column_ref = _column_reference(source_type, filter_spec.source_table, filter_spec.source_column)
    predicate = filter_spec.predicate

    if isinstance(predicate, dict):
        operator = predicate.get("op")
        if operator == "gt":
            return f"{column_ref} > {_sql_literal(predicate.get('value'))}"
        if operator == "gte":
            return f"{column_ref} >= {_sql_literal(predicate.get('value'))}"
        if operator == "lt":
            return f"{column_ref} < {_sql_literal(predicate.get('value'))}"
        if operator == "lte":
            return f"{column_ref} <= {_sql_literal(predicate.get('value'))}"
        if operator == "between":
            return (
                f"{column_ref} BETWEEN {_sql_literal(predicate.get('lower_bound'))} "
                f"AND {_sql_literal(predicate.get('upper_bound'))}"
            )
        if operator == "neq":
            return _render_neq_predicate(source_type, column_ref, predicate.get("value"))
        if operator == "year_eq":
            return f"{_date_part_expression(source_type, column_ref, 'year')} = {int(predicate.get('value'))}"
        if operator == "month_eq":
            return f"{_date_part_expression(source_type, column_ref, 'month')} = {int(predicate.get('value'))}"
        if operator == "year_month_eq":
            return f"{_year_month_expression(source_type, column_ref)} = {_sql_literal(predicate.get('value'))}"
        if operator == "day_of_month_eq":
            return f"{_date_part_expression(source_type, column_ref, 'day')} = {int(predicate.get('value'))}"
        if operator == "quarter_eq":
            return f"{_quarter_expression(source_type, column_ref)} = {int(predicate.get('value'))}"
        return None

    if predicate is None:
        return f"{column_ref} IS NULL"
    if isinstance(predicate, str):
        return _render_case_insensitive_equality(source_type, column_ref, predicate)
    return f"{column_ref} = {_sql_literal(predicate)}"


def _render_order_by(source_type: str, order_spec: RelationalOrderSpec) -> str:
    direction = "DESC" if str(order_spec.direction).lower() == "desc" else "ASC"
    column_ref = _column_reference(source_type, order_spec.source_table, order_spec.source_column)
    return f"{column_ref} {direction}"


def _render_neq_predicate(source_type: str, column_ref: str, value: Any) -> str:
    if value is None:
        return f"{column_ref} IS NOT NULL"
    if isinstance(value, str):
        return f"{_lower_text_expression(source_type, column_ref)} <> {_sql_literal(value.lower())}"
    return f"{column_ref} <> {_sql_literal(value)}"


def _render_case_insensitive_equality(source_type: str, column_ref: str, value: str) -> str:
    return f"{_lower_text_expression(source_type, column_ref)} = {_sql_literal(value.lower())}"


def _column_reference(source_type: str, table_name: str, column_name: str) -> str:
    return f"{_quoted_identifier(source_type, table_name)}.{_quoted_identifier(source_type, column_name)}"


def _lower_text_expression(source_type: str, expression: str) -> str:
    if source_type == "mysql":
        return f"LOWER(CAST({expression} AS CHAR))"
    if source_type == "postgresql":
        return f"LOWER(CAST({expression} AS TEXT))"
    return f"LOWER(CAST({expression} AS TEXT))"


def _date_part_expression(source_type: str, expression: str, part: str) -> str:
    if part not in {"year", "month", "day"}:
        raise AdapterError(f"Unsupported date-part expression: {part}")
    if source_type == "sqlite":
        format_token = {"year": "%Y", "month": "%m", "day": "%d"}[part]
        return f"CAST(strftime('{format_token}', {expression}) AS INTEGER)"
    if source_type == "mysql":
        function_name = {"year": "YEAR", "month": "MONTH", "day": "DAYOFMONTH"}[part]
        return f"{function_name}({expression})"
    return f"CAST(EXTRACT({part.upper()} FROM {expression}) AS INTEGER)"


def _quarter_expression(source_type: str, expression: str) -> str:
    if source_type == "sqlite":
        month_expression = _date_part_expression(source_type, expression, "month")
        return f"(CAST((({month_expression} - 1) / 3) AS INTEGER) + 1)"
    if source_type == "mysql":
        return f"QUARTER({expression})"
    return f"CAST(EXTRACT(QUARTER FROM {expression}) AS INTEGER)"


def _year_month_expression(source_type: str, expression: str) -> str:
    if source_type == "sqlite":
        return f"strftime('%Y-%m', {expression})"
    if source_type == "mysql":
        return f"DATE_FORMAT({expression}, '%Y-%m')"
    return f"to_char({expression}, 'YYYY-MM')"


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _quoted_table(source_type: str, table_name: str) -> str:
    return _quoted_identifier(source_type, table_name)


def _quoted_identifier(source_type: str, identifier: str) -> str:
    quote = "`" if source_type == "mysql" else '"'
    escaped = identifier.replace(quote, quote * 2)
    return f"{quote}{escaped}{quote}"
