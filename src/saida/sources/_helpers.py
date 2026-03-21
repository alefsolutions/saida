"""Shared source helper utilities."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from saida.core.context import SourceContextParser
from saida.exceptions import AdapterError
from saida.core.contracts import Dataset, SourceContext


def load_context(context_path: str | Path | None) -> SourceContext | None:
    """Load optional semantic context from disk."""
    if context_path is None:
        return None
    return SourceContextParser().parse_file(context_path)


def build_dataset(
    dataframe: pd.DataFrame,
    *,
    name: str,
    source_type: str,
    metadata: dict[str, object] | None = None,
    context: SourceContext | None = None,
) -> Dataset:
    """Validate a loaded frame and return the canonical SAIDA dataset schema."""
    prepared = dataframe.copy()
    prepared.columns = [_normalize_column_name(column_name) for column_name in prepared.columns]

    if prepared.columns.empty:
        raise AdapterError("Loaded dataset has no columns.")
    if prepared.empty:
        raise AdapterError("Loaded dataset is empty.")

    duplicate_columns = prepared.columns[prepared.columns.duplicated()].tolist()
    if duplicate_columns:
        joined_columns = ", ".join(str(column_name) for column_name in duplicate_columns)
        raise AdapterError(f"Loaded dataset contains duplicate column names: {joined_columns}")

    dataset_metadata = dict(metadata or {})
    dataset_metadata["row_count"] = int(len(prepared))
    dataset_metadata["column_count"] = int(len(prepared.columns))

    return Dataset(
        name=name,
        source_type=source_type,
        data=prepared,
        metadata=dataset_metadata,
        context=context,
    )


def _normalize_column_name(column_name: object) -> str:
    text = str(column_name).strip()
    if not text:
        raise AdapterError("Loaded dataset contains an empty column name.")
    return text
