"""Validation helpers for datasets and plans."""

from __future__ import annotations

import pandas as pd

from saida.exceptions import PlanningError, ValidationError
from saida.core.contracts import AnalysisPlan, Dataset


class PlanValidator:
    """Validate datasets and canonical plans before execution."""

    def validate_dataset(self, dataset: Dataset) -> None:
        """Validate the incoming dataset payload."""
        if not isinstance(dataset.data, pd.DataFrame):
            raise ValidationError("Dataset.data must be a pandas DataFrame.")
        if dataset.data.empty:
            raise ValidationError("Cannot analyze an empty dataset.")
        if len(dataset.data.columns) == 0:
            raise ValidationError("Cannot analyze a dataset with no columns.")
        duplicate_columns = dataset.data.columns[dataset.data.columns.duplicated()].tolist()
        if duplicate_columns:
            joined = ", ".join(str(column_name) for column_name in duplicate_columns)
            raise ValidationError(f"Dataset contains duplicate column names: {joined}")

    def validate_plan(self, plan: AnalysisPlan) -> None:
        """Validate that the plan contains executable steps."""
        if not plan.steps:
            raise PlanningError("Analysis plan contains no executable steps.")
