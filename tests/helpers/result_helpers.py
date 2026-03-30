from __future__ import annotations

from typing import Any


def normalized_result_value(result_payload: dict[str, Any]) -> Any:
    value = result_payload.get("value")
    logical_shape = result_payload.get("logical_shape")

    if logical_shape == "scalar" and isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        row = value[0]
        if len(row) == 1:
            return next(iter(row.values()))

    if logical_shape == "verification" and isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]

    if logical_shape == "table" and isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]

    return value


def result_row_count(result_payload: dict[str, Any]) -> int | None:
    row_count = result_payload.get("row_count")
    if isinstance(row_count, int):
        return row_count

    metadata = result_payload.get("metadata")
    if isinstance(metadata, dict):
        pagination = metadata.get("pagination")
        if isinstance(pagination, dict) and isinstance(pagination.get("total_rows"), int):
            return pagination["total_rows"]

    value = result_payload.get("value")
    if isinstance(value, list):
        return len(value)

    return None

