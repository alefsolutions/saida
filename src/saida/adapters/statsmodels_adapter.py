"""Statsmodels-backed statistical adapter."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from saida.adapters.interfaces import ComputeInterface, ComputeRequest, ComputeResponse
from saida.core.artifacts import artifact_from_value
try:  # pragma: no cover - exercised indirectly in environments with statsmodels
    import statsmodels.api as sm
except Exception:  # pragma: no cover - graceful fallback path
    sm = None

try:  # pragma: no cover - exercised indirectly in environments with statsmodels
    from statsmodels.stats.power import TTestIndPower
except Exception:  # pragma: no cover - graceful fallback path
    TTestIndPower = None

from saida.exceptions import ComputeError
from saida.core.contracts import TableArtifact


class StatsModelsAdapter(ComputeInterface):
    """Run statistical routines over a pandas DataFrame."""

    DEFAULT_ALPHA = 0.05
    DEFAULT_CONFIDENCE_LEVEL = 0.95
    DEFAULT_POWER = 0.80
    STATISTICAL_TEST_METHODS = {
        "t_test",
        "chi_square",
        "anova",
        "mann_whitney",
        "confidence_interval",
        "regression_significance",
        "significance_inference",
        "power_analysis",
        "sample_size_estimate",
    }
    SUPPORTED_METHODS = (
        "missingness_summary",
        "numeric_summary",
        "distribution_summary",
        "target_correlation",
        "anomaly_summary",
        "time_series_diagnostics",
        "group_mean_comparison",
        "t_test",
        "chi_square",
        "anova",
        "mann_whitney",
        "confidence_interval",
        "regression_significance",
        "significance_inference",
        "power_analysis",
        "sample_size_estimate",
    )

    @property
    def tool_family(self) -> str:
        return "stats"

    def supported_methods(self) -> tuple[str, ...]:
        return self.SUPPORTED_METHODS

    def execute(self, request: ComputeRequest) -> ComputeResponse:
        dataframe = self._resolve_dataframe(request)
        parameters = request.parameters
        method_id = request.method_id

        if method_id == "missingness_summary":
            return self._table_response(self.missingness_summary(dataframe), request, logical_shape="table")
        if method_id == "numeric_summary":
            return self._table_response(self.numeric_summary(dataframe), request, logical_shape="table")
        if method_id == "distribution_summary":
            distribution_table = self.distribution_summary(dataframe, parameters["target"])
            return self._optional_table_response(distribution_table, request, logical_shape="table")
        if method_id == "target_correlation":
            correlation_table = self.correlation_matrix(dataframe, parameters.get("target"))
            return self._optional_table_response(correlation_table, request, logical_shape="table")
        if method_id == "anomaly_summary":
            anomaly_table = self.anomaly_summary(dataframe, parameters["target"], parameters.get("time_column"))
            return self._optional_table_response(anomaly_table, request, logical_shape="table")
        if method_id == "time_series_diagnostics":
            diagnostics_table = self.time_series_diagnostics(dataframe, parameters["target"], parameters["time_column"])
            return self._optional_table_response(diagnostics_table, request, logical_shape="table")
        if method_id == "group_mean_comparison":
            comparison_table = self.group_mean_comparison(dataframe, parameters["target"], parameters["group_column"])
            return self._optional_table_response(comparison_table, request, logical_shape="table")
        if method_id == "t_test":
            return self._table_response(
                self.t_test(dataframe, parameters["target"], parameters["group_by"][0], parameters.get("alpha", 0.05)),
                request,
                logical_shape="statistical_test",
            )
        if method_id == "chi_square":
            comparison_columns = parameters.get("comparison_columns", [])
            return self._table_response(
                self.chi_square_test(dataframe, comparison_columns[0], comparison_columns[1], parameters.get("alpha", 0.05)),
                request,
                logical_shape="statistical_test",
            )
        if method_id == "anova":
            return self._table_response(
                self.anova_test(dataframe, parameters["target"], parameters["group_by"][0], parameters.get("alpha", 0.05)),
                request,
                logical_shape="statistical_test",
            )
        if method_id == "mann_whitney":
            return self._table_response(
                self.mann_whitney_test(dataframe, parameters["target"], parameters["group_by"][0], parameters.get("alpha", 0.05)),
                request,
                logical_shape="statistical_test",
            )
        if method_id == "confidence_interval":
            return self._table_response(
                self.confidence_interval(dataframe, parameters["target"], parameters.get("confidence_level", 0.95)),
                request,
                logical_shape="statistical_test",
            )
        if method_id == "regression_significance":
            return self._table_response(
                self.regression_significance(
                    dataframe,
                    parameters["target"],
                    parameters.get("feature_columns", []),
                    parameters.get("alpha", 0.05),
                ),
                request,
                logical_shape="statistical_test",
            )
        if method_id == "significance_inference":
            return self._table_response(
                self.group_significance_test(dataframe, parameters["target"], parameters["group_by"][0], parameters.get("alpha", 0.05)),
                request,
                logical_shape="statistical_test",
            )
        if method_id == "power_analysis":
            return self._table_response(
                self.power_analysis(dataframe, parameters["target"], parameters["group_by"][0], parameters.get("alpha", 0.05)),
                request,
                logical_shape="statistical_test",
            )
        if method_id == "sample_size_estimate":
            return self._table_response(
                self.sample_size_estimate(
                    dataframe,
                    parameters["target"],
                    parameters["group_by"][0],
                    parameters.get("alpha", 0.05),
                    parameters.get("desired_power", 0.80),
                ),
                request,
                logical_shape="statistical_test",
            )
        raise ComputeError(f"Stats adapter does not support method {method_id!r}.")

    def _resolve_dataframe(self, request: ComputeRequest) -> pd.DataFrame:
        for artifact in request.resolved_inputs.values():
            if artifact.kind in {"dataset", "frame"} and isinstance(artifact.value, pd.DataFrame):
                return artifact.value
        if request.dataset is not None:
            return request.dataset.data
        raise ComputeError("Stats compute methods require a dataset or frame artifact input.")

    def _optional_table_response(
        self,
        table: TableArtifact | None,
        request: ComputeRequest,
        *,
        logical_shape: str,
    ) -> ComputeResponse:
        if table is None:
            return ComputeResponse()
        return self._table_response(table, request, logical_shape=logical_shape)

    def _table_response(self, table: TableArtifact, request: ComputeRequest, *, logical_shape: str) -> ComputeResponse:
        artifact_id = request.primary_output_ref() or table.name
        artifact = artifact_from_value(
            artifact_id,
            table.dataframe,
            role="final",
            logical_shape=logical_shape,
            physical_shape="recordset",
            metadata={"table_name": table.name, **dict(table.metadata)},
        )
        return ComputeResponse(tables=[table], produced_artifacts=[artifact])

    def missingness_summary(self, dataframe: pd.DataFrame) -> TableArtifact:
        """Return a null summary for each column."""
        summary = pd.DataFrame(
            {
                "column": dataframe.columns,
                "null_count": [int(dataframe[column].isna().sum()) for column in dataframe.columns],
                "null_ratio": [float(dataframe[column].isna().mean()) for column in dataframe.columns],
            }
        ).sort_values(["null_ratio", "null_count"], ascending=False)

        return TableArtifact(
            name="missingness_summary",
            description="Null counts and ratios by column.",
            dataframe=summary.reset_index(drop=True),
        )

    def numeric_summary(self, dataframe: pd.DataFrame) -> TableArtifact:
        """Return a summary table for numeric columns."""
        numeric_columns = dataframe.select_dtypes(include=["number"])
        if numeric_columns.empty:
            summary = pd.DataFrame(columns=["column", "count", "mean", "std", "min", "max"])
        else:
            summary = numeric_columns.describe().transpose().reset_index().rename(columns={"index": "column"})

        return TableArtifact(
            name="numeric_summary",
            description="Summary statistics for numeric columns.",
            dataframe=summary,
        )

    def distribution_summary(self, dataframe: pd.DataFrame, target: str) -> TableArtifact | None:
        """Return simple distribution diagnostics for a numeric target."""
        if target not in dataframe.columns:
            raise ComputeError(f"Target column '{target}' does not exist in the dataset.")

        series = pd.to_numeric(dataframe[target], errors="coerce").dropna()
        if series.empty:
            raise ComputeError(f"Target column '{target}' has no numeric values for distribution analysis.")

        summary = pd.DataFrame(
            [
                {
                    "target": target,
                    "count": int(series.count()),
                    "mean": float(series.mean()),
                    "median": float(series.median()),
                    "std": float(series.std(ddof=0)),
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "q1": float(series.quantile(0.25)),
                    "q3": float(series.quantile(0.75)),
                    "skewness": float(series.skew()),
                    "kurtosis": float(series.kurtosis()),
                }
            ]
        )

        return TableArtifact(
            name="distribution_summary",
            description=f"Distribution summary for {target}.",
            dataframe=summary,
        )

    def correlation_matrix(self, dataframe: pd.DataFrame, target: str | None = None) -> TableArtifact | None:
        """Return a correlation table for numeric columns."""
        numeric_columns = dataframe.select_dtypes(include=["number"])
        if numeric_columns.shape[1] < 2:
            return None
        if target is not None and target not in dataframe.columns:
            raise ComputeError(f"Target column '{target}' does not exist in the dataset.")

        correlations = numeric_columns.corr(numeric_only=True)
        if target and target in correlations.columns:
            target_correlations = (
                correlations[target]
                .drop(labels=[target], errors="ignore")
                .sort_values(ascending=False)
                .reset_index()
                .rename(columns={"index": "column", target: "correlation"})
            )
            description = f"Correlation of numeric columns against {target}."
            table = target_correlations
            name = "target_correlation"
        else:
            table = correlations.reset_index().rename(columns={"index": "column"})
            description = "Correlation matrix for numeric columns."
            name = "correlation_matrix"

        return TableArtifact(name=name, description=description, dataframe=table)

    def group_mean_comparison(self, dataframe: pd.DataFrame, target: str, group_column: str) -> TableArtifact | None:
        """Compare the target mean across the first two groups in a dimension column."""
        if target not in dataframe.columns or group_column not in dataframe.columns:
            raise ComputeError(f"Columns '{target}' and '{group_column}' are required for group mean comparison.")
        if group_column == target:
            raise ComputeError("Group comparison column must be different from the target column.")

        prepared = dataframe[[target, group_column]].copy()
        prepared[target] = pd.to_numeric(prepared[target], errors="coerce")
        prepared = prepared.dropna(subset=[target, group_column])
        if prepared.empty:
            return None

        grouped_values: list[tuple[str, pd.Series]] = []
        for group_name, group_frame in prepared.groupby(group_column, dropna=False):
            values = group_frame[target]
            if len(values) >= 2:
                grouped_values.append((str(group_name), values))

        if len(grouped_values) < 2:
            return None

        left_name, left_values = grouped_values[0]
        right_name, right_values = grouped_values[1]
        t_stat, p_value = stats.ttest_ind(left_values, right_values, equal_var=False)

        comparison = pd.DataFrame(
            [
                {
                    "group_column": group_column,
                    "left_group": left_name,
                    "right_group": right_name,
                    "left_mean": float(left_values.mean()),
                    "right_mean": float(right_values.mean()),
                    "mean_delta": float(left_values.mean() - right_values.mean()),
                    "t_statistic": float(t_stat),
                    "p_value": float(p_value),
                }
            ]
        )

        return TableArtifact(
            name="group_mean_comparison",
            description=f"Mean comparison for {target} across {group_column}.",
            dataframe=comparison,
        )

    def time_series_diagnostics(self, dataframe: pd.DataFrame, target: str, time_column: str) -> TableArtifact | None:
        """Return simple diagnostics for a time-ordered target series."""
        if target not in dataframe.columns or time_column not in dataframe.columns:
            raise ComputeError(f"Columns '{target}' and '{time_column}' are required for time-series diagnostics.")

        prepared = dataframe[[time_column, target]].copy()
        prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared[target] = pd.to_numeric(prepared[target], errors="coerce")
        prepared = prepared.dropna(subset=[time_column, target]).sort_values(time_column)
        if len(prepared) < 3:
            return None

        prepared["period_month"] = prepared[time_column].dt.to_period("M").astype(str)
        series = prepared.groupby("period_month", as_index=False)[target].sum()
        if len(series) < 3:
            return None

        values = series[target].astype(float)
        diffs = values.diff().dropna()
        diagnostics = pd.DataFrame(
            [
                {
                    "target": target,
                    "period_count": int(len(series)),
                    "first_period": series.iloc[0]["period_month"],
                    "last_period": series.iloc[-1]["period_month"],
                    "first_value": float(values.iloc[0]),
                    "last_value": float(values.iloc[-1]),
                    "net_change": float(values.iloc[-1] - values.iloc[0]),
                    "average_change": float(diffs.mean()) if not diffs.empty else 0.0,
                    "change_volatility": float(diffs.std(ddof=0)) if len(diffs) > 1 else 0.0,
                    "lag1_autocorrelation": float(values.autocorr(lag=1)) if len(values) > 2 else 0.0,
                }
            ]
        )

        return TableArtifact(
            name="time_series_diagnostics",
            description=f"Time-series diagnostics for {target}.",
            dataframe=diagnostics,
        )

    def anomaly_summary(self, dataframe: pd.DataFrame, target: str, time_column: str | None = None) -> TableArtifact | None:
        """Flag simple z-score anomalies for a target series."""
        if target not in dataframe.columns:
            raise ComputeError(f"Target column '{target}' does not exist in the dataset.")

        prepared = dataframe[[target]].copy()
        if time_column and time_column in dataframe.columns:
            prepared[time_column] = pd.to_datetime(dataframe[time_column], errors="coerce")
            prepared = prepared.dropna(subset=[time_column, target]).sort_values(time_column)
            prepared["label"] = prepared[time_column].astype(str)
        else:
            prepared = prepared.dropna(subset=[target])
            prepared["label"] = prepared.index.astype(str)

        if len(prepared) < 3:
            return None

        series = prepared[target].astype(float)
        std = float(series.std(ddof=0))
        if std == 0.0:
            return None

        mean = float(series.mean())
        prepared["z_score"] = (series - mean) / std
        anomalies = prepared.loc[prepared["z_score"].abs() >= 1.8, ["label", target, "z_score"]].copy()
        anomalies = anomalies.rename(columns={"label": "observation", target: "target_value"})

        return TableArtifact(
            name="anomaly_summary",
            description=f"Z-score anomaly candidates for {target}.",
            dataframe=anomalies.reset_index(drop=True),
        )

    def t_test(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_column: str,
        alpha: float = DEFAULT_ALPHA,
    ) -> TableArtifact:
        """Run a Welch two-sample t-test across exactly two groups."""
        left_name, left_values, right_name, right_values = self._two_group_numeric_values(dataframe, target, group_column)
        statistic, p_value = stats.ttest_ind(left_values, right_values, equal_var=False)
        return self._test_result_table(
            name="t_test",
            description=f"Welch t-test for {target} by {group_column}.",
            payload={
                "test_name": "welch_t_test",
                "target": target,
                "group_column": group_column,
                "left_group": left_name,
                "right_group": right_name,
                "left_count": int(len(left_values)),
                "right_count": int(len(right_values)),
                "left_mean": float(left_values.mean()),
                "right_mean": float(right_values.mean()),
                "statistic": float(statistic),
                "p_value": float(p_value),
                "alpha": float(alpha),
            },
        )

    def mann_whitney_test(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_column: str,
        alpha: float = DEFAULT_ALPHA,
    ) -> TableArtifact:
        """Run a Mann-Whitney U test across exactly two groups."""
        left_name, left_values, right_name, right_values = self._two_group_numeric_values(dataframe, target, group_column)
        statistic, p_value = stats.mannwhitneyu(left_values, right_values, alternative="two-sided")
        return self._test_result_table(
            name="mann_whitney_test",
            description=f"Mann-Whitney U test for {target} by {group_column}.",
            payload={
                "test_name": "mann_whitney_u",
                "target": target,
                "group_column": group_column,
                "left_group": left_name,
                "right_group": right_name,
                "left_count": int(len(left_values)),
                "right_count": int(len(right_values)),
                "left_median": float(left_values.median()),
                "right_median": float(right_values.median()),
                "statistic": float(statistic),
                "p_value": float(p_value),
                "alpha": float(alpha),
            },
        )

    def anova_test(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_column: str,
        alpha: float = DEFAULT_ALPHA,
    ) -> TableArtifact:
        """Run a one-way ANOVA across two or more groups."""
        grouped_values = self._grouped_numeric_values(dataframe, target, group_column, minimum_count=2)
        if len(grouped_values) < 2:
            raise ComputeError("ANOVA requires at least two groups with two or more observations.")

        statistic, p_value = stats.f_oneway(*(values for _, values in grouped_values))
        payload = {
            "test_name": "anova",
            "target": target,
            "group_column": group_column,
            "group_count": int(len(grouped_values)),
            "statistic": float(statistic),
            "p_value": float(p_value),
            "alpha": float(alpha),
        }
        for index, (group_name, values) in enumerate(grouped_values, start=1):
            payload[f"group_{index}_name"] = group_name
            payload[f"group_{index}_count"] = int(len(values))
            payload[f"group_{index}_mean"] = float(values.mean())
        return self._test_result_table(
            name="anova_test",
            description=f"One-way ANOVA for {target} by {group_column}.",
            payload=payload,
        )

    def chi_square_test(
        self,
        dataframe: pd.DataFrame,
        left_column: str,
        right_column: str,
        alpha: float = DEFAULT_ALPHA,
    ) -> TableArtifact:
        """Run a chi-square independence test between two categorical columns."""
        self._require_columns(dataframe, [left_column, right_column])
        prepared = dataframe[[left_column, right_column]].dropna()
        if prepared.empty:
            raise ComputeError("Chi-square testing requires non-null categorical observations.")

        contingency = pd.crosstab(prepared[left_column], prepared[right_column])
        if contingency.shape[0] < 2 or contingency.shape[1] < 2:
            raise ComputeError("Chi-square testing requires at least two categories in each column.")

        statistic, p_value, degrees_of_freedom, _ = stats.chi2_contingency(contingency)
        result = self._test_result_table(
            name="chi_square_test",
            description=f"Chi-square independence test for {left_column} and {right_column}.",
            payload={
                "test_name": "chi_square",
                "left_column": left_column,
                "right_column": right_column,
                "statistic": float(statistic),
                "p_value": float(p_value),
                "degrees_of_freedom": int(degrees_of_freedom),
                "alpha": float(alpha),
                "row_category_count": int(contingency.shape[0]),
                "column_category_count": int(contingency.shape[1]),
            },
        )
        result.dataframe["observed_rows"] = int(len(prepared))
        return result

    def confidence_interval(
        self,
        dataframe: pd.DataFrame,
        target: str,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    ) -> TableArtifact:
        """Return a confidence interval for the mean of a numeric target."""
        series = self._numeric_series(dataframe, target)
        if len(series) < 2:
            raise ComputeError("Confidence interval analysis requires at least two numeric observations.")

        mean_value = float(series.mean())
        standard_error = float(stats.sem(series))
        interval = stats.t.interval(confidence_level, len(series) - 1, loc=mean_value, scale=standard_error)
        return TableArtifact(
            name="confidence_interval",
            description=f"{confidence_level:.0%} confidence interval for {target}.",
            dataframe=pd.DataFrame(
                [
                    {
                        "target": target,
                        "confidence_level": float(confidence_level),
                        "sample_size": int(len(series)),
                        "sample_mean": mean_value,
                        "standard_error": standard_error,
                        "lower_bound": float(interval[0]),
                        "upper_bound": float(interval[1]),
                        "margin_of_error": float(interval[1] - mean_value),
                    }
                ]
            ),
        )

    def regression_significance(
        self,
        dataframe: pd.DataFrame,
        target: str,
        feature_columns: list[str],
        alpha: float = DEFAULT_ALPHA,
    ) -> TableArtifact:
        """Fit a simple OLS model and return coefficient significance."""
        self._require_columns(dataframe, [target, *feature_columns])
        prepared = dataframe[[target, *feature_columns]].copy()
        prepared[target] = pd.to_numeric(prepared[target], errors="coerce")
        for feature_column in feature_columns:
            prepared[feature_column] = pd.to_numeric(prepared[feature_column], errors="coerce")
        prepared = prepared.dropna()
        if prepared.empty or len(prepared) < len(feature_columns) + 2:
            raise ComputeError("Regression significance testing requires enough complete numeric observations.")

        rows: list[dict[str, object]] = []
        if sm is not None:
            design_matrix = sm.add_constant(prepared[feature_columns], has_constant="add")
            model = sm.OLS(prepared[target], design_matrix).fit()
            intervals = model.conf_int(alpha=alpha)

            for parameter_name in model.params.index:
                rows.append(
                    {
                        "parameter": str(parameter_name),
                        "coefficient": float(model.params[parameter_name]),
                        "std_error": float(model.bse[parameter_name]),
                        "t_value": float(model.tvalues[parameter_name]),
                        "p_value": float(model.pvalues[parameter_name]),
                        "lower_bound": float(intervals.loc[parameter_name, 0]),
                        "upper_bound": float(intervals.loc[parameter_name, 1]),
                        "alpha": float(alpha),
                        "is_significant": bool(model.pvalues[parameter_name] < alpha),
                    }
                )
        else:
            rows.extend(self._fallback_regression_significance_rows(prepared, target, feature_columns, alpha))

        return TableArtifact(
            name="regression_significance",
            description=f"OLS coefficient significance for {target}.",
            dataframe=pd.DataFrame(rows),
        )

    def group_significance_test(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_column: str,
        alpha: float = DEFAULT_ALPHA,
    ) -> TableArtifact:
        """Choose an appropriate group significance test based on group count."""
        grouped_values = self._grouped_numeric_values(dataframe, target, group_column, minimum_count=2)
        if len(grouped_values) < 2:
            raise ComputeError("Statistical significance testing requires at least two populated groups.")
        if len(grouped_values) == 2:
            result = self.t_test(dataframe, target, group_column, alpha)
            result.name = "significance_test"
            result.description = f"Significance inference for {target} by {group_column} using a Welch t-test."
            return result

        result = self.anova_test(dataframe, target, group_column, alpha)
        result.name = "significance_test"
        result.description = f"Significance inference for {target} by {group_column} using ANOVA."
        return result

    def power_analysis(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_column: str,
        alpha: float = DEFAULT_ALPHA,
    ) -> TableArtifact:
        """Estimate observed power for a two-group mean comparison."""
        left_name, left_values, right_name, right_values = self._two_group_numeric_values(dataframe, target, group_column)
        effect_size = self._cohens_d(left_values, right_values)
        if effect_size == 0.0:
            raise ComputeError("Power analysis requires a non-zero observed effect size.")

        if TTestIndPower is not None:
            power_model = TTestIndPower()
            actual_power = power_model.power(
                effect_size=abs(effect_size),
                nobs1=len(left_values),
                alpha=alpha,
                ratio=len(right_values) / len(left_values),
            )
        else:
            actual_power = self._approximate_two_group_power(
                abs(effect_size),
                len(left_values),
                len(right_values),
                alpha,
            )
        return TableArtifact(
            name="power_analysis",
            description=f"Observed power for {target} by {group_column}.",
            dataframe=pd.DataFrame(
                [
                    {
                        "target": target,
                        "group_column": group_column,
                        "left_group": left_name,
                        "right_group": right_name,
                        "effect_size": float(effect_size),
                        "alpha": float(alpha),
                        "power": float(actual_power),
                        "left_count": int(len(left_values)),
                        "right_count": int(len(right_values)),
                    }
                ]
            ),
        )

    def sample_size_estimate(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_column: str,
        alpha: float = DEFAULT_ALPHA,
        desired_power: float = DEFAULT_POWER,
    ) -> TableArtifact:
        """Estimate per-group sample size for a two-group mean comparison."""
        left_name, left_values, right_name, right_values = self._two_group_numeric_values(dataframe, target, group_column)
        effect_size = self._cohens_d(left_values, right_values)
        if effect_size == 0.0:
            raise ComputeError("Sample size estimation requires a non-zero observed effect size.")

        if TTestIndPower is not None:
            power_model = TTestIndPower()
            required_sample_size = power_model.solve_power(
                effect_size=abs(effect_size),
                power=desired_power,
                alpha=alpha,
                ratio=1.0,
            )
            required_sample_size_value = self._coerce_scalar_float(required_sample_size)
        else:
            required_sample_size_value = self._approximate_sample_size_per_group(
                abs(effect_size),
                alpha,
                desired_power,
            )
        if not math.isfinite(required_sample_size_value):
            raise ComputeError("Sample size estimation did not converge to a finite result.")
        return TableArtifact(
            name="sample_size_estimate",
            description=f"Estimated per-group sample size for {target} by {group_column}.",
            dataframe=pd.DataFrame(
                [
                    {
                        "target": target,
                        "group_column": group_column,
                        "left_group": left_name,
                        "right_group": right_name,
                        "effect_size": float(effect_size),
                        "alpha": float(alpha),
                        "desired_power": float(desired_power),
                        "required_sample_size_per_group": required_sample_size_value,
                    }
                ]
            ),
        )

    def _test_result_table(self, name: str, description: str, payload: dict[str, object]) -> TableArtifact:
        p_value = float(payload["p_value"])
        alpha = float(payload["alpha"])
        payload["is_significant"] = bool(p_value < alpha)
        payload["decision"] = "reject_null" if p_value < alpha else "fail_to_reject_null"
        return TableArtifact(name=name, description=description, dataframe=pd.DataFrame([payload]))

    def _require_columns(self, dataframe: pd.DataFrame, column_names: list[str]) -> None:
        missing_columns = [column_name for column_name in column_names if column_name not in dataframe.columns]
        if missing_columns:
            joined = ", ".join(missing_columns)
            raise ComputeError(f"Required columns are missing from the dataset: {joined}")

    def _coerce_scalar_float(self, value: object) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if hasattr(value, "item"):
            try:
                return float(value.item())
            except Exception:
                pass
        if hasattr(value, "__len__") and hasattr(value, "__getitem__"):
            try:
                if len(value) == 1:
                    return float(value[0])
            except Exception:
                pass
        raise ComputeError("Statistical routine returned a non-scalar result.")

    def _numeric_series(self, dataframe: pd.DataFrame, target: str) -> pd.Series:
        if target not in dataframe.columns:
            raise ComputeError(f"Target column '{target}' does not exist in the dataset.")
        series = pd.to_numeric(dataframe[target], errors="coerce").dropna()
        if series.empty:
            raise ComputeError(f"Target column '{target}' has no numeric values for statistical testing.")
        return series

    def _grouped_numeric_values(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_column: str,
        minimum_count: int,
    ) -> list[tuple[str, pd.Series]]:
        self._require_columns(dataframe, [target, group_column])
        prepared = dataframe[[target, group_column]].copy()
        prepared[target] = pd.to_numeric(prepared[target], errors="coerce")
        prepared = prepared.dropna(subset=[target, group_column])
        grouped_values: list[tuple[str, pd.Series]] = []
        for group_name, group_frame in prepared.groupby(group_column, dropna=False):
            values = group_frame[target].astype(float)
            if len(values) >= minimum_count:
                grouped_values.append((str(group_name), values.reset_index(drop=True)))
        grouped_values.sort(key=lambda item: item[0])
        return grouped_values

    def _two_group_numeric_values(
        self,
        dataframe: pd.DataFrame,
        target: str,
        group_column: str,
    ) -> tuple[str, pd.Series, str, pd.Series]:
        grouped_values = self._grouped_numeric_values(dataframe, target, group_column, minimum_count=2)
        if len(grouped_values) != 2:
            raise ComputeError("This statistical test requires exactly two groups with two or more observations.")
        left_name, left_values = grouped_values[0]
        right_name, right_values = grouped_values[1]
        return left_name, left_values, right_name, right_values

    def _cohens_d(self, left_values: pd.Series, right_values: pd.Series) -> float:
        pooled_deviation = (((len(left_values) - 1) * left_values.var(ddof=1)) + ((len(right_values) - 1) * right_values.var(ddof=1)))
        pooled_deviation /= (len(left_values) + len(right_values) - 2)
        if pooled_deviation <= 0.0:
            return 0.0
        return float((left_values.mean() - right_values.mean()) / pooled_deviation**0.5)

    def _fallback_regression_significance_rows(
        self,
        prepared: pd.DataFrame,
        target: str,
        feature_columns: list[str],
        alpha: float,
    ) -> list[dict[str, object]]:
        y = prepared[target].to_numpy(dtype=float)
        x = prepared[feature_columns].to_numpy(dtype=float)
        x = np.column_stack([np.ones(len(x)), x])
        parameter_names = ["const", *feature_columns]
        observation_count, parameter_count = x.shape
        degrees_of_freedom = observation_count - parameter_count
        if degrees_of_freedom <= 0:
            raise ComputeError("Regression significance testing requires more rows than model parameters.")

        xtx = x.T @ x
        try:
            xtx_inv = np.linalg.inv(xtx)
        except np.linalg.LinAlgError as exc:
            raise ComputeError("Regression significance testing encountered a singular design matrix.") from exc

        coefficients = xtx_inv @ x.T @ y
        residuals = y - (x @ coefficients)
        rss = float(np.sum(residuals**2))
        sigma_squared = rss / degrees_of_freedom
        standard_errors = np.sqrt(np.diag(sigma_squared * xtx_inv))
        if np.any(standard_errors == 0):
            raise ComputeError("Regression significance testing produced zero standard error estimates.")

        t_values = coefficients / standard_errors
        p_values = 2.0 * (1.0 - stats.t.cdf(np.abs(t_values), df=degrees_of_freedom))
        critical_value = float(stats.t.ppf(1.0 - (alpha / 2.0), df=degrees_of_freedom))

        rows: list[dict[str, object]] = []
        for index, parameter_name in enumerate(parameter_names):
            coefficient = float(coefficients[index])
            std_error = float(standard_errors[index])
            lower_bound = coefficient - (critical_value * std_error)
            upper_bound = coefficient + (critical_value * std_error)
            p_value = float(p_values[index])
            rows.append(
                {
                    "parameter": parameter_name,
                    "coefficient": coefficient,
                    "std_error": std_error,
                    "t_value": float(t_values[index]),
                    "p_value": p_value,
                    "lower_bound": float(lower_bound),
                    "upper_bound": float(upper_bound),
                    "alpha": float(alpha),
                    "is_significant": bool(p_value < alpha),
                }
            )
        return rows

    def _approximate_two_group_power(
        self,
        effect_size: float,
        left_count: int,
        right_count: int,
        alpha: float,
    ) -> float:
        effective_n = (left_count * right_count) / max(left_count + right_count, 1)
        z_alpha = float(stats.norm.ppf(1.0 - (alpha / 2.0)))
        z_effect = effect_size * math.sqrt(max(effective_n, 1e-9))
        power = float(stats.norm.cdf(z_effect - z_alpha))
        return min(max(power, 0.0), 1.0)

    def _approximate_sample_size_per_group(
        self,
        effect_size: float,
        alpha: float,
        desired_power: float,
    ) -> float:
        z_alpha = float(stats.norm.ppf(1.0 - (alpha / 2.0)))
        z_beta = float(stats.norm.ppf(desired_power))
        if effect_size <= 0.0:
            raise ComputeError("Sample size estimation requires a positive effect size.")
        return float(2.0 * ((z_alpha + z_beta) / effect_size) ** 2)


StatsComputeEngine = StatsModelsAdapter
