"""Deterministic dataset discovery and profiling for loaded sources."""

from __future__ import annotations

import warnings

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype, is_string_dtype

from saida.core.contracts import ColumnProfile, Dataset, DatasetProfile, MLReadinessProfile
from saida.exceptions import ProfileError


class SchemaDiscoveryService:
    """Build dataset intelligence from a pandas DataFrame."""

    CATEGORY_RATIO_THRESHOLD = 0.5
    IDENTIFIER_NAME_HINTS = ("id", "_id", "uuid", "key", "code")
    DATETIME_PARSE_RATIO_THRESHOLD = 0.6

    def profile(self, dataset: Dataset) -> DatasetProfile:
        """Create a deterministic profile for a dataset."""
        dataframe = dataset.data
        if dataframe.empty and len(dataframe.columns) == 0:
            raise ProfileError("Dataset contains no columns to profile.")

        columns = [self._profile_column(dataframe, column_name) for column_name in dataframe.columns]
        measure_columns = [column.name for column in columns if column.is_measure_candidate]
        dimension_columns = [column.name for column in columns if column.is_dimension_candidate]
        time_columns = [column.name for column in columns if column.is_time_candidate]
        identifier_columns = [column.name for column in columns if column.is_identifier_candidate]

        warnings_list: list[str] = []
        if dataframe.empty:
            warnings_list.append("Dataset contains no rows.")
        if int(dataframe.duplicated().sum()) > 0:
            warnings_list.append("Dataset contains duplicate rows.")
        if dataframe.empty:
            warnings_list.append("Schema discovery results may be limited because the dataset is empty.")
        if not measure_columns:
            warnings_list.append("No measure columns were detected.")
        if not dimension_columns:
            warnings_list.append("No dimension columns were detected.")
        if not time_columns:
            warnings_list.append("No datetime columns detected.")

        ml_readiness = self._build_ml_readiness(dataframe, columns, measure_columns, time_columns)

        return DatasetProfile(
            dataset_name=dataset.name,
            row_count=int(len(dataframe)),
            column_count=int(len(dataframe.columns)),
            columns=columns,
            measure_columns=measure_columns,
            dimension_columns=dimension_columns,
            time_columns=time_columns,
            identifier_columns=identifier_columns,
            duplicate_row_count=int(dataframe.duplicated().sum()),
            warnings=warnings_list,
            ml_readiness=ml_readiness,
        )

    def _profile_column(self, dataframe: pd.DataFrame, column_name: str) -> ColumnProfile:
        series = dataframe[column_name]
        row_count = len(series)
        null_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
        distinct_ratio = (unique_count / row_count) if row_count else None
        inferred_type = self._infer_type(series)
        sample_values = series.dropna().head(5).tolist()

        is_time_candidate = inferred_type in {"datetime", "date"}
        is_identifier_candidate = self._is_identifier_candidate(
            column_name=column_name,
            inferred_type=inferred_type,
            row_count=row_count,
            unique_count=unique_count,
            distinct_ratio=distinct_ratio,
        )
        is_measure_candidate = self._is_measure_candidate(
            inferred_type=inferred_type,
            distinct_ratio=distinct_ratio,
            unique_count=unique_count,
        )
        is_dimension_candidate = self._is_dimension_candidate(
            inferred_type=inferred_type,
            unique_count=unique_count,
            distinct_ratio=distinct_ratio,
            is_identifier_candidate=is_identifier_candidate,
            is_time_candidate=is_time_candidate,
        )

        warnings_list: list[str] = []
        if null_count == row_count:
            warnings_list.append("Column contains only null values.")
        if row_count > 0 and null_count / row_count > 0.5:
            warnings_list.append("Column has more than 50% null values.")
        if is_identifier_candidate and null_count > 0:
            warnings_list.append("Identifier candidate contains null values.")
        if inferred_type == "string" and distinct_ratio is not None and distinct_ratio < self.CATEGORY_RATIO_THRESHOLD:
            inferred_type = "category"

        return ColumnProfile(
            name=column_name,
            inferred_type=inferred_type,
            nullable=null_count > 0,
            null_ratio=(null_count / row_count) if row_count else 0.0,
            unique_count=unique_count,
            distinct_ratio=distinct_ratio,
            sample_values=sample_values,
            is_identifier_candidate=is_identifier_candidate,
            is_dimension_candidate=is_dimension_candidate,
            is_measure_candidate=is_measure_candidate,
            is_time_candidate=is_time_candidate,
            warnings=warnings_list,
        )

    def _infer_type(self, series: pd.Series) -> str:
        if is_datetime64_any_dtype(series):
            return "datetime"
        if is_bool_dtype(series):
            return "boolean"
        if is_numeric_dtype(series):
            if pd.api.types.is_integer_dtype(series):
                return "integer"
            if pd.api.types.is_float_dtype(series):
                return "float"
            return "numeric"
        if is_string_dtype(series):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().sum() > 0 and parsed.notna().mean() >= self.DATETIME_PARSE_RATIO_THRESHOLD:
                return "datetime"
            return "string"
        return "unknown"

    def _build_ml_readiness(
        self,
        dataframe: pd.DataFrame,
        columns: list[ColumnProfile],
        measure_columns: list[str],
        time_columns: list[str],
    ) -> MLReadinessProfile:
        candidate_targets = list(measure_columns)
        identifier_columns = [column.name for column in columns if column.is_identifier_candidate]
        candidate_features = [
            column
            for column in dataframe.columns
            if column not in candidate_targets and column not in identifier_columns
        ]
        readiness_warnings: list[str] = []
        if len(dataframe) < 12:
            readiness_warnings.append("Dataset has fewer than 12 rows; ML results may be weak.")
        if not time_columns:
            readiness_warnings.append("No time column was detected for forecasting.")
        if not candidate_targets:
            readiness_warnings.append("No candidate numeric targets were detected.")
        if not candidate_features:
            readiness_warnings.append("No candidate feature columns were detected.")

        return MLReadinessProfile(
            candidate_targets=candidate_targets,
            candidate_features=candidate_features,
            forecasting_ready=bool(time_columns and measure_columns and len(dataframe) >= 3),
            regression_ready=bool(measure_columns and candidate_features and len(dataframe) >= 12),
            classification_ready=bool(candidate_features and len(dataframe.columns) > 1 and len(dataframe) >= 12),
            detected_time_column=time_columns[0] if time_columns else None,
            readiness_warnings=readiness_warnings,
        )

    def _is_identifier_candidate(
        self,
        column_name: str,
        inferred_type: str,
        row_count: int,
        unique_count: int,
        distinct_ratio: float | None,
    ) -> bool:
        if row_count == 0 or unique_count == 0:
            return False

        name_lower = column_name.lower()
        has_identifier_name = any(
            name_lower == hint or name_lower.endswith(hint) or name_lower.startswith(hint)
            for hint in self.IDENTIFIER_NAME_HINTS
        )
        high_uniqueness = distinct_ratio is not None and distinct_ratio >= 0.98
        supported_type = inferred_type in {"string", "category", "integer"}

        if inferred_type == "integer" and not has_identifier_name:
            return False

        return supported_type and (high_uniqueness or has_identifier_name)

    def _is_measure_candidate(
        self,
        inferred_type: str,
        distinct_ratio: float | None,
        unique_count: int,
    ) -> bool:
        if inferred_type not in {"integer", "float", "numeric"}:
            return False
        if unique_count <= 1 and distinct_ratio not in {1.0, None}:
            return False
        if distinct_ratio is not None and distinct_ratio < 0.02:
            return False
        return True

    def _is_dimension_candidate(
        self,
        inferred_type: str,
        unique_count: int,
        distinct_ratio: float | None,
        is_identifier_candidate: bool,
        is_time_candidate: bool,
    ) -> bool:
        if is_time_candidate:
            return False
        if inferred_type in {"string", "category", "boolean"}:
            return True
        if is_identifier_candidate:
            return True
        if inferred_type in {"integer", "numeric"} and distinct_ratio is not None and distinct_ratio <= 0.2:
            return unique_count > 1
        return False


DatasetProfiler = SchemaDiscoveryService
