"""Helpers for extracting numeric threshold filters from prompts."""

from __future__ import annotations

import re

from saida.core.contracts import DatasetProfile


def extract_numeric_threshold_filters(
    question: str,
    profile: DatasetProfile,
    target: str | None,
    intent_name: str | None,
    filters: dict[str, object] | None,
    *,
    named_columns: list[str] | None = None,
) -> dict[str, object]:
    """Extract threshold filters for measure columns mentioned in a prompt."""
    if intent_name == "existence_check":
        return {}

    lowered = question.lower()
    measure_columns = set(profile.measure_columns)
    candidate_columns: list[str] = []

    if target in measure_columns:
        candidate_columns.append(target)

    candidate_columns.extend(
        column_name
        for column_name in (named_columns or [])
        if column_name in measure_columns
    )

    resolved_filters: dict[str, object] = {}
    existing_columns = set(filters or {})
    for column_name in dict.fromkeys(candidate_columns):
        if column_name in existing_columns:
            continue
        threshold_filter = extract_column_threshold_filter(lowered, column_name)
        if threshold_filter is not None:
            resolved_filters[column_name] = threshold_filter
    return resolved_filters


def extract_column_threshold_filter(
    lowered_question: str,
    column_name: str,
) -> dict[str, object] | None:
    """Extract a threshold comparison for a specific column mention."""
    escaped_column = re.escape(column_name.lower())
    between_match = re.search(
        rf"\b{escaped_column}\b(?:\s+is)?\s+between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)\b",
        lowered_question,
    )
    if between_match:
        lower_bound = float(between_match.group(1))
        upper_bound = float(between_match.group(2))
        if lower_bound > upper_bound:
            lower_bound, upper_bound = upper_bound, lower_bound
        return {"op": "between", "lower_bound": lower_bound, "upper_bound": upper_bound}

    operator_patterns = {
        "gte": [
            rf"\b{escaped_column}\b(?:\s+is)?\s*(?:>=|=>)\s*(-?\d+(?:\.\d+)?)\b",
            rf"\b{escaped_column}\b(?:\s+is)?\s+(?:at least|greater than or equal to|no less than)\s+(-?\d+(?:\.\d+)?)\b",
        ],
        "lte": [
            rf"\b{escaped_column}\b(?:\s+is)?\s*(?:<=|=<)\s*(-?\d+(?:\.\d+)?)\b",
            rf"\b{escaped_column}\b(?:\s+is)?\s+(?:at most|less than or equal to|no more than)\s+(-?\d+(?:\.\d+)?)\b",
        ],
        "gt": [
            rf"\b{escaped_column}\b(?:\s+is)?\s*>\s*(-?\d+(?:\.\d+)?)\b",
            rf"\b{escaped_column}\b(?:\s+is)?\s+(?:above|over|greater than|more than)\s+(-?\d+(?:\.\d+)?)\b",
        ],
        "lt": [
            rf"\b{escaped_column}\b(?:\s+is)?\s*<\s*(-?\d+(?:\.\d+)?)\b",
            rf"\b{escaped_column}\b(?:\s+is)?\s+(?:below|under|less than)\s+(-?\d+(?:\.\d+)?)\b",
        ],
    }
    for operator, patterns in operator_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, lowered_question)
            if match:
                return {"op": operator, "value": float(match.group(1))}
    return None
