"""Human-readable summary formatting for computed outputs."""

from __future__ import annotations

import pandas as pd

from saida.core.contracts import AnalysisPlan, AnalysisRequest, DatasetProfile, Metric, SourceContext, TableArtifact


class SummaryFormatter:
    """Build a grounded summary from computed outputs."""

    def summarize(
        self,
        plan: AnalysisPlan,
        metrics: list[Metric],
        tables: list[TableArtifact],
        warnings: list[str],
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None = None,
    ) -> str:
        """Generate a deterministic summary grounded in computed outputs."""
        target_label = request.target.replace("_", " ") if request.target else "the dataset"
        parts = [f"Completed a {plan.task_type} analysis for {target_label} on {profile.dataset_name}."]
        direct_aggregate_summary = bool(plan.task_type == "descriptive" and request.aggregation)

        row_count = self._metric_value(metrics, "row_count")
        if row_count is not None and request.intent_name != "row_count":
            parts.append(f"The dataset contains {row_count} rows.")

        metadata_part = self._describe_metadata_inventory(tables, request)
        if metadata_part:
            parts.append(metadata_part)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        row_count_part = self._describe_row_count_only(metrics, request)
        if row_count_part:
            parts.append(row_count_part)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        time_coverage_part = self._describe_time_coverage(tables, request)
        if time_coverage_part:
            parts.append(time_coverage_part)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        time_bucket_count_part = self._describe_time_bucket_counts(tables, request)
        if time_bucket_count_part:
            parts.append(time_bucket_count_part)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        time_bucket_breakdown_part = self._describe_time_bucket_breakdown(tables, request)
        if time_bucket_breakdown_part:
            parts.append(time_bucket_breakdown_part)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        existence_part = self._describe_existence_check(tables, request)
        if existence_part:
            parts.append(existence_part)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        statistical_part = self._describe_statistical_result(tables)
        if statistical_part:
            parts.append(statistical_part)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        representation_part = self._describe_representation_ranking(tables, request)
        if representation_part:
            parts.append(representation_part)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        ranked_rows_part = self._describe_ranked_rows(tables, request)
        if ranked_rows_part:
            parts.append(ranked_rows_part)
            context_note = self._describe_context_note(context)
            if context_note:
                parts.append(context_note)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        ranked_groups_part = self._describe_ranked_groups(tables, request)
        if ranked_groups_part:
            parts.append(ranked_groups_part)
            context_note = self._describe_context_note(context)
            if context_note:
                parts.append(context_note)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        distinct_values_part = self._describe_distinct_values(tables, request)
        if distinct_values_part:
            parts.append(distinct_values_part)
            context_note = self._describe_context_note(context)
            if context_note:
                parts.append(context_note)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        grouped_aggregate_part = self._describe_grouped_aggregation(tables, request)
        if grouped_aggregate_part:
            parts.append(grouped_aggregate_part)

        aggregate_part = self._describe_requested_aggregation(metrics, request)
        if aggregate_part and not grouped_aggregate_part:
            parts.append(aggregate_part)

        if direct_aggregate_summary:
            context_note = self._describe_context_note(context)
            if context_note:
                parts.append(context_note)
            if warnings:
                parts.append(f"Warnings: {'; '.join(warnings)}.")
            return " ".join(parts)

        target_metric = next((metric for metric in metrics if metric.name.endswith("_sum")), None)
        if target_metric is not None and request.aggregation != "sum":
            label = target_metric.name.replace("_sum", "").replace("_", " ").title()
            parts.append(f"{label} total is {target_metric.value:.2f}.")

        period_table = self._table(tables, "period_comparison")
        if period_table is not None and len(period_table.dataframe) >= 2:
            parts.append(self._describe_period_comparison(period_table.dataframe, request.target))
        else:
            trend_table = self._table(tables, "time_trend")
            if trend_table is not None and not trend_table.dataframe.empty:
                parts.append(self._describe_latest_trend_point(trend_table.dataframe, request.target))

        ranked_table = self._table(tables, "ranked_breakdown")
        if ranked_table is not None and not ranked_table.dataframe.empty:
            parts.append(self._describe_ranked_contributor(ranked_table.dataframe.iloc[0], request.target))

        contribution_table = self._table(tables, "contribution_breakdown")
        if contribution_table is not None and not contribution_table.dataframe.empty:
            contribution_part = self._describe_contribution_breakdown(contribution_table.dataframe, request.target)
            if contribution_part:
                parts.append(contribution_part)

        mover_table = self._table(tables, "top_movers")
        if mover_table is not None and not mover_table.dataframe.empty:
            parts.append(self._describe_top_mover(mover_table.dataframe.iloc[0], request.target))

        diagnostics_table = self._table(tables, "time_series_diagnostics")
        if diagnostics_table is not None and not diagnostics_table.dataframe.empty:
            parts.append(self._describe_time_series_diagnostics(diagnostics_table.dataframe.iloc[0], request.target))

        anomaly_table = self._table(tables, "anomaly_summary")
        if anomaly_table is not None:
            anomaly_count = len(anomaly_table.dataframe)
            parts.append(f"Detected {anomaly_count} anomaly candidate{'s' if anomaly_count != 1 else ''}.")

        context_note = self._describe_context_note(context)
        if context_note:
            parts.append(context_note)

        if warnings:
            parts.append(f"Warnings: {'; '.join(warnings)}.")

        return " ".join(parts)

    def _metric_value(self, metrics: list[Metric], name: str) -> object | None:
        metric = next((item for item in metrics if item.name == name), None)
        if metric is None:
            return None
        return metric.value

    def _table(self, tables: list[TableArtifact], name: str) -> TableArtifact | None:
        return next((table for table in tables if table.name == name), None)

    def _describe_period_comparison(self, dataframe: pd.DataFrame, target: str | None) -> str:
        previous_row = dataframe.iloc[0]
        current_row = dataframe.iloc[-1]
        delta = float(current_row.get("delta", 0.0) or 0.0)
        previous_total = float(previous_row.get("target_total", 0.0) or 0.0)
        current_total = float(current_row.get("target_total", 0.0) or 0.0)
        pct_change = (delta / previous_total) if previous_total else 0.0
        label = target.replace("_", " ") if target else "value"

        return (
            f"{label.title()} moved from {previous_total:.2f} in {previous_row['period']} "
            f"to {current_total:.2f} in {current_row['period']} ({pct_change:+.1%})."
        )

    def _describe_requested_aggregation(self, metrics: list[Metric], request: AnalysisRequest) -> str | None:
        if not request.target or not request.aggregation:
            return None
        metric_name = f"{request.target}_{request.aggregation}"
        metric_value = self._metric_value(metrics, metric_name)
        if metric_value is None:
            return None

        label = request.target.replace("_", " ")
        if request.aggregation == "mean":
            return f"Average {label} is {float(metric_value):.2f}."
        if request.aggregation == "max":
            return f"Highest {label} is {float(metric_value):.2f}."
        if request.aggregation == "min":
            return f"Lowest {label} is {float(metric_value):.2f}."
        if request.aggregation == "sum":
            return f"Total {label} is {float(metric_value):.2f}."
        if request.aggregation == "count":
            return f"Count of {label} is {int(metric_value)}."
        return None

    def _describe_distinct_values(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if not request.options.get("distinct_values") or not request.target:
            return None
        distinct_table = self._table(tables, "distinct_values")
        if distinct_table is None or distinct_table.dataframe.empty:
            return None

        value_column = request.target
        values = [str(value) for value in distinct_table.dataframe[value_column].head(10).tolist()]
        if not values:
            return None

        label = request.target.replace("_", " ")
        summary = f"Available {label} values: {', '.join(values)}."
        remaining_values = len(distinct_table.dataframe) - len(values)
        if remaining_values > 0:
            summary += f" {remaining_values} more value{'s' if remaining_values != 1 else ''} are available in distinct_values."
        return summary

    def _describe_representation_ranking(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if request.intent_name != "representation_ranking" or not request.target:
            return None
        count_table = self._table(tables, "group_row_counts")
        if count_table is None or count_table.dataframe.empty:
            return None
        row = count_table.dataframe.iloc[0]
        row_label = self._row_label(row, exclude={"row_count"})
        row_count = int(row.get("row_count", 0) or 0)
        if request.options.get("ranking_direction") == "asc":
            return f"The least represented {request.target.replace('_', ' ')} is {row_label} with {row_count} rows."
        return f"The most represented {request.target.replace('_', ' ')} is {row_label} with {row_count} rows."

    def _describe_ranked_rows(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if request.intent_name != "row_ranking" or not request.target:
            return None
        ranked_rows = self._table(tables, "ranked_rows")
        if ranked_rows is None or ranked_rows.dataframe.empty:
            return None
        limit = int(request.options.get("ranking_limit", len(ranked_rows.dataframe)))
        direction = "Bottom" if request.options.get("ranking_direction") == "asc" else "Top"
        label = request.target.replace("_", " ")
        entries: list[str] = []
        for _, row in ranked_rows.dataframe.head(limit).iterrows():
            rank = int(row.get("rank", len(entries) + 1))
            value = float(row.get(request.target, 0.0) or 0.0)
            row_label = self._row_label(row, exclude={"rank", request.target})
            if row_label and row_label != "the leading group":
                entries.append(f"#{rank} {value:.2f} ({row_label})")
            else:
                entries.append(f"#{rank} {value:.2f}")
        return f"{direction} {min(limit, len(ranked_rows.dataframe))} {label} values: {'; '.join(entries)}."

    def _describe_ranked_groups(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if request.intent_name != "group_ranking" or not request.target:
            return None
        ranked_groups = self._table(tables, "ranked_breakdown")
        if ranked_groups is None or ranked_groups.dataframe.empty:
            return None
        limit = int(request.options.get("ranking_limit", len(ranked_groups.dataframe)))
        direction = "Bottom" if request.options.get("ranking_direction") == "asc" else "Top"
        label = request.target.replace("_", " ")
        entries: list[str] = []
        for _, row in ranked_groups.dataframe.head(limit).iterrows():
            rank = int(row.get("rank", len(entries) + 1))
            value = float(row.get("target_total", 0.0) or 0.0)
            row_label = self._row_label(row, exclude={"rank", "target_total"})
            entries.append(f"#{rank} {row_label} = {value:.2f}")
        return f"{direction} {min(limit, len(ranked_groups.dataframe))} {label} groups: {'; '.join(entries)}."

    def _describe_row_count_only(self, metrics: list[Metric], request: AnalysisRequest) -> str | None:
        if request.intent_name != "row_count":
            return None
        row_count = self._metric_value(metrics, "row_count")
        if row_count is None:
            return None
        return f"The dataset contains {int(row_count)} rows."

    def _describe_metadata_inventory(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        inventory_mapping = {
            "column_inventory": ("column_inventory", "column_name", "Available columns"),
            "numeric_column_inventory": ("numeric_column_inventory", "column_name", "Numeric columns"),
            "categorical_column_inventory": ("categorical_column_inventory", "column_name", "Categorical columns"),
            "measure_inventory": ("measure_inventory", "measure_column", "Available measure columns"),
            "dimension_inventory": ("dimension_inventory", "dimension_column", "Available dimension columns"),
            "time_column_inventory": ("time_column_inventory", "time_column", "Available time columns"),
        }
        if request.intent_name == "column_type_inventory":
            inventory_table = self._table(tables, "column_type_inventory")
            if inventory_table is None or inventory_table.dataframe.empty:
                return "No column type information is available."
            entries = []
            for _, row in inventory_table.dataframe.iterrows():
                nullable_label = "nullable" if bool(row.get("nullable")) else "non-null"
                entries.append(f"{row['column_name']} ({row['dtype']}, {nullable_label})")
            return f"Column types: {'; '.join(entries)}."
        if request.intent_name == "missing_value_inventory":
            inventory_table = self._table(tables, "missing_value_inventory")
            if inventory_table is None:
                return None
            if inventory_table.dataframe.empty:
                return "No columns with missing values were detected."
            entries = []
            for _, row in inventory_table.dataframe.iterrows():
                entries.append(f"{row['column_name']} ({int(row['null_count'])} nulls, {float(row['null_ratio']):.1%})")
            return f"Columns with missing values: {'; '.join(entries)}."
        if request.intent_name == "identifier_inventory":
            inventory_table = self._table(tables, "identifier_inventory")
            if inventory_table is None:
                return None
            if inventory_table.dataframe.empty:
                return "No likely identifier columns were detected."
            values = [str(value) for value in inventory_table.dataframe["column_name"].tolist()]
            return f"Likely identifier columns: {', '.join(values)}."
        if request.intent_name == "high_cardinality_inventory":
            inventory_table = self._table(tables, "high_cardinality_inventory")
            if inventory_table is None:
                return None
            if inventory_table.dataframe.empty:
                return "No high-cardinality columns were detected."
            entries = []
            for _, row in inventory_table.dataframe.iterrows():
                entries.append(f"{row['column_name']} ({int(row['unique_count'])} unique, {float(row['distinct_ratio']):.1%} distinct)")
            return f"High-cardinality columns: {'; '.join(entries)}."
        if request.intent_name not in inventory_mapping:
            return None
        table_name, column_name, prefix = inventory_mapping[request.intent_name]
        inventory_table = self._table(tables, table_name)
        if inventory_table is None or inventory_table.dataframe.empty:
            return f"{prefix}: none."
        values = [str(value) for value in inventory_table.dataframe[column_name].tolist()]
        return f"{prefix}: {', '.join(values)}."

    def _describe_time_coverage(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if request.intent_name != "time_coverage":
            return None
        coverage_table = self._table(tables, "time_coverage")
        if coverage_table is None:
            return None
        mode = request.options.get("time_coverage_mode", "years_present")
        dataframe = coverage_table.dataframe
        if mode == "years_present":
            years = [str(value) for value in dataframe.get("year", pd.Series(dtype="int64")).tolist()]
            if not years:
                return "No valid years were detected in the dataset."
            return f"The data contains records for these years: {', '.join(years)}."
        if mode == "months_present":
            months = [str(value) for value in dataframe.get("month", pd.Series(dtype="object")).tolist()]
            if not months:
                return "No valid months were detected in the dataset."
            return f"The data contains records for these months: {', '.join(months)}."
        if mode == "date_range":
            if dataframe.empty:
                return "No valid dates were detected in the dataset."
            row = dataframe.iloc[0]
            return f"The data covers {row['earliest_date']} to {row['latest_date']}."
        return None

    def _describe_time_bucket_counts(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if request.intent_name != "time_bucket_counts":
            return None
        count_table = self._table(tables, "time_bucket_counts")
        if count_table is None or count_table.dataframe.empty:
            return None

        bucket = request.options.get("time_bucket", "year")
        bucket_column = {"month": "month", "quarter": "quarter"}.get(str(bucket), "year")
        entries = [
            f"{row[bucket_column]} = {int(row['row_count'])}"
            for _, row in count_table.dataframe.iterrows()
        ]
        if bucket == "month":
            return f"Ticket counts by month: {'; '.join(entries)}."
        if bucket == "quarter":
            return f"Ticket counts by quarter: {'; '.join(entries)}."
        return f"Ticket counts by year: {'; '.join(entries)}."

    def _describe_time_bucket_breakdown(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if request.intent_name != "time_bucket_breakdown" or not request.target:
            return None
        breakdown_table = self._table(tables, "time_bucket_breakdown")
        if breakdown_table is None or breakdown_table.dataframe.empty:
            return None

        bucket = request.options.get("time_bucket", "month")
        bucket_column = {"month": "month", "quarter": "quarter"}.get(str(bucket), "year")
        label = request.target.replace("_", " ")
        entries: list[str] = []
        for _, row in breakdown_table.dataframe.head(8).iterrows():
            row_label = self._row_label(row, exclude={"target_total"})
            entries.append(f"{row_label} = {float(row['target_total']):.2f}")

        if not entries:
            return None
        return f"{label.title()} by {bucket_column}: {'; '.join(entries)}."

    def _describe_existence_check(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if request.intent_name != "existence_check":
            return None
        existence_mode = request.options.get("existence_mode", "filtered_rows")
        if existence_mode == "time_value":
            table = self._table(tables, "time_value_exists")
            if table is None or table.dataframe.empty:
                return None
            row = table.dataframe.iloc[0]
            time_column = str(row.get("time_column", request.target or "the time column"))
            match_value = str(row.get("match_value", "the requested value"))
            matching_row_count = int(row.get("matching_row_count", 0) or 0)
            if bool(row.get("exists")):
                return f"Yes, {time_column} contains dates in {match_value} ({matching_row_count} matching rows)."
            return f"No, {time_column} does not contain dates in {match_value}."
        if existence_mode == "null_check":
            table = self._table(tables, "null_check")
            if table is None or table.dataframe.empty:
                return None
            row = table.dataframe.iloc[0]
            column_name = str(row.get("column_name", request.target or "the requested column"))
            null_row_count = int(row.get("null_row_count", 0) or 0)
            total_row_count = int(row.get("total_row_count", 0) or 0)
            if row.get("null_expectation") == "no_nulls":
                if bool(row.get("matches")):
                    return f"Yes, {column_name} is complete with no missing values."
                return f"No, {column_name} is not complete ({null_row_count} null rows out of {total_row_count})."
            if bool(row.get("matches")):
                return f"Yes, {column_name} has missing values ({null_row_count} null rows out of {total_row_count})."
            return f"No, {column_name} does not have missing values."
        if existence_mode == "threshold_check":
            table = self._table(tables, "threshold_check")
            if table is None or table.dataframe.empty:
                return None
            row = table.dataframe.iloc[0]
            column_name = str(row.get("column_name", request.target or "the requested column"))
            condition_text = self._threshold_condition_text(row)
            matching_row_count = int(row.get("matching_row_count", 0) or 0)
            total_numeric_row_count = int(row.get("total_numeric_row_count", 0) or 0)
            if bool(row.get("matches")):
                return (
                    f"Yes, {column_name} contains values {condition_text} "
                    f"({matching_row_count} matching rows out of {total_numeric_row_count})."
                )
            return f"No, {column_name} does not contain values {condition_text}."
        if existence_mode == "column_property_check":
            table = self._table(tables, "column_property_check")
            if table is None or table.dataframe.empty:
                return None
            row = table.dataframe.iloc[0]
            column_name = str(row.get("column_name", request.target or "the requested column"))
            expected_property = str(row.get("expected_property", request.options.get("expected_property", "requested")))
            if bool(row.get("matches")):
                if expected_property == "identifier":
                    return f"Yes, {column_name} is likely an identifier."
                article = "an" if expected_property[:1] in {"a", "e", "i", "o", "u"} else "a"
                return f"Yes, {column_name} is {article} {expected_property} column."
            if expected_property == "identifier":
                return f"No, {column_name} is not marked as an identifier."
            actual_dtype = str(row.get("dtype", "unknown"))
            return f"No, {column_name} is not a {expected_property} column; detected type is {actual_dtype}."

        table = self._table(tables, "row_existence")
        if table is None or table.dataframe.empty:
            return None
        row = table.dataframe.iloc[0]
        filter_parts = [self._format_filter_condition(column, value) for column, value in (request.filters or {}).items()]
        filter_text = ", ".join(filter_parts) if filter_parts else "the requested conditions"
        matching_row_count = int(row.get("matching_row_count", 0) or 0)
        if bool(row.get("exists")):
            return f"Yes, the dataset contains rows matching {filter_text} ({matching_row_count} rows)."
        return f"No, the dataset does not contain rows matching {filter_text}."

    def _threshold_condition_text(self, row: pd.Series) -> str:
        operator = str(row.get("threshold_operator", ""))
        if operator == "between":
            return f"between {float(row['lower_bound']):.2f} and {float(row['upper_bound']):.2f}"
        threshold_value = float(row.get("threshold_value", 0.0) or 0.0)
        labels = {
            "gt": f"above {threshold_value:.2f}",
            "gte": f"at least {threshold_value:.2f}",
            "lt": f"below {threshold_value:.2f}",
            "lte": f"at most {threshold_value:.2f}",
        }
        return labels.get(operator, f"matching the threshold {threshold_value:.2f}")

    def _format_filter_condition(self, column: str, value: object) -> str:
        if isinstance(value, dict):
            operator = value.get("op")
            if operator == "neq":
                return f"{column}!={value.get('value')}"
            if operator == "year_eq":
                return f"year({column})={value.get('value')}"
            if operator == "month_eq":
                label = value.get("label") or value.get("value")
                return f"month({column})={label}"
        return f"{column}={value}"

    def _describe_statistical_result(self, tables: list[TableArtifact]) -> str | None:
        statistical_tables = {
            "t_test",
            "chi_square_test",
            "anova_test",
            "mann_whitney_test",
            "confidence_interval",
            "regression_significance",
            "significance_test",
            "power_analysis",
            "sample_size_estimate",
        }
        statistical_table = next((table for table in tables if table.name in statistical_tables), None)
        if statistical_table is None or statistical_table.dataframe.empty:
            return None

        row = statistical_table.dataframe.iloc[0]
        if statistical_table.name in {"t_test", "significance_test"} and row.get("test_name") == "welch_t_test":
            conclusion = "statistically significant" if bool(row.get("is_significant")) else "not statistically significant"
            return (
                f"Welch t-test for {row['target']} by {row['group_column']} compared {row['left_group']} and {row['right_group']}: "
                f"p={float(row['p_value']):.4f}, which is {conclusion} at alpha={float(row['alpha']):.2f}."
            )
        if statistical_table.name in {"anova_test", "significance_test"} and row.get("test_name") == "anova":
            conclusion = "statistically significant" if bool(row.get("is_significant")) else "not statistically significant"
            return (
                f"ANOVA for {row['target']} by {row['group_column']} returned p={float(row['p_value']):.4f}, "
                f"which is {conclusion} at alpha={float(row['alpha']):.2f}."
            )
        if statistical_table.name == "chi_square_test":
            conclusion = "statistically significant" if bool(row.get("is_significant")) else "not statistically significant"
            return (
                f"Chi-square test for {row['left_column']} and {row['right_column']} returned p={float(row['p_value']):.4f}, "
                f"which is {conclusion} at alpha={float(row['alpha']):.2f}."
            )
        if statistical_table.name == "mann_whitney_test":
            conclusion = "statistically significant" if bool(row.get("is_significant")) else "not statistically significant"
            return (
                f"Mann-Whitney test for {row['target']} by {row['group_column']} returned p={float(row['p_value']):.4f}, "
                f"which is {conclusion} at alpha={float(row['alpha']):.2f}."
            )
        if statistical_table.name == "confidence_interval":
            return (
                f"The {float(row['confidence_level']):.0%} confidence interval for {row['target']} is "
                f"[{float(row['lower_bound']):.2f}, {float(row['upper_bound']):.2f}] around a sample mean of {float(row['sample_mean']):.2f}."
            )
        if statistical_table.name == "regression_significance":
            significant_rows = statistical_table.dataframe.loc[statistical_table.dataframe["is_significant"] == True]
            predictors = [str(value) for value in significant_rows["parameter"].tolist() if value != "const"]
            if predictors:
                return f"Regression significance identified these significant predictors: {', '.join(predictors)}."
            return "Regression significance did not identify any statistically significant predictors beyond the intercept."
        if statistical_table.name == "power_analysis":
            return (
                f"Observed power for {row['target']} by {row['group_column']} is {float(row['power']):.2f} "
                f"with effect size {float(row['effect_size']):.2f}."
            )
        if statistical_table.name == "sample_size_estimate":
            return (
                f"Estimated sample size per group for {row['target']} by {row['group_column']} is "
                f"{float(row['required_sample_size_per_group']):.1f} at alpha={float(row['alpha']):.2f} and power={float(row['desired_power']):.2f}."
            )
        return None

    def _describe_grouped_aggregation(self, tables: list[TableArtifact], request: AnalysisRequest) -> str | None:
        if not request.target or not request.group_by or not request.aggregation:
            return None

        group_breakdown = self._table(tables, "group_breakdown")
        if group_breakdown is None or group_breakdown.dataframe.empty:
            return None

        label = request.target.replace("_", " ")
        dimension_label = ", ".join(request.group_by)
        prefix = self._aggregation_prefix(request.aggregation, label, dimension_label)
        if prefix is None:
            return None

        rows = group_breakdown.dataframe.head(5)
        entries: list[str] = []
        for _, row in rows.iterrows():
            row_label = self._row_label(row, exclude={"target_total"})
            if not row_label:
                continue
            value = float(row.get("target_total", 0.0) or 0.0)
            entries.append(f"{row_label} = {value:.2f}")

        if not entries:
            return None

        grouped_summary = f"{prefix}: {'; '.join(entries)}."
        remaining_rows = len(group_breakdown.dataframe) - len(rows)
        if remaining_rows > 0:
            grouped_summary += f" {remaining_rows} more group{'s' if remaining_rows != 1 else ''} are available in group_breakdown."
        return grouped_summary

    def _aggregation_prefix(self, aggregation: str, label: str, dimension_label: str) -> str | None:
        if aggregation == "sum":
            return f"Total {label} by {dimension_label}"
        if aggregation == "mean":
            return f"Average {label} by {dimension_label}"
        if aggregation == "max":
            return f"Highest {label} by {dimension_label}"
        if aggregation == "min":
            return f"Lowest {label} by {dimension_label}"
        if aggregation == "count":
            return f"Count of {label} by {dimension_label}"
        return None

    def _describe_latest_trend_point(self, dataframe: pd.DataFrame, target: str | None) -> str:
        latest_row = dataframe.iloc[-1]
        target_total = float(latest_row.get("target_total", 0.0) or 0.0)
        period = latest_row.get("period_month", "the latest period")
        delta = latest_row.get("period_delta")
        label = target.replace("_", " ") if target else "value"
        if pd.notna(delta):
            return f"The latest period is {period} with {label} at {target_total:.2f} and a period change of {float(delta):+.2f}."
        return f"The latest period is {period} with {label} at {target_total:.2f}."

    def _describe_ranked_contributor(self, row: pd.Series, target: str | None) -> str:
        group_label = self._row_label(row, exclude={"rank", "target_total"})
        target_total = float(row.get("target_total", 0.0) or 0.0)
        label = target.replace("_", " ") if target else "value"
        return f"Top contributor was {group_label} with {label} total of {target_total:.2f}."

    def _describe_contribution_breakdown(self, dataframe: pd.DataFrame, target: str | None) -> str | None:
        label = target.replace("_", " ") if target else "value"
        if "delta" in dataframe.columns:
            strongest_drop = dataframe.sort_values("delta").iloc[0]
            group_label = self._row_label(strongest_drop, exclude={"previous_total", "current_total", "delta", "share_of_total"})
            delta = float(strongest_drop.get("delta", 0.0) or 0.0)
            return f"Largest contribution change came from {group_label} at {delta:+.2f} {label}."
        if "share_of_total" in dataframe.columns:
            top_share = dataframe.sort_values("share_of_total", ascending=False).iloc[0]
            group_label = self._row_label(top_share, exclude={"target_total", "share_of_total"})
            share = float(top_share.get("share_of_total", 0.0) or 0.0)
            return f"Largest share of total {label} came from {group_label} at {share:.1%}."
        return None

    def _describe_top_mover(self, row: pd.Series, target: str | None) -> str:
        group_label = self._row_label(row, exclude={"rank", "previous_total", "current_total", "delta", "pct_change", "abs_delta"})
        delta = float(row.get("delta", 0.0) or 0.0)
        pct_change = float(row.get("pct_change", 0.0) or 0.0)
        label = target.replace("_", " ") if target else "value"
        return f"Top mover was {group_label} with a {delta:+.2f} change in {label} ({pct_change:+.1%})."

    def _describe_time_series_diagnostics(self, row: pd.Series, target: str | None) -> str:
        label = target.replace("_", " ") if target else "value"
        first_period = row.get("first_period")
        last_period = row.get("last_period")
        net_change = float(row.get("net_change", 0.0) or 0.0)
        volatility = float(row.get("change_volatility", 0.0) or 0.0)
        return (
            f"Across {first_period} to {last_period}, {label} changed by {net_change:+.2f} "
            f"with period-to-period volatility of {volatility:.2f}."
        )

    def _describe_context_note(self, context: SourceContext | None) -> str | None:
        if context is None:
            return None
        if context.caveats:
            return f"Context caveat: {context.caveats[0]}."
        if context.freshness_notes:
            return f"Context freshness note: {context.freshness_notes[0]}."
        return None

    def _row_label(self, row: pd.Series, exclude: set[str]) -> str:
        parts: list[str] = []
        for key, value in row.items():
            if key in exclude:
                continue
            if pd.isna(value):
                continue
            parts.append(f"{key}={value}")
        return ", ".join(parts) if parts else "the leading group"


ResultSummarizer = SummaryFormatter
