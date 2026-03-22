"""DuckDB backend adapter."""

from __future__ import annotations

import duckdb
import pandas as pd
import warnings

from saida.exceptions import ComputeError
from saida.core.contracts import Metric, TableArtifact


class DuckDBAdapter:
    """Run analytical plan steps against DuckDB."""

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

    def distinct_value_count(
        self,
        dataframe: pd.DataFrame,
        target: str,
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Return the number of distinct values for a dimension column."""
        prepared = self._apply_filters(dataframe, filters)
        self._require_columns(prepared, [target])
        query = f'select count(distinct "{target}") as distinct_count from source_df'
        try:
            connection = duckdb.connect()
            connection.register("source_df", self._prepare_for_duckdb(prepared))
            values = connection.execute(query).fetchdf()
            connection.close()
        except Exception as exc:  # pragma: no cover
            raise ComputeError(f"Failed to compute distinct value count for target '{target}'.") from exc
        return TableArtifact(
            name="distinct_value_count",
            description=f"Distinct value count for {target}.",
            dataframe=values,
        )

    def tabular_query(
        self,
        dataframe: pd.DataFrame,
        selected_columns: list[str] | None = None,
        filters: dict[str, object] | None = None,
        sort_by: str | None = None,
        sort_direction: str = "asc",
        limit: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> TableArtifact:
        """Return a filtered, sorted, and paginated table result."""
        prepared = self._filter_dataframe(dataframe, filters, allow_empty=True).copy()
        selected_columns = selected_columns or list(prepared.columns)
        self._require_columns(prepared, selected_columns)
        if sort_by is not None:
            self._require_columns(prepared, [sort_by])
            prepared = self._sort_dataframe(prepared, sort_by, sort_direction)
        limited = prepared.head(limit).copy() if limit is not None else prepared.copy()
        page_frame, pagination = self._paginate_frame(limited, page, page_size)
        result = page_frame.loc[:, selected_columns].reset_index(drop=True)
        return TableArtifact(
            name="tabular_query",
            description="Filtered rows returned for a natural-language table query.",
            dataframe=result,
            metadata={
                "pagination": pagination,
                "query": {
                    "selected_columns": list(selected_columns),
                    "sort_by": sort_by,
                    "sort_direction": sort_direction,
                    "limit": limit,
                    "filters": filters or {},
                },
            },
        )

    def grouped_tabular_query(
        self,
        dataframe: pd.DataFrame,
        group_by: list[str],
        target: str | None = None,
        aggregation: str = "count",
        filters: dict[str, object] | None = None,
        sort_by: str | None = None,
        sort_direction: str = "desc",
        limit: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> TableArtifact:
        """Return a grouped and paginated table result for discovery workflows."""
        prepared = self._filter_dataframe(dataframe, filters, allow_empty=True).copy()
        required_columns = list(group_by)
        if target is not None:
            required_columns.append(target)
        self._require_columns(prepared, required_columns)

        if target is None or aggregation == "count":
            grouped = (
                prepared.groupby(group_by, as_index=False)
                .size()
                .rename(columns={"size": "row_count"})
            )
            aggregate_column = "row_count"
        else:
            prepared["_group_target"] = pd.to_numeric(prepared[target], errors="coerce")
            prepared = prepared.dropna(subset=["_group_target"])
            if prepared.empty:
                grouped = pd.DataFrame(columns=[*group_by, "target_total"])
            else:
                grouped = (
                    prepared.groupby(group_by, as_index=False)["_group_target"]
                    .agg(self._aggregation_function(aggregation))
                    .rename(columns={"_group_target": "target_total"})
                )
            aggregate_column = "target_total"

        resolved_sort_by = sort_by
        if resolved_sort_by in {None, target, "count"}:
            resolved_sort_by = aggregate_column
        if resolved_sort_by not in grouped.columns and resolved_sort_by is not None:
            raise ComputeError(f"Grouped tabular sort column '{resolved_sort_by}' is not available.")
        if resolved_sort_by is not None and not grouped.empty:
            grouped = self._sort_dataframe(grouped, resolved_sort_by, sort_direction)

        limited = grouped.head(limit).copy() if limit is not None else grouped.copy()
        page_frame, pagination = self._paginate_frame(limited, page, page_size)
        result = page_frame.reset_index(drop=True)
        return TableArtifact(
            name="grouped_tabular_query",
            description="Grouped table returned for a natural-language discovery query.",
            dataframe=result,
            metadata={
                "pagination": pagination,
                "query": {
                    "group_by": list(group_by),
                    "target": target,
                    "aggregation": aggregation,
                    "sort_by": resolved_sort_by,
                    "sort_direction": sort_direction,
                    "limit": limit,
                    "filters": filters or {},
                },
            },
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

    def time_bucket_counts(
        self,
        dataframe: pd.DataFrame,
        time_column: str,
        bucket: str = "year",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Count rows across derived year or month buckets from a datetime column."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [time_column])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column])

        prepared = self._prepare_time_bucket_frame(prepared, time_column, bucket)
        bucket_column = self._bucket_label_column(bucket)
        counted = (
            prepared.groupby(["_period_bucket", bucket_column], as_index=False)
            .size()
            .rename(columns={"size": "row_count"})
            .sort_values("_period_bucket")
            .drop(columns=["_period_bucket"])
            .reset_index(drop=True)
        )

        return TableArtifact(
            name="time_bucket_counts",
            description=f"Row counts by {bucket} for {time_column}.",
            dataframe=counted,
        )

    def time_bucket_breakdown(
        self,
        dataframe: pd.DataFrame,
        target: str,
        time_column: str,
        bucket: str = "month",
        aggregation: str = "sum",
        group_by: list[str] | None = None,
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Aggregate a numeric target across derived time buckets, optionally by group."""
        prepared = self._apply_filters(dataframe, filters).copy()
        group_by = group_by or []
        self._require_columns(prepared, [target, time_column, *group_by])
        prepared = self._prepare_time_bucket_frame(prepared, time_column, bucket)
        prepared["target_value"] = pd.to_numeric(prepared[target], errors="coerce")
        prepared = prepared.dropna(subset=["target_value"])
        if prepared.empty:
            raise ComputeError(f"Target column '{target}' has no numeric values for time bucket analysis.")

        aggregation_function = self._aggregation_function(aggregation)
        bucket_column = self._bucket_label_column(bucket)
        grouped = (
            prepared.groupby(["_period_bucket", bucket_column, *group_by], as_index=False)["target_value"]
            .agg(aggregation_function)
            .rename(columns={"target_value": "target_total"})
            .sort_values(["_period_bucket", *group_by])
            .drop(columns=["_period_bucket"])
            .reset_index(drop=True)
        )

        return TableArtifact(
            name="time_bucket_breakdown",
            description=f"{bucket.title()} {aggregation} breakdown for {target}.",
            dataframe=grouped,
        )

    def row_existence(
        self,
        dataframe: pd.DataFrame,
        filters: dict[str, object],
    ) -> TableArtifact:
        """Return whether any rows match the requested filters."""
        prepared = self._filter_dataframe(dataframe, filters, allow_empty=True)

        return TableArtifact(
            name="row_existence",
            description="Whether matching rows exist for the requested filters.",
            dataframe=pd.DataFrame(
                [
                    {
                        "exists": bool(not prepared.empty),
                        "matching_row_count": int(len(prepared)),
                    }
                ]
            ),
        )

    def time_value_exists(
        self,
        dataframe: pd.DataFrame,
        time_column: str,
        expected_year: int | None = None,
        time_reference: dict[str, str] | None = None,
        filters: dict[str, object] | None = None,
    ) -> TableArtifact:
        """Return whether a requested time value exists in a datetime column."""
        prepared = dataframe.copy()
        self._require_columns(prepared, [time_column])
        if filters:
            prepared = self._filter_dataframe(prepared, filters, allow_empty=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column])

        label: str
        if expected_year is not None:
            matches = prepared.loc[prepared[time_column].dt.year == expected_year]
            label = str(expected_year)
        elif time_reference and time_reference.get("type") == "month_name":
            expected_month = int(time_reference["month"])
            matches = prepared.loc[prepared[time_column].dt.month == expected_month]
            label = time_reference["value"]
        else:
            raise ComputeError("Time existence verification requires a supported year or month reference.")

        return TableArtifact(
            name="time_value_exists",
            description=f"Whether {time_column} contains the requested time value.",
            dataframe=pd.DataFrame(
                [
                    {
                        "time_column": time_column,
                        "match_value": label,
                        "exists": bool(not matches.empty),
                        "matching_row_count": int(len(matches)),
                    }
                ]
            ),
        )

    def null_check(
        self,
        dataframe: pd.DataFrame,
        target: str,
        null_expectation: str = "has_nulls",
        filters: dict[str, object] | None = None,
    ) -> TableArtifact:
        """Return whether a column has nulls or is complete."""
        prepared = self._apply_filters(dataframe, filters)
        self._require_columns(prepared, [target])
        null_count = int(prepared[target].isna().sum())
        total_row_count = int(len(prepared))
        non_null_row_count = total_row_count - null_count
        matches = null_count > 0 if null_expectation == "has_nulls" else null_count == 0
        return TableArtifact(
            name="null_check",
            description=f"Whether {target} satisfies the requested null-value condition.",
            dataframe=pd.DataFrame(
                [
                    {
                        "column_name": target,
                        "null_expectation": null_expectation,
                        "matches": bool(matches),
                        "null_row_count": null_count,
                        "non_null_row_count": non_null_row_count,
                        "total_row_count": total_row_count,
                    }
                ]
            ),
        )

    def threshold_check(
        self,
        dataframe: pd.DataFrame,
        target: str,
        threshold_operator: str,
        threshold_value: float | None = None,
        lower_bound: float | None = None,
        upper_bound: float | None = None,
        filters: dict[str, object] | None = None,
    ) -> TableArtifact:
        """Return whether a numeric target satisfies a threshold condition."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [target])
        prepared["_threshold_target"] = pd.to_numeric(prepared[target], errors="coerce")
        prepared = prepared.dropna(subset=["_threshold_target"])
        if prepared.empty:
            raise ComputeError(f"Target column '{target}' has no numeric values for threshold verification.")

        series = prepared["_threshold_target"]
        if threshold_operator == "between":
            if lower_bound is None or upper_bound is None:
                raise ComputeError("Between-threshold verification requires lower and upper bounds.")
            match_mask = series.between(lower_bound, upper_bound, inclusive="both")
        elif threshold_operator == "gt":
            match_mask = series > float(threshold_value)
        elif threshold_operator == "gte":
            match_mask = series >= float(threshold_value)
        elif threshold_operator == "lt":
            match_mask = series < float(threshold_value)
        elif threshold_operator == "lte":
            match_mask = series <= float(threshold_value)
        else:
            raise ComputeError(f"Unsupported threshold operator: {threshold_operator}")

        matching_row_count = int(match_mask.sum())
        total_numeric_row_count = int(len(prepared))
        return TableArtifact(
            name="threshold_check",
            description=f"Whether {target} satisfies the requested threshold condition.",
            dataframe=pd.DataFrame(
                [
                    {
                        "column_name": target,
                        "threshold_operator": threshold_operator,
                        "threshold_value": threshold_value,
                        "lower_bound": lower_bound,
                        "upper_bound": upper_bound,
                        "matches": bool(matching_row_count > 0),
                        "matching_row_count": matching_row_count,
                        "total_numeric_row_count": total_numeric_row_count,
                        "observed_min": float(series.min()),
                        "observed_max": float(series.max()),
                    }
                ]
            ),
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
        bucket: str | None = None,
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Compare grouped totals between adjacent periods."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [target, time_column, *group_by])
        resolved_bucket = bucket or self._bucket_from_time_reference(time_reference)
        prepared = self._prepare_time_bucket_frame(prepared, time_column, resolved_bucket)
        prepared["target_value"] = pd.to_numeric(prepared[target], errors="coerce")
        prepared = prepared.dropna(subset=["target_value"])

        periods = self._resolve_adjacent_periods(prepared, time_reference, resolved_bucket)
        if periods is None:
            return TableArtifact(
                name="grouped_period_comparison",
                description="No comparable grouped periods could be derived from the request.",
                dataframe=pd.DataFrame(columns=[*group_by, "previous_total", "current_total", "delta", "pct_change"]),
            )

        current_period, previous_period = periods
        current_slice = prepared.loc[prepared["_period_bucket"] == current_period]
        previous_slice = prepared.loc[prepared["_period_bucket"] == previous_period]

        aggregation_function = self._aggregation_function(aggregation)
        current_grouped = (
            current_slice.groupby(group_by, as_index=False)["target_value"]
            .agg(aggregation_function)
            .rename(columns={"target_value": "current_total"})
        )
        previous_grouped = (
            previous_slice.groupby(group_by, as_index=False)["target_value"]
            .agg(aggregation_function)
            .rename(columns={"target_value": "previous_total"})
        )

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
            bucket=None,
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
        bucket: str | None = None,
        aggregation: str = "sum",
        filters: dict[str, str] | None = None,
    ) -> TableArtifact:
        """Compare a selected period against the immediately previous comparable period."""
        prepared = self._apply_filters(dataframe, filters).copy()
        self._require_columns(prepared, [target, time_column])
        resolved_bucket = bucket or self._bucket_from_time_reference(time_reference)
        prepared = self._prepare_time_bucket_frame(prepared, time_column, resolved_bucket)
        prepared["target_value"] = pd.to_numeric(prepared[target], errors="coerce")
        prepared = prepared.dropna(subset=["target_value"])

        periods = self._resolve_adjacent_periods(prepared, time_reference, resolved_bucket)
        if periods is None:
            empty = pd.DataFrame(columns=["period", "target_total"])
            return TableArtifact(
                name="period_comparison",
                description="No rows matched the requested period.",
                dataframe=empty,
            )
        current_period, previous_period = periods

        current_total = self._aggregate_series(
            prepared.loc[prepared["_period_bucket"] == current_period, "target_value"],
            aggregation,
        )
        previous_total = self._aggregate_series(
            prepared.loc[prepared["_period_bucket"] == previous_period, "target_value"],
            aggregation,
        )

        comparison = pd.DataFrame(
            {
                "period": [self._format_period_label(previous_period, resolved_bucket), self._format_period_label(current_period, resolved_bucket)],
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
        bucket: str,
    ) -> tuple[pd.Period, pd.Period] | None:
        periods = dataframe["_period_bucket"].dropna().sort_values().unique().tolist()
        if not periods:
            return None

        reference_type = time_reference.get("type")
        current_period: pd.Period | None = None
        if reference_type == "month_name" and bucket == "month":
            requested_month = int(time_reference["month"])
            matching_periods = [period for period in periods if period.month == requested_month]
            if matching_periods:
                current_period = matching_periods[-1]
        elif reference_type == "quarter" and bucket == "quarter":
            requested_quarter = int(time_reference["quarter"])
            matching_periods = [period for period in periods if period.quarter == requested_quarter]
            if matching_periods:
                current_period = matching_periods[-1]
        elif reference_type == "relative_period":
            latest_period = periods[-1]
            value = time_reference.get("value")
            offset = 0 if value in {"this_month", "this_quarter", "this_year"} else 1
            current_candidate = latest_period - offset
            if current_candidate in periods:
                current_period = current_candidate

        if current_period is None:
            return None

        previous_period = current_period - 1
        if previous_period not in periods:
            return None
        return current_period, previous_period

    def _apply_filters(self, dataframe: pd.DataFrame, filters: dict[str, object] | None) -> pd.DataFrame:
        return self._filter_dataframe(dataframe, filters, allow_empty=False)

    def _filter_dataframe(
        self,
        dataframe: pd.DataFrame,
        filters: dict[str, object] | None,
        allow_empty: bool,
    ) -> pd.DataFrame:
        if not filters:
            return dataframe

        prepared = dataframe.copy()
        for column_name, expected_value in filters.items():
            if column_name not in prepared.columns:
                raise ComputeError(f"Filter column '{column_name}' does not exist in the dataset.")
            prepared = self._apply_single_filter(prepared, column_name, expected_value)

        if prepared.empty and not allow_empty:
            raise ComputeError("Filters removed all rows from the dataset.")
        return prepared

    def _apply_single_filter(self, dataframe: pd.DataFrame, column_name: str, expected_value: object) -> pd.DataFrame:
        series = dataframe[column_name]
        if isinstance(expected_value, dict):
            operator = expected_value.get("op")
            if operator == "neq":
                value = expected_value.get("value")
                if pd.api.types.is_string_dtype(series):
                    return dataframe.loc[series.astype(str).str.lower() != str(value).lower()]
                return dataframe.loc[series.astype(str) != str(value)]
            if operator == "year_eq":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                return prepared.loc[prepared[column_name].dt.year == int(expected_value["value"])]
            if operator == "month_eq":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                return prepared.loc[prepared[column_name].dt.month == int(expected_value["value"])]
            if operator == "year_month_eq":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                expected_period = str(expected_value["value"])
                return prepared.loc[prepared[column_name].dt.strftime("%Y-%m") == expected_period]
            if operator == "day_of_month_eq":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                return prepared.loc[prepared[column_name].dt.day == int(expected_value["value"])]
            if operator == "weekday_eq":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                return prepared.loc[prepared[column_name].dt.dayofweek == int(expected_value["value"])]
            if operator == "weekday_in":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                weekday_values = [int(value) for value in expected_value.get("values", [])]
                return prepared.loc[prepared[column_name].dt.dayofweek.isin(weekday_values)]
            if operator == "month_start":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                return prepared.loc[prepared[column_name].dt.is_month_start]
            if operator == "month_end":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                return prepared.loc[prepared[column_name].dt.is_month_end]
            if operator == "quarter_eq":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                return prepared.loc[prepared[column_name].dt.quarter == int(expected_value["value"])]
            if operator == "recent_window":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                datetime_series = prepared[column_name].dropna()
                if datetime_series.empty:
                    return prepared.iloc[0:0]
                anchor = datetime_series.max()
                window_value = int(expected_value["value"])
                window_unit = str(expected_value["unit"])
                if window_unit == "day":
                    start = anchor - pd.Timedelta(days=window_value)
                elif window_unit == "week":
                    start = anchor - pd.Timedelta(weeks=window_value)
                elif window_unit == "month":
                    start = anchor - pd.DateOffset(months=window_value)
                else:  # pragma: no cover
                    raise ComputeError(f"Unsupported recent window unit: {window_unit}")
                return prepared.loc[(prepared[column_name] >= start) & (prepared[column_name] <= anchor)]
            if operator == "nth_weekday_of_month":
                prepared = dataframe.copy()
                prepared[column_name] = pd.to_datetime(prepared[column_name], errors="coerce")
                weekday = int(expected_value["weekday"])
                occurrence = expected_value["occurrence"]
                weekday_mask = prepared[column_name].dt.dayofweek == weekday
                if occurrence == "last":
                    next_week = prepared[column_name] + pd.Timedelta(days=7)
                    month_mask = next_week.dt.month != prepared[column_name].dt.month
                    return prepared.loc[weekday_mask & month_mask]
                occurrence_value = int(occurrence)
                occurrence_mask = ((prepared[column_name].dt.day - 1) // 7 + 1) == occurrence_value
                return prepared.loc[weekday_mask & occurrence_mask]
            raise ComputeError(f"Unsupported filter operator: {operator}")

        if pd.api.types.is_string_dtype(series):
            return dataframe.loc[series.astype(str).str.lower() == str(expected_value).lower()]
        return dataframe.loc[series.astype(str) == str(expected_value)]

    def _sort_dataframe(self, dataframe: pd.DataFrame, sort_by: str, sort_direction: str) -> pd.DataFrame:
        ascending = sort_direction != "desc"
        return dataframe.sort_values(sort_by, ascending=ascending, kind="stable")

    def _paginate_frame(
        self,
        dataframe: pd.DataFrame,
        page: int,
        page_size: int,
    ) -> tuple[pd.DataFrame, dict[str, int | bool | None]]:
        total_rows = int(len(dataframe))
        safe_page = page if page > 0 else 1
        safe_page_size = page_size if page_size > 0 else 50
        offset = (safe_page - 1) * safe_page_size
        page_frame = dataframe.iloc[offset : offset + safe_page_size].copy()
        returned_rows = int(len(page_frame))
        pagination = {
            "page": safe_page,
            "page_size": safe_page_size,
            "total_rows": total_rows,
            "returned_rows": returned_rows,
            "has_next_page": bool(offset + safe_page_size < total_rows),
            "has_previous_page": bool(safe_page > 1 and total_rows > 0),
            "offset": offset,
            "next_page_token": None,
        }
        return page_frame, pagination

    def _require_columns(self, dataframe: pd.DataFrame, column_names: list[str]) -> None:
        missing_columns = [column_name for column_name in column_names if column_name not in dataframe.columns]
        if missing_columns:
            joined = ", ".join(missing_columns)
            raise ComputeError(f"Required columns are missing from the dataset: {joined}")

    def _aggregation_expression(self, aggregation: str) -> str:
        if aggregation not in self.AGGREGATION_EXPRESSIONS:
            raise ComputeError(f"Unsupported aggregation: {aggregation}")
        return self.AGGREGATION_EXPRESSIONS[aggregation]

    def _aggregation_function(self, aggregation: str) -> str:
        mapping = {
            "sum": "sum",
            "mean": "mean",
            "max": "max",
            "min": "min",
            "count": "count",
        }
        if aggregation not in mapping:
            raise ComputeError(f"Unsupported aggregation: {aggregation}")
        return mapping[aggregation]

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

    def _prepare_time_bucket_frame(
        self,
        dataframe: pd.DataFrame,
        time_column: str,
        bucket: str,
    ) -> pd.DataFrame:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            prepared = dataframe.copy()
            prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column])

        if bucket == "month":
            periods = prepared[time_column].dt.to_period("M")
        elif bucket == "quarter":
            periods = prepared[time_column].dt.to_period("Q")
        elif bucket == "year":
            periods = prepared[time_column].dt.to_period("Y")
        else:
            raise ComputeError(f"Unsupported time bucket: {bucket}")

        prepared["_period_bucket"] = periods
        if bucket == "year":
            prepared[self._bucket_label_column(bucket)] = periods.map(lambda period: period.year)
        else:
            prepared[self._bucket_label_column(bucket)] = periods.map(lambda period: self._format_period_label(period, bucket))
        return prepared

    def _bucket_label_column(self, bucket: str) -> str:
        return {
            "month": "month",
            "quarter": "quarter",
            "year": "year",
        }[bucket]

    def _bucket_from_time_reference(self, time_reference: dict[str, str]) -> str:
        reference_type = time_reference.get("type")
        if reference_type == "month_name":
            return "month"
        if reference_type == "quarter":
            return "quarter"
        if reference_type == "relative_period":
            value = time_reference.get("value", "")
            if value.endswith("month"):
                return "month"
            if value.endswith("quarter"):
                return "quarter"
            if value.endswith("year"):
                return "year"
        raise ComputeError("Time comparison requires a supported month, quarter, or year reference.")

    def _format_period_label(self, period: pd.Period, bucket: str) -> str:
        if bucket == "month":
            return str(period)
        if bucket == "quarter":
            return f"{period.year}-Q{period.quarter}"
        if bucket == "year":
            return str(period.year)
        raise ComputeError(f"Unsupported time bucket: {bucket}")


DuckDBComputeEngine = DuckDBAdapter
