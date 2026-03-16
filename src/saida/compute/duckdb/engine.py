"""DuckDB-backed deterministic analytics."""

from __future__ import annotations

import duckdb
import pandas as pd
import warnings

from saida.exceptions import ComputeError
from saida.schemas import Metric, TableArtifact


class DuckDBComputeEngine:
    """Run deterministic analytical queries against a pandas DataFrame."""

    AGGREGATION_EXPRESSIONS = {
        "sum": "sum(target_value)",
        "mean": "avg(target_value)",
        "max": "max(target_value)",
        "min": "min(target_value)",
        "count": "count(target_value)",
    }

    def dataset_summary(
        self,
        dataframe: pd.DataFrame,
        target: str | None,
        filters: dict[str, str] | None = None,
    ) -> tuple[list[Metric], list[TableArtifact]]:
        """Compute top-level metrics for the dataset."""
        prepared = self._apply_filters(dataframe, filters)
        if target is not None:
            self._require_columns(prepared, [target])
        metrics = [
            Metric(name="row_count", value=int(len(prepared)), description="Number of rows in the dataset."),
            Metric(name="column_count", value=int(len(prepared.columns)), description="Number of columns in the dataset."),
        ]
        if target and pd.api.types.is_numeric_dtype(prepared[target]):
            try:
                connection = duckdb.connect()
                connection.register("source_df", self._prepare_for_duckdb(prepared))
                value = connection.execute(f'select sum("{target}") as total_value from source_df').fetchone()[0]
                connection.close()
            except Exception as exc:  # pragma: no cover
                raise ComputeError(f"Failed to compute summary metric for target '{target}'.") from exc
            metrics.append(Metric(name=f"{target}_sum", value=float(value or 0.0), description=f"Sum of {target}."))

        preview = prepared.head(10).copy()
        tables = [TableArtifact(name="dataset_preview", description="First 10 rows of the dataset.", dataframe=preview)]
        return metrics, tables

    def row_count(
        self,
        dataframe: pd.DataFrame,
        filters: dict[str, str] | None = None,
    ) -> list[Metric]:
        """Count rows in the dataset or filtered slice."""
        prepared = self._apply_filters(dataframe, filters)
        return [Metric(name="row_count", value=int(len(prepared)), description="Number of rows in the dataset slice.")]

    def distinct_values(
        self,
        dataframe: pd.DataFrame,
        target: str,
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """List distinct values for a dimension column with row counts."""
        prepared = self._apply_filters(dataframe, filters)
        self._require_columns(prepared, [target])
        query = f"""
            select
                "{target}" as "{target}",
                count(*) as row_count
            from source_df
            group by "{target}"
            order by "{target}"
        """
        try:
            connection = duckdb.connect()
            connection.register("source_df", self._prepare_for_duckdb(prepared))
            values = connection.execute(query).fetchdf()
            connection.close()
        except Exception as exc:  # pragma: no cover
            raise ComputeError(f"Failed to compute distinct values for target '{target}'.") from exc
        return TableArtifact(
            name="distinct_values",
            description=f"Distinct values for {target}.",
            dataframe=values,
        )

    def time_coverage(
        self,
        dataframe: pd.DataFrame,
        time_column: str,
        mode: str = "years_present",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Inspect the temporal coverage of a datetime column."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [time_column])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column])

        if mode == "years_present":
            years = sorted(int(value) for value in prepared[time_column].dt.year.dropna().unique().tolist())
            coverage = pd.DataFrame({"year": years})
        elif mode == "months_present":
            months = sorted(prepared[time_column].dt.to_period("M").astype(str).dropna().unique().tolist())
            coverage = pd.DataFrame({"month": months})
        elif mode == "date_range":
            if prepared.empty:
                coverage = pd.DataFrame(columns=["earliest_date", "latest_date", "non_null_row_count"])
            else:
                earliest_date = prepared[time_column].min().date().isoformat()
                latest_date = prepared[time_column].max().date().isoformat()
                coverage = pd.DataFrame(
                    {
                        "earliest_date": [earliest_date],
                        "latest_date": [latest_date],
                        "non_null_row_count": [int(len(prepared))],
                    }
                )
        else:
            raise ComputeError(f"Unsupported time coverage mode: {mode}")

        return TableArtifact(
            name="time_coverage",
            description=f"Temporal coverage for {time_column} using mode {mode}.",
            dataframe=coverage,
        )

    def count_rows_by_group(
        self,
        dataframe: pd.DataFrame,
        group_by: list[str],
        filters: dict[str, str] | None = None,
        ascending: bool = False,
        limit: int | None = None,
    ) -> TableArtifact:
        """Count rows by group and rank the results."""
        prepared = self._apply_filters(dataframe, filters)
        self._require_columns(prepared, group_by)
        group_column_sql = ", ".join(group_by)
        order_direction = "asc" if ascending else "desc"
        query = f"""
            select
                {group_column_sql},
                count(*) as row_count
            from source_df
            group by {group_column_sql}
            order by row_count {order_direction}, {group_column_sql}
        """
        try:
            connection = duckdb.connect()
            connection.register("source_df", self._prepare_for_duckdb(prepared))
            grouped = connection.execute(query).fetchdf()
            connection.close()
        except Exception as exc:  # pragma: no cover
            raise ComputeError("Failed to count rows by group.") from exc
        if limit is not None:
            grouped = grouped.head(limit).copy()
        return TableArtifact(
            name="group_row_counts",
            description="Row counts grouped by dimension.",
            dataframe=grouped.reset_index(drop=True),
        )

    def aggregate_value(
        self,
        dataframe: pd.DataFrame,
        target: str,
        aggregation: str,
        filters: dict[str, str] | None = None,
    ) -> list[Metric]:
        """Compute a single deterministic aggregate value for a target column."""
        prepared = self._apply_filters(dataframe, filters)
        self._require_columns(prepared, [target])
        expression = self._aggregation_expression(aggregation)
        try:
            connection = duckdb.connect()
            connection.register(
                "source_df",
                self._prepare_for_duckdb(prepared.assign(target_value=prepared[target])),
            )
            value = connection.execute(f"select {expression} as aggregate_value from source_df").fetchone()[0]
            connection.close()
        except Exception as exc:  # pragma: no cover
            raise ComputeError(f"Failed to compute {aggregation} for target '{target}'.") from exc

        if aggregation == "count":
            metric_value: float | int = int(value or 0)
        else:
            metric_value = float(value or 0.0)
        return [
            Metric(
                name=f"{target}_{aggregation}",
                value=metric_value,
                description=f"{aggregation.title()} of {target}.",
            )
        ]

    def ranked_rows(
        self,
        dataframe: pd.DataFrame,
        target: str,
        filters: dict[str, str] | None = None,
        ascending: bool = False,
        limit: int = 5,
    ) -> TableArtifact:
        """Return the top or bottom rows by a numeric target."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [target])
        numeric_target = pd.to_numeric(prepared[target], errors="coerce")
        prepared = prepared.assign(_rank_target=numeric_target).dropna(subset=["_rank_target"])
        if prepared.empty:
            raise ComputeError(f"Target column '{target}' has no numeric values for row ranking.")
        ordered = prepared.sort_values(["_rank_target"], ascending=ascending).head(limit).copy()
        ordered.insert(0, "rank", range(1, len(ordered) + 1))
        ordered[target] = ordered["_rank_target"].astype(float)
        ordered = ordered.drop(columns=["_rank_target"])
        direction_label = "Bottom" if ascending else "Top"
        return TableArtifact(
            name="ranked_rows",
            description=f"{direction_label} {limit} rows ranked by {target}.",
            dataframe=ordered.reset_index(drop=True),
        )

    def time_trend(
        self,
        dataframe: pd.DataFrame,
        target: str,
        time_column: str,
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Aggregate a target over monthly time buckets."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [target, time_column])
        expression = self._aggregation_expression(aggregation)
        prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column])
        prepared["period_month"] = prepared[time_column].dt.to_period("M").astype(str)
        query = f"""
            with monthly_totals as (
                select
                    period_month,
                    {expression} as target_total
                from prepared
                group by period_month
            )
            select
                period_month,
                target_total,
                target_total - lag(target_total) over(order by period_month) as period_delta
            from monthly_totals
            order by period_month
        """
        try:
            connection = duckdb.connect()
            connection.register(
                "prepared",
                self._prepare_for_duckdb(prepared.assign(target_value=prepared[target])),
            )
            trend = connection.execute(query).fetchdf()
            connection.close()
        except Exception as exc:  # pragma: no cover
            raise ComputeError(f"Failed to compute time trend for target '{target}'.") from exc
        return TableArtifact(name="time_trend", description=f"Monthly {aggregation} trend for {target}.", dataframe=trend)

    def grouped_period_comparison(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_by: list[str],
        time_column: str,
        time_reference: dict[str, str],
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Compare grouped totals between adjacent periods."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [target, time_column, *group_by])
        expression = self._aggregation_expression(aggregation)
        prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column, target])
        prepared["period_month"] = prepared[time_column].dt.to_period("M")

        periods = self._resolve_adjacent_periods(prepared, time_reference)
        if periods is None:
            return TableArtifact(
                name="grouped_period_comparison",
                description="No comparable grouped periods could be derived from the request.",
                dataframe=pd.DataFrame(columns=[*group_by, "previous_total", "current_total", "delta", "pct_change"]),
            )

        current_period, previous_period = periods
        current_slice = prepared.loc[prepared["period_month"] == current_period]
        previous_slice = prepared.loc[prepared["period_month"] == previous_period]

        current_grouped = self._grouped_aggregate(current_slice, group_by, target, expression, "current_total")
        previous_grouped = self._grouped_aggregate(previous_slice, group_by, target, expression, "previous_total")

        comparison = current_grouped.merge(previous_grouped, on=group_by, how="outer").fillna(0.0)
        comparison["delta"] = comparison["current_total"] - comparison["previous_total"]
        comparison["pct_change"] = comparison.apply(
            lambda row: float(row["delta"] / row["previous_total"]) if row["previous_total"] else 0.0,
            axis=1,
        )
        comparison = comparison.sort_values("delta")

        return TableArtifact(
            name="grouped_period_comparison",
            description=f"Grouped {aggregation} period comparison for {target}.",
            dataframe=comparison.reset_index(drop=True),
        )

    def top_movers(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_by: list[str],
        time_column: str,
        time_reference: dict[str, str],
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
        limit: int = 5,
    ) -> TableArtifact:
        """Return the largest grouped movers between adjacent periods."""
        comparison = self.grouped_period_comparison(
            dataframe=dataframe,
            target=target,
            group_by=group_by,
            time_column=time_column,
            time_reference=time_reference,
            aggregation=aggregation,
            filters=filters,
        ).dataframe.copy()

        if comparison.empty:
            return TableArtifact(
                name="top_movers",
            description=f"No movers were available for {target}.",
                dataframe=comparison,
            )

        comparison["abs_delta"] = comparison["delta"].abs()
        comparison = comparison.sort_values("abs_delta", ascending=False).head(limit).copy()
        comparison["rank"] = range(1, len(comparison) + 1)

        ordered_columns = ["rank", *group_by, "previous_total", "current_total", "delta", "pct_change", "abs_delta"]
        comparison = comparison.loc[:, [column for column in ordered_columns if column in comparison.columns]]
        return TableArtifact(
            name="top_movers",
            description=f"Top {limit} movers for {target} using {aggregation}.",
            dataframe=comparison.reset_index(drop=True),
        )

    def group_breakdown(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_by: list[str],
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Aggregate a target by one or more grouping columns."""
        prepared = self._apply_filters(dataframe, filters)
        self._require_columns(prepared, [target, *group_by])
        expression = self._aggregation_expression(aggregation)
        group_column_sql = ", ".join(group_by)
        query = f"""
            select
                {group_column_sql},
                {expression} as target_total
            from prepared
            group by {group_column_sql}
            order by target_total desc
        """
        try:
            connection = duckdb.connect()
            connection.register(
                "prepared",
                self._prepare_for_duckdb(prepared.assign(target_value=prepared[target])),
            )
            grouped = connection.execute(query).fetchdf()
            connection.close()
        except Exception as exc:  # pragma: no cover
            raise ComputeError(f"Failed to compute grouped breakdown for target '{target}'.") from exc
        return TableArtifact(name="group_breakdown", description=f"Grouped {aggregation} breakdown for {target}.", dataframe=grouped)

    def ranked_breakdown(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_by: list[str],
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
        limit: int = 5,
        ascending: bool = False,
    ) -> TableArtifact:
        """Return the top grouped contributors by target total."""
        grouped = self.group_breakdown(dataframe, target, group_by, aggregation, filters).dataframe.copy()
        grouped = grouped.sort_values("target_total", ascending=ascending).head(limit).copy()
        grouped["rank"] = range(1, len(grouped) + 1)
        ordered_columns = ["rank", *group_by, "target_total"]
        ranked = grouped.loc[:, [column for column in ordered_columns if column in grouped.columns]]
        direction_label = "Bottom" if ascending else "Top"
        return TableArtifact(
            name="ranked_breakdown",
            description=f"{direction_label} {limit} grouped contributors for {target} using {aggregation}.",
            dataframe=ranked,
        )

    def contribution_breakdown(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_by: list[str],
        time_column: str | None = None,
        time_reference: dict[str, str] | None = None,
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Measure group contribution deltas between adjacent periods when possible."""
        self._require_columns(dataframe, [target, *group_by])
        if time_column is None or time_reference is None:
            grouped = self.group_breakdown(dataframe, target, group_by, aggregation, filters).dataframe.copy()
            total = float(grouped["target_total"].sum()) if not grouped.empty else 0.0
            grouped["share_of_total"] = grouped["target_total"].apply(lambda value: float(value / total) if total else 0.0)
            return TableArtifact(
                name="contribution_breakdown",
                description=f"Share of total {aggregation} {target} by group.",
                dataframe=grouped,
            )

        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [time_column])
        prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column, target])
        prepared["period_month"] = prepared[time_column].dt.to_period("M")

        if time_reference.get("type") != "month_name":
            return self.contribution_breakdown(
                dataframe,
                target,
                group_by,
                time_column=None,
                time_reference=None,
                aggregation=aggregation,
                filters=filters,
            )

        requested_month = int(time_reference["month"])
        matching_periods = prepared.loc[prepared["period_month"].dt.month == requested_month, "period_month"].sort_values()
        if matching_periods.empty:
            return TableArtifact(
                name="contribution_breakdown",
                description="No rows matched the requested period for contribution analysis.",
                dataframe=pd.DataFrame(columns=[*group_by, "previous_total", "current_total", "delta"]),
            )

        current_period = matching_periods.iloc[-1]
        previous_period = current_period - 1

        current_slice = prepared.loc[prepared["period_month"] == current_period]
        previous_slice = prepared.loc[prepared["period_month"] == previous_period]

        expression = self._aggregation_expression(aggregation)
        current_grouped = self._grouped_aggregate(current_slice, group_by, target, expression, "current_total")
        previous_grouped = self._grouped_aggregate(previous_slice, group_by, target, expression, "previous_total")

        merged = current_grouped.merge(previous_grouped, on=group_by, how="outer").fillna(0.0)
        merged["delta"] = merged["current_total"] - merged["previous_total"]
        merged = merged.sort_values("delta")

        return TableArtifact(
            name="contribution_breakdown",
            description=f"Contribution deltas for {aggregation} {target} between adjacent periods.",
            dataframe=merged.reset_index(drop=True),
        )

    def period_comparison(
        self,
        dataframe: pd.DataFrame,
        target: str,
        time_column: str,
        time_reference: dict[str, str],
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Compare a selected period against the immediately previous comparable period."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [target, time_column])
        expression = self._aggregation_expression(aggregation)
        prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column, target])
        prepared["period_month"] = prepared[time_column].dt.to_period("M")

        if time_reference.get("type") != "month_name":
            empty = pd.DataFrame(columns=["period", "target_total"])
            return TableArtifact(
                name="period_comparison",
                description="No comparable period could be derived from the request.",
                dataframe=empty,
            )

        periods = self._resolve_adjacent_periods(prepared, time_reference)
        if periods is None:
            empty = pd.DataFrame(columns=["period", "target_total"])
            return TableArtifact(
                name="period_comparison",
                description="No rows matched the requested period.",
                dataframe=empty,
            )
        current_period, previous_period = periods

        current_total = self._aggregate_series(prepared.loc[prepared["period_month"] == current_period, target], aggregation)
        previous_total = self._aggregate_series(prepared.loc[prepared["period_month"] == previous_period, target], aggregation)

        comparison = pd.DataFrame(
            {
                "period": [str(previous_period), str(current_period)],
                "target_total": [float(previous_total), float(current_total)],
            }
        )
        comparison["delta"] = comparison["target_total"].diff()

        return TableArtifact(
            name="period_comparison",
            description=f"Comparison for {aggregation} {target} across adjacent periods.",
            dataframe=comparison,
        )

    def _resolve_adjacent_periods(
        self,
        dataframe: pd.DataFrame,
        time_reference: dict[str, str],
    ) -> tuple[pd.Period, pd.Period] | None:
        if time_reference.get("type") != "month_name":
            return None

        requested_month = int(time_reference["month"])
        matching_periods = dataframe.loc[dataframe["period_month"].dt.month == requested_month, "period_month"].sort_values()
        if matching_periods.empty:
            return None

        current_period = matching_periods.iloc[-1]
        previous_period = current_period - 1
        return current_period, previous_period

    def _apply_filters(self, dataframe: pd.DataFrame, filters: dict[str, str] | None) -> pd.DataFrame:
        if not filters:
            return dataframe

        prepared = dataframe.copy()
        for column_name, expected_value in filters.items():
            if column_name not in prepared.columns:
                raise ComputeError(f"Filter column '{column_name}' does not exist in the dataset.")

            series = prepared[column_name]
            if pd.api.types.is_string_dtype(series):
                prepared = prepared.loc[series.astype(str).str.lower() == expected_value.lower()]
            else:
                prepared = prepared.loc[series.astype(str) == str(expected_value)]

        if prepared.empty:
            raise ComputeError("Filters removed all rows from the dataset.")
        return prepared

    def _require_columns(self, dataframe: pd.DataFrame, column_names: list[str]) -> None:
        missing_columns = [column_name for column_name in column_names if column_name not in dataframe.columns]
        if missing_columns:
            joined = ", ".join(missing_columns)
            raise ComputeError(f"Required columns are missing from the dataset: {joined}")

    def _aggregation_expression(self, aggregation: str) -> str:
        if aggregation not in self.AGGREGATION_EXPRESSIONS:
            raise ComputeError(f"Unsupported aggregation: {aggregation}")
        return self.AGGREGATION_EXPRESSIONS[aggregation]

    def _grouped_aggregate(
        self,
        dataframe: pd.DataFrame,
        group_by: list[str],
        target: str,
        expression: str,
        output_name: str,
    ) -> pd.DataFrame:
        prepared = dataframe.assign(target_value=dataframe[target])
        group_column_sql = ", ".join(group_by)
        query = f"""
            select
                {group_column_sql},
                {expression} as {output_name}
            from prepared
            group by {group_column_sql}
        """
        try:
            connection = duckdb.connect()
            connection.register("prepared", self._prepare_for_duckdb(prepared))
            grouped = connection.execute(query).fetchdf()
            connection.close()
        except Exception as exc:  # pragma: no cover
            raise ComputeError("Failed to compute grouped aggregate.") from exc
        return grouped

    def _prepare_for_duckdb(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        prepared = dataframe.copy()
        for column_name in prepared.columns:
            if isinstance(prepared[column_name].dtype, pd.PeriodDtype):
                prepared[column_name] = prepared[column_name].astype(str)
        return prepared

    def _aggregate_series(self, series: pd.Series, aggregation: str) -> float:
        numeric_series = pd.to_numeric(series, errors="coerce").dropna()
        if numeric_series.empty:
            return 0.0
        if aggregation == "sum":
            return float(numeric_series.sum())
        if aggregation == "mean":
            return float(numeric_series.mean())
        if aggregation == "max":
            return float(numeric_series.max())
        if aggregation == "min":
            return float(numeric_series.min())
        if aggregation == "count":
            return float(numeric_series.count())
        raise ComputeError(f"Unsupported aggregation: {aggregation}")
