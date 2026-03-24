"""Metadata-backed compute adapter."""

from __future__ import annotations

import pandas as pd

from saida.adapters.interfaces import ComputeInterface, ComputeRequest, ComputeResponse
from saida.core.contracts import ColumnProfile, DatasetProfile, TableArtifact
from saida.exceptions import ComputeError


class MetadataComputeAdapter(ComputeInterface):
    """Execute schema and metadata methods against a dataset profile."""

    HIGH_CARDINALITY_DISTINCT_RATIO = 0.8

    @property
    def tool_family(self) -> str:
        return "metadata"

    def supported_methods(self) -> tuple[str, ...]:
        return (
            "column_count",
            "column_inventory",
            "column_type_inventory",
            "numeric_column_inventory",
            "numeric_column_count",
            "categorical_column_inventory",
            "categorical_column_count",
            "measure_inventory",
            "measure_count",
            "dimension_inventory",
            "dimension_count",
            "time_column_inventory",
            "time_column_count",
            "missing_value_inventory",
            "identifier_inventory",
            "identifier_count",
            "high_cardinality_inventory",
            "high_cardinality_count",
            "column_property_check",
            "column_presence_check",
        )

    def execute(self, request: ComputeRequest) -> ComputeResponse:
        profile = request.profile
        if profile is None:
            raise ComputeError("Metadata compute methods require a dataset profile.")
        if request.method_id == "column_property_check":
            return ComputeResponse(tables=[self._column_property_check_table(request.parameters, profile)])
        if request.method_id == "column_presence_check":
            return ComputeResponse(tables=[self._column_presence_check_table(request.parameters, profile)])
        return ComputeResponse(tables=[self._metadata_table(request.method_id, profile, request.parameters)])

    def _metadata_table(
        self,
        action: str,
        profile: DatasetProfile,
        parameters: dict[str, object] | None = None,
    ) -> TableArtifact:
        parameters = parameters or {}
        if action == "column_count":
            dataframe = pd.DataFrame({"column_count": [int(profile.column_count)]})
            return TableArtifact(name="column_count", description="Count of dataset columns.", dataframe=dataframe)
        if action == "column_inventory":
            dataframe = pd.DataFrame({"column_name": [column.name for column in profile.columns]})
            return TableArtifact(name="column_inventory", description="Available dataset columns.", dataframe=dataframe)
        if action == "column_type_inventory":
            rows = []
            for column in profile.columns:
                rows.append(
                    {
                        "column_name": column.name,
                        "dtype": column.inferred_type,
                        "nullable": column.nullable,
                        "null_count": self._estimated_null_count(profile, column.null_ratio),
                        "null_ratio": column.null_ratio,
                        "unique_count": column.unique_count,
                        "distinct_ratio": column.distinct_ratio,
                        "semantic_role": self._semantic_role(column.name, profile),
                    }
                )
            target = parameters.get("target")
            if isinstance(target, str):
                rows = [row for row in rows if row["column_name"] == target]
            dataframe = pd.DataFrame(rows)
            return TableArtifact(
                name="column_type_inventory",
                description=(
                    f"Detected data type and schema properties for column '{target}'."
                    if isinstance(target, str)
                    else "Detected data types and schema properties for all columns."
                ),
                dataframe=dataframe,
            )
        if action == "numeric_column_inventory":
            rows = [
                {"column_name": column.name, "dtype": column.inferred_type}
                for column in profile.columns
                if column.inferred_type in {"integer", "float", "numeric"}
            ]
            return TableArtifact(
                name="numeric_column_inventory",
                description="Detected numeric columns.",
                dataframe=pd.DataFrame(rows, columns=["column_name", "dtype"]),
            )
        if action == "numeric_column_count":
            count = sum(1 for column in profile.columns if column.inferred_type in {"integer", "float", "numeric"})
            return TableArtifact(
                name="numeric_column_count",
                description="Count of numeric columns.",
                dataframe=pd.DataFrame({"numeric_column_count": [int(count)]}),
            )
        if action == "categorical_column_inventory":
            rows = [
                {"column_name": column.name, "dtype": column.inferred_type}
                for column in profile.columns
                if column.inferred_type in {"category", "string", "boolean"}
            ]
            return TableArtifact(
                name="categorical_column_inventory",
                description="Detected categorical and text-like columns.",
                dataframe=pd.DataFrame(rows, columns=["column_name", "dtype"]),
            )
        if action == "categorical_column_count":
            count = sum(1 for column in profile.columns if column.inferred_type in {"category", "string", "boolean"})
            return TableArtifact(
                name="categorical_column_count",
                description="Count of categorical columns.",
                dataframe=pd.DataFrame({"categorical_column_count": [int(count)]}),
            )
        if action == "measure_inventory":
            return TableArtifact(
                name="measure_inventory",
                description="Detected measure columns.",
                dataframe=pd.DataFrame({"measure_column": list(profile.measure_columns)}),
            )
        if action == "measure_count":
            return TableArtifact(
                name="measure_count",
                description="Count of measure columns.",
                dataframe=pd.DataFrame({"measure_count": [int(len(profile.measure_columns))]}),
            )
        if action == "dimension_inventory":
            return TableArtifact(
                name="dimension_inventory",
                description="Detected dimension columns.",
                dataframe=pd.DataFrame({"dimension_column": list(profile.dimension_columns)}),
            )
        if action == "dimension_count":
            return TableArtifact(
                name="dimension_count",
                description="Count of dimension columns.",
                dataframe=pd.DataFrame({"dimension_count": [int(len(profile.dimension_columns))]}),
            )
        if action == "time_column_inventory":
            rows = [
                {"time_column": column.name, "dtype": column.inferred_type}
                for column in profile.columns
                if column.name in set(profile.time_columns)
            ]
            return TableArtifact(
                name="time_column_inventory",
                description="Detected time columns.",
                dataframe=pd.DataFrame(rows, columns=["time_column", "dtype"]),
            )
        if action == "time_column_count":
            return TableArtifact(
                name="time_column_count",
                description="Count of time columns.",
                dataframe=pd.DataFrame({"time_column_count": [int(len(profile.time_columns))]}),
            )
        if action == "missing_value_inventory":
            rows = []
            for column in profile.columns:
                null_count = self._estimated_null_count(profile, column.null_ratio)
                if null_count <= 0:
                    continue
                rows.append({"column_name": column.name, "null_count": null_count, "null_ratio": column.null_ratio})
            return TableArtifact(
                name="missing_value_inventory",
                description="Columns with observed missing values.",
                dataframe=pd.DataFrame(rows, columns=["column_name", "null_count", "null_ratio"]),
            )
        if action == "identifier_inventory":
            rows = [
                {
                    "column_name": column.name,
                    "dtype": column.inferred_type,
                    "unique_count": column.unique_count,
                    "distinct_ratio": column.distinct_ratio,
                }
                for column in profile.columns
                if column.is_identifier_candidate
            ]
            return TableArtifact(
                name="identifier_inventory",
                description="Columns that look like identifiers.",
                dataframe=pd.DataFrame(rows, columns=["column_name", "dtype", "unique_count", "distinct_ratio"]),
            )
        if action == "identifier_count":
            count = sum(1 for column in profile.columns if column.is_identifier_candidate)
            return TableArtifact(
                name="identifier_count",
                description="Count of likely identifier columns.",
                dataframe=pd.DataFrame({"identifier_count": [int(count)]}),
            )
        if action == "high_cardinality_inventory":
            rows = [
                {
                    "column_name": column.name,
                    "dtype": column.inferred_type,
                    "unique_count": column.unique_count,
                    "distinct_ratio": column.distinct_ratio,
                }
                for column in profile.columns
                if column.distinct_ratio is not None and column.distinct_ratio >= self.HIGH_CARDINALITY_DISTINCT_RATIO
            ]
            return TableArtifact(
                name="high_cardinality_inventory",
                description="Columns with a high distinct-value ratio.",
                dataframe=pd.DataFrame(rows, columns=["column_name", "dtype", "unique_count", "distinct_ratio"]),
            )
        if action == "high_cardinality_count":
            count = sum(
                1
                for column in profile.columns
                if column.distinct_ratio is not None and column.distinct_ratio >= self.HIGH_CARDINALITY_DISTINCT_RATIO
            )
            return TableArtifact(
                name="high_cardinality_count",
                description="Count of high-cardinality columns.",
                dataframe=pd.DataFrame({"high_cardinality_count": [int(count)]}),
            )
        raise ComputeError(f"Unsupported metadata method: {action}")

    def _estimated_null_count(self, profile: DatasetProfile, null_ratio: float) -> int:
        return int(round(profile.row_count * null_ratio))

    def _column_property_check_table(self, parameters: dict[str, object], profile: DatasetProfile) -> TableArtifact:
        target = str(parameters["target"])
        expected_property = str(parameters["expected_property"])
        column = next((column for column in profile.columns if column.name == target), None)
        matches = self._column_matches_property(column, profile, expected_property) if column is not None else False
        return TableArtifact(
            name="column_property_check",
            description="Verification of a requested schema property for a column.",
            dataframe=pd.DataFrame(
                [
                    {
                        "column_name": target,
                        "expected_property": expected_property,
                        "matches": bool(matches),
                        "column_exists": bool(column is not None),
                        "dtype": column.inferred_type if column is not None else None,
                        "semantic_role": self._semantic_role(target, profile) if column is not None else None,
                        "is_identifier_candidate": bool(column.is_identifier_candidate) if column is not None else False,
                        "distinct_ratio": column.distinct_ratio if column is not None else None,
                    }
                ]
            ),
        )

    def _column_presence_check_table(self, parameters: dict[str, object], profile: DatasetProfile) -> TableArtifact:
        requested_column = str(parameters["requested_column"])
        profile_columns = {column.name.lower(): column.name for column in profile.columns}
        matched_column = profile_columns.get(requested_column.lower())
        column = next((item for item in profile.columns if item.name == matched_column), None)
        return TableArtifact(
            name="column_presence_check",
            description="Verification of whether a requested column exists in the dataset schema.",
            dataframe=pd.DataFrame(
                [
                    {
                        "requested_column": requested_column,
                        "matched_column": matched_column,
                        "exists": bool(matched_column is not None),
                        "dtype": column.inferred_type if column is not None else None,
                        "semantic_role": self._semantic_role(matched_column, profile) if matched_column is not None else None,
                    }
                ]
            ),
        )

    def _column_matches_property(
        self,
        column: ColumnProfile,
        profile: DatasetProfile,
        expected_property: str,
    ) -> bool:
        if expected_property == "datetime":
            return column.name in set(profile.time_columns) or column.inferred_type == "datetime"
        if expected_property == "numeric":
            return column.name in set(profile.measure_columns) or column.inferred_type in {"integer", "float", "numeric"}
        if expected_property == "categorical":
            return column.name in set(profile.dimension_columns) or column.inferred_type in {"category", "string", "boolean"}
        if expected_property == "identifier":
            return column.name in set(profile.identifier_columns) or bool(column.is_identifier_candidate)
        if expected_property == "dimension":
            return column.name in set(profile.dimension_columns)
        if expected_property == "measure":
            return column.name in set(profile.measure_columns)
        if expected_property == "high_cardinality":
            return bool(column.distinct_ratio is not None and column.distinct_ratio >= self.HIGH_CARDINALITY_DISTINCT_RATIO)
        return False

    def _semantic_role(self, column_name: str, profile: DatasetProfile) -> str:
        if column_name in set(profile.time_columns):
            return "time"
        if column_name in set(profile.identifier_columns):
            return "identifier"
        if column_name in set(profile.measure_columns):
            return "measure"
        if column_name in set(profile.dimension_columns):
            return "dimension"
        return "unclassified"
