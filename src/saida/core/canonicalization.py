"""Structured input canonicalization with a transformer hook."""

from __future__ import annotations

import re
from calendar import month_name
from calendar import month_abbr

from saida.config import NlpConfig
from saida.exceptions import ValidationError
from saida.llm import IntentProposal
from saida.core.contracts import AnalysisRequest, Dataset, DatasetProfile, SourceContext
from saida.core.prompt_family_catalog import derive_prompt_family

TASK_LABELS = ["descriptive", "diagnostic", "statistical", "predictive", "forecasting"]
DISTINCT_VALUE_KEYWORDS = {
    "list",
    "list of all",
    "list all",
    "all values",
    "available values",
    "give me all",
}
DISTINCT_VALUE_CATEGORY_KEYWORDS = {
    "different",
    "categories",
    "category",
    "values",
    "types",
    "kinds",
}
ROW_COUNT_KEYWORDS = {"how many rows", "number of rows", "data rows", "row count", "count rows"}
REPRESENTATION_LOW_KEYWORDS = {"least represented", "fewest rows", "least number of rows", "smallest count"}
REPRESENTATION_HIGH_KEYWORDS = {"most represented", "most rows", "highest count", "largest count"}
TIME_COVERAGE_YEAR_KEYWORDS = {
    "which years",
    "what years",
    "years are present",
    "years does the data cover",
    "years are in the data",
}
TIME_COVERAGE_MONTH_KEYWORDS = {
    "which months",
    "what months",
    "months are present",
    "months are in the data",
}
TIME_COVERAGE_RANGE_KEYWORDS = {
    "date range",
    "date span",
    "data range",
    "earliest and latest date",
    "from when to when",
}
COLUMN_TYPE_INVENTORY_KEYWORDS = {
    "data type",
    "data types",
    "field types",
    "column types",
    "dtype",
    "schema",
}
NUMERIC_COLUMN_INVENTORY_KEYWORDS = {
    "numeric columns",
    "numeric fields",
    "numerical columns",
    "numerical fields",
    "number columns",
    "number fields",
}
CATEGORICAL_COLUMN_INVENTORY_KEYWORDS = {
    "categorical columns",
    "categorical fields",
    "category columns",
    "category fields",
    "text columns",
    "text fields",
    "string columns",
    "string fields",
}
MISSING_VALUE_INVENTORY_KEYWORDS = {
    "missing values",
    "missing data",
    "null values",
    "null data",
    "nullable columns",
    "nullable fields",
}
IDENTIFIER_INVENTORY_KEYWORDS = {
    "identifier columns",
    "identifier fields",
    "likely identifiers",
    "primary key",
    "primary keys",
    "unique identifiers",
}
HIGH_CARDINALITY_INVENTORY_KEYWORDS = {
    "high cardinality",
    "high-cardinality",
    "many unique values",
    "most unique values",
    "cardinality",
}
TIME_BUCKET_COUNT_YEAR_KEYWORDS = {
    "by year",
    "per year",
    "each year",
    "those years",
    "years and how many",
}
TIME_BUCKET_COUNT_MONTH_KEYWORDS = {
    "by month",
    "per month",
    "each month",
    "those months",
    "months and how many",
}
TIME_BUCKET_COUNT_QUARTER_KEYWORDS = {
    "by quarter",
    "per quarter",
    "each quarter",
    "those quarters",
    "quarters and how many",
}
TIME_BUCKET_BREAKDOWN_YEAR_KEYWORDS = {"by year", "per year", "each year", "yearly"}
TIME_BUCKET_BREAKDOWN_MONTH_KEYWORDS = {"by month", "per month", "each month", "monthly"}
TIME_BUCKET_BREAKDOWN_QUARTER_KEYWORDS = {"by quarter", "per quarter", "each quarter", "quarterly"}
TIME_COMPARISON_KEYWORDS = {"compare", "comparison", "versus", "vs", "against"}
TABULAR_ROW_KEYWORDS = {"row", "rows", "record", "records", "entry", "entries"}
TABULAR_SURFACE_KEYWORDS = {"table", "tabular", "recordset"}
TABULAR_VERBS = {"show", "list", "return", "give me", "display"}
TABULAR_LIMIT_KEYWORDS = {"first", "last", "return", "show", "list"}
TABULAR_SORT_KEYWORDS = {"sort by", "sorted by", "order by", "ordered by", "ascending", "descending", "latest", "earliest"}
DATASET_SLICE_KEYWORDS = {"dataset", "data set", "data", "table"}
EXISTENCE_REQUEST_KEYWORDS = {
    "is there",
    "are there",
    "does",
    "do we have",
    "contains",
    "contain",
    "includes",
    "include",
    "has",
    "shows",
}
NULL_CHECK_KEYWORDS = {
    "missing value",
    "missing values",
    "missing data",
    "null value",
    "null values",
    "blank value",
    "blank values",
    "empty value",
    "empty values",
}
COMPLETE_CHECK_KEYWORDS = {
    "complete",
    "fully populated",
    "no missing values",
    "no null values",
    "without missing values",
    "without null values",
}
NUMERIC_PROPERTY_KEYWORDS = {"numeric", "numerical", "number field", "number column", "number"}
DATETIME_PROPERTY_KEYWORDS = {"datetime", "date/time", "date field", "date column", "time field", "time column"}
IDENTIFIER_PROPERTY_KEYWORDS = {"identifier", "identifiers", "primary key", "primary keys", "id field", "id column"}
CATEGORICAL_PROPERTY_KEYWORDS = {"categorical", "category", "text field", "text column", "string field", "string column"}
DIMENSION_PROPERTY_KEYWORDS = {"dimension", "dimensions", "grouping column", "grouping field", "group by column"}
MEASURE_PROPERTY_KEYWORDS = {"measure", "measures", "metric", "metrics", "measure column", "metric column"}
HIGH_CARDINALITY_PROPERTY_KEYWORDS = {"high cardinality", "high-cardinality", "many unique values"}
STATISTICAL_TEST_KEYWORDS = {
    "t_test": {"t-test", "t test", "ttest"},
    "chi_square": {"chi-square", "chi square", "chisquare"},
    "anova": {"anova"},
    "mann_whitney": {"mann-whitney", "mann whitney", "mannwhitney"},
    "confidence_interval": {"confidence interval", "confidence intervals"},
    "regression_significance": {"regression significance", "significant predictors", "significant coefficients"},
    "power_analysis": {"statistical power", "power analysis"},
    "sample_size_estimate": {"sample size", "required sample size"},
}
SIGNIFICANCE_COMPARISON_KEYWORDS = {
    "statistically significant",
    "significant difference",
    "significant differences",
    "differ significantly",
    "different enough",
}
NATURAL_SIGNIFICANCE_COMPARISON_KEYWORDS = {
    "differ in",
    "difference in",
    "different by",
    "higher than",
    "lower than",
    "longer than",
    "shorter than",
    "more than",
    "less than",
}
NATURAL_CONFIDENCE_INTERVAL_KEYWORDS = {
    "confidence range",
    "confident range",
    "uncertainty range",
    "range are we",
    "range can we be",
}
NATURAL_POWER_ANALYSIS_KEYWORDS = {
    "enough data to detect",
    "enough data for",
    "enough power",
    "sufficient power",
    "powered to detect",
    "detect a real difference",
}
NATURAL_SAMPLE_SIZE_KEYWORDS = {
    "how many samples",
    "how many observations",
    "how many rows per group",
    "how many records per group",
    "sample size do we need",
    "sample size is needed",
    "sample size needed",
}
NATURAL_REGRESSION_SIGNIFICANCE_KEYWORDS = {
    "significantly affect",
    "significantly affects",
    "significantly influence",
    "significantly influences",
    "significantly predict",
    "significantly predicts",
}
AGGREGATION_KEYWORDS = {
    "mean": {"average", "mean", "avg"},
    "max": {"highest", "maximum", "max", "top", "largest", "best"},
    "min": {"lowest", "minimum", "min", "smallest", "worst"},
    "sum": {"total", "sum"},
    "count": {"count", "how many", "number of"},
}
TASK_KEYWORDS = {
    "forecasting": {"forecast", "predict next", "projection", "future"},
    "predictive": {"train", "predict", "classification", "regression", "model"},
    "diagnostic": {"why", "drop", "decrease", "decline", "driver", "cause"},
    "statistical": {"correlation", "significant", "hypothesis", "anomaly", "distribution"},
    "descriptive": {"show", "summarize", "overview", "trend", "list"},
}
RANKING_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


class InputCanonicalizer:
    """Convert raw input text into a canonical structured analysis plan request."""

    def __init__(self, config: NlpConfig | None = None) -> None:
        self.config = config or NlpConfig()

    def normalize(
        self,
        question: str,
        dataset: Dataset,
        profile: DatasetProfile,
        context: SourceContext | None = None,
    ) -> tuple[AnalysisRequest, list[str]]:
        """Normalize a user question into an AnalysisRequest."""
        if not question or not question.strip():
            raise ValidationError("Analysis question cannot be empty.")
        if dataset.data.empty:
            raise ValidationError("Cannot analyze an empty dataset.")
        if profile.column_count == 0:
            raise ValidationError("Dataset profile contains no columns.")

        warnings: list[str] = []
        intent_name = self._detect_intent_name(question, profile)
        task_type_hint = self._classify_task(question)
        if self.config.enable_transformers and self.config.zero_shot_model:
            task_type_hint = self._maybe_refine_task_with_transformers(question, task_type_hint, warnings)

        target = self._resolve_target(question, profile, context, intent_name)
        aggregation = self._extract_aggregation(question)
        time_reference = self._extract_time_reference(question)
        horizon = self._extract_horizon(question)
        group_by = self._extract_group_by(question, profile)
        filters = self._extract_filters(question, profile, context)
        options = self._build_request_options(dataset.name, intent_name)
        selected_columns = self._extract_selected_columns(question, profile, filters)
        sort_by, sort_direction = self._extract_sort_request(question, profile, target, group_by)
        limit = self._extract_tabular_limit(question)
        page = self._extract_page_number(question)
        page_size = self._extract_page_size(question)
        self._apply_statistical_options(question, profile, options)
        intent_name = self._resolve_ranking_intent(question, intent_name, target, group_by, profile, options)
        if intent_name in {"row_ranking", "group_ranking"}:
            aggregation = None
        intent_name = self._resolve_tabular_intent(
            question,
            intent_name,
            target,
            group_by,
            selected_columns,
            filters,
            aggregation,
        )
        if intent_name == "grouped_tabular_query" and target in set(group_by or []) and target not in set(profile.measure_columns):
            target = None
        if self._looks_like_grouped_entity_count_request(question, target, group_by, profile):
            intent_name = "grouped_tabular_query"
            target = None
            aggregation = "count"
        if intent_name == "existence_check":
            target, aggregation, group_by = self._configure_existence_request(
                question,
                profile,
                target,
                aggregation,
                group_by,
                filters,
                options,
            )
        if options.get("statistical_test"):
            task_type_hint = "statistical"
        if options.get("statistical_test") == "chi_square" and options.get("comparison_columns"):
            comparison_columns = list(options["comparison_columns"])
            target = comparison_columns[0]
            group_by = comparison_columns[1:2]
        if options.get("statistical_test") == "regression_significance" and options.get("feature_columns"):
            regression_target = options.get("regression_target")
            if isinstance(regression_target, str):
                target = regression_target
            else:
                named_columns = self._extract_named_columns(question, profile)
                if named_columns:
                    target = named_columns[0]
        if intent_name in {"time_coverage", "time_bucket_counts", "time_bucket_breakdown", "time_period_comparison"}:
            options["time_coverage_mode"] = self._time_coverage_mode(question)
            if intent_name in {"time_bucket_counts", "time_bucket_breakdown", "time_period_comparison"}:
                options["time_bucket"] = self._time_bucket_mode(question)
            if intent_name in {"time_coverage", "time_bucket_counts"}:
                target = None
                aggregation = None
                group_by = None
        if options.get("statistical_test") == "chi_square":
            group_by = self._extract_statistical_group_by(question, profile, target)
        elif options.get("statistical_test") == "regression_significance":
            group_by = None
        elif options.get("statistical_test") in {"t_test", "anova", "mann_whitney", "significance_inference", "power_analysis", "sample_size_estimate"} and not group_by:
            group_by = self._extract_statistical_group_by(question, profile, target)

        if intent_name == "representation_ranking" and target is not None:
            group_by = [target]
            aggregation = "count"
            options["ranking_direction"] = self._representation_direction(question)
            if question.lower().strip().startswith(("which ", "what ")):
                options["ranking_limit"] = 1
        if intent_name in {"tabular_query", "grouped_tabular_query"}:
            options["selected_columns"] = selected_columns or []
            options["sort_by"] = sort_by
            options["sort_direction"] = sort_direction
            options["limit"] = limit
            options["page"] = page
            options["page_size"] = page_size or limit or 50
            if intent_name == "grouped_tabular_query" and aggregation is None:
                aggregation = "count" if target is None else "sum"
        options["intent_name"] = intent_name

        if target is None and profile.measure_columns and intent_name not in {
            "row_count",
            "column_inventory",
            "column_type_inventory",
            "numeric_column_inventory",
            "categorical_column_inventory",
            "measure_inventory",
            "dimension_inventory",
            "time_column_inventory",
            "missing_value_inventory",
            "identifier_inventory",
            "high_cardinality_inventory",
            "time_coverage",
            "time_bucket_counts",
            "time_bucket_breakdown",
            "time_period_comparison",
            "existence_check",
            "tabular_query",
            "grouped_tabular_query",
        }:
            warnings.append("No explicit metric matched the prompt; using the first measure candidate.")
            target = profile.measure_columns[0]
        if target is None and not profile.measure_columns and intent_name not in {
            "row_count",
            "column_inventory",
            "column_type_inventory",
            "numeric_column_inventory",
            "categorical_column_inventory",
            "measure_inventory",
            "dimension_inventory",
            "time_column_inventory",
            "missing_value_inventory",
            "identifier_inventory",
            "high_cardinality_inventory",
            "time_coverage",
            "time_bucket_counts",
            "time_bucket_breakdown",
            "time_period_comparison",
            "existence_check",
            "tabular_query",
            "grouped_tabular_query",
        }:
            raise ValidationError("No target metric could be resolved from the question or dataset profile.")
        distinct_values = self._should_list_distinct_values(question, target, profile)

        request = AnalysisRequest(
            question=question,
            intent_name=intent_name,
            task_type_hint=task_type_hint,
            target=target,
            aggregation=aggregation,
            horizon=horizon,
            filters=filters,
            group_by=group_by,
            time_reference=time_reference,
            options={
                **options,
                "nlp_backend": "transformer+rules" if self.config.enable_transformers else "rules",
                "distinct_values": distinct_values,
            },
        )
        request.prompt_family = derive_prompt_family(request)
        return request, warnings

    def _configure_existence_request(
        self,
        question: str,
        profile: DatasetProfile,
        target: str | None,
        aggregation: str | None,
        group_by: list[str] | None,
        filters: dict[str, str] | None,
        options: dict[str, object],
    ) -> tuple[str | None, str | None, list[str] | None]:
        existence_mode = self._resolve_existence_mode(question, profile, target, filters)
        options["existence_mode"] = existence_mode

        if existence_mode == "time_value":
            target = target or (profile.time_columns[0] if profile.time_columns else None)
            expected_year = self._extract_year_value(question)
            if expected_year is not None:
                options["expected_year"] = expected_year
            return target, aggregation, group_by

        aggregation = None
        group_by = None
        if existence_mode == "column_presence_check":
            options["requested_column"] = self._extract_column_presence_target(question, profile)
            return None, aggregation, group_by
        if existence_mode == "null_check":
            options["null_expectation"] = self._extract_null_expectation(question)
            return target, aggregation, group_by
        if existence_mode == "threshold_check":
            threshold_spec = self._extract_threshold_check_spec(question)
            if threshold_spec:
                options.update(threshold_spec)
            return target, aggregation, group_by
        if existence_mode == "column_property_check":
            target = target or self._extract_property_check_target(question, profile)
            expected_property = self._extract_expected_property(question)
            if expected_property is not None:
                options["expected_property"] = expected_property
            if target is not None:
                options["requested_column"] = target
            return target, aggregation, group_by

        return None, aggregation, group_by

    def normalize_with_proposal(
        self,
        question: str,
        dataset: Dataset,
        profile: DatasetProfile,
        proposal: IntentProposal,
        context: SourceContext | None = None,
    ) -> tuple[AnalysisRequest, list[str]]:
        """Normalize a prompt using a validated LLM proposal plus deterministic fallbacks."""
        self._validate_inputs(question, dataset, profile)
        warnings = list(proposal.warnings)

        rule_intent_name = self._detect_intent_name(question, profile)
        rule_task_type = self._classify_task(question)
        rule_target = self._resolve_target(question, profile, context, rule_intent_name)
        rule_aggregation = self._extract_aggregation(question)
        rule_time_reference = self._extract_time_reference(question)
        rule_horizon = self._extract_horizon(question)
        rule_group_by = self._extract_group_by(question, profile)
        rule_filters = self._extract_filters(question, profile, context)
        rule_selected_columns = self._extract_selected_columns(question, profile, rule_filters)
        rule_sort_by, rule_sort_direction = self._extract_sort_request(question, profile, rule_target, rule_group_by)
        rule_limit = self._extract_tabular_limit(question)
        rule_page = self._extract_page_number(question)
        rule_page_size = self._extract_page_size(question)

        task_type_hint = self._validate_task_type(proposal.task_type_hint) or rule_task_type
        target = self._resolve_candidate_column(proposal.target, profile, context)
        aggregation = self._validate_aggregation(proposal.aggregation) or rule_aggregation
        if target is None:
            target = rule_target
        group_by = self._resolve_candidate_group_by(proposal.group_by, profile)
        if group_by is None:
            group_by = rule_group_by
        filters = self._resolve_candidate_filters(proposal.filters, profile)
        if filters is None:
            filters = rule_filters
        time_reference = self._resolve_candidate_time_reference(proposal.time_reference)
        if time_reference is None:
            time_reference = rule_time_reference
        horizon = proposal.horizon if proposal.horizon and proposal.horizon > 0 else rule_horizon

        options = self._build_request_options(dataset.name, rule_intent_name)
        self._apply_statistical_options(question, profile, options)
        rule_intent_name = self._resolve_ranking_intent(question, rule_intent_name, target or rule_target, group_by or rule_group_by, profile, options)
        if rule_intent_name in {"row_ranking", "group_ranking"}:
            aggregation = None
        rule_intent_name = self._resolve_tabular_intent(
            question,
            rule_intent_name,
            target or rule_target,
            group_by or rule_group_by,
            rule_selected_columns,
            filters or rule_filters,
            aggregation or rule_aggregation,
        )
        if rule_intent_name == "grouped_tabular_query" and target in set(group_by or []) and target not in set(profile.measure_columns):
            target = None
        if self._looks_like_grouped_entity_count_request(question, target, group_by, profile):
            rule_intent_name = "grouped_tabular_query"
            target = None
            aggregation = "count"
        if rule_intent_name == "existence_check":
            target, aggregation, group_by = self._configure_existence_request(
                question,
                profile,
                target,
                aggregation,
                group_by,
                filters,
                options,
            )
        if options.get("statistical_test"):
            task_type_hint = "statistical"
        if options.get("statistical_test") == "chi_square" and options.get("comparison_columns"):
            comparison_columns = list(options["comparison_columns"])
            target = comparison_columns[0]
            group_by = comparison_columns[1:2]
        if options.get("statistical_test") == "regression_significance" and options.get("feature_columns"):
            regression_target = options.get("regression_target")
            if isinstance(regression_target, str):
                target = regression_target
            else:
                named_columns = self._extract_named_columns(question, profile)
                if named_columns:
                    target = named_columns[0]
        if rule_intent_name in {"time_coverage", "time_bucket_counts", "time_bucket_breakdown", "time_period_comparison"}:
            options["time_coverage_mode"] = self._time_coverage_mode(question)
            if rule_intent_name in {"time_bucket_counts", "time_bucket_breakdown", "time_period_comparison"}:
                options["time_bucket"] = self._time_bucket_mode(question)
            if rule_intent_name in {"time_coverage", "time_bucket_counts"}:
                target = None
                aggregation = None
                group_by = None
        if options.get("statistical_test") == "chi_square":
            group_by = self._extract_statistical_group_by(question, profile, target)
        elif options.get("statistical_test") == "regression_significance":
            group_by = None
        elif options.get("statistical_test") in {"t_test", "anova", "mann_whitney", "significance_inference", "power_analysis", "sample_size_estimate"} and not group_by:
            group_by = self._extract_statistical_group_by(question, profile, target)
        if rule_intent_name == "representation_ranking" and target is not None:
            group_by = [target]
            aggregation = "count"
            options["ranking_direction"] = self._representation_direction(question)
            if question.lower().strip().startswith(("which ", "what ")):
                options["ranking_limit"] = 1
        if rule_intent_name in {"tabular_query", "grouped_tabular_query"}:
            options["selected_columns"] = rule_selected_columns or []
            options["sort_by"] = rule_sort_by
            options["sort_direction"] = rule_sort_direction
            options["limit"] = rule_limit
            options["page"] = rule_page
            options["page_size"] = rule_page_size or rule_limit or 50
            if rule_intent_name == "grouped_tabular_query" and aggregation is None:
                aggregation = "count" if target is None else "sum"
        options["intent_name"] = rule_intent_name

        if target is None and profile.measure_columns and rule_intent_name not in {
            "row_count",
            "column_inventory",
            "column_type_inventory",
            "numeric_column_inventory",
            "categorical_column_inventory",
            "measure_inventory",
            "dimension_inventory",
            "time_column_inventory",
            "missing_value_inventory",
            "identifier_inventory",
            "high_cardinality_inventory",
            "time_coverage",
            "time_bucket_counts",
            "time_bucket_breakdown",
            "time_period_comparison",
            "existence_check",
            "tabular_query",
            "grouped_tabular_query",
        }:
            warnings.append("No explicit metric matched the prompt; using the first measure candidate.")
            target = profile.measure_columns[0]
        if target is None and not profile.measure_columns and rule_intent_name not in {
            "row_count",
            "column_inventory",
            "column_type_inventory",
            "numeric_column_inventory",
            "categorical_column_inventory",
            "measure_inventory",
            "dimension_inventory",
            "time_column_inventory",
            "missing_value_inventory",
            "identifier_inventory",
            "high_cardinality_inventory",
            "time_coverage",
            "time_bucket_counts",
            "time_bucket_breakdown",
            "time_period_comparison",
            "existence_check",
            "tabular_query",
            "grouped_tabular_query",
        }:
            raise ValidationError("No target metric could be resolved from the question or dataset profile.")
        distinct_values = self._should_list_distinct_values(question, target, profile)

        request = AnalysisRequest(
            question=question,
            intent_name=rule_intent_name,
            task_type_hint=task_type_hint,
            target=target,
            aggregation=aggregation,
            horizon=horizon,
            filters=filters,
            group_by=group_by,
            time_reference=time_reference,
            options={
                **options,
                "candidate_capabilities": list(proposal.candidate_capabilities or []),
                "nlp_backend": "llm+validation",
                "llm_status": proposal.status,
                "distinct_values": distinct_values,
            },
        )
        request.prompt_family = derive_prompt_family(request)
        return request, warnings

    def _validate_inputs(self, question: str, dataset: Dataset, profile: DatasetProfile) -> None:
        if not question or not question.strip():
            raise ValidationError("Analysis question cannot be empty.")
        if dataset.data.empty:
            raise ValidationError("Cannot analyze an empty dataset.")
        if profile.column_count == 0:
            raise ValidationError("Dataset profile contains no columns.")

    def _classify_task(self, question: str) -> str:
        lowered = question.lower()
        for task_name, keywords in TASK_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return task_name
        return "descriptive"

    def _maybe_refine_task_with_transformers(self, question: str, current_label: str, warnings: list[str]) -> str:
        try:
            from transformers import pipeline
        except Exception:
            warnings.append("Transformers pipeline not available; falling back to deterministic canonicalization rules.")
            return current_label

        try:
            classifier = pipeline("zero-shot-classification", model=self.config.zero_shot_model)
            result = classifier(question, TASK_LABELS, multi_label=False)
        except Exception:
            warnings.append("Transformer classification failed; falling back to deterministic canonicalization rules.")
            return current_label

        label = result["labels"][0]
        score = float(result["scores"][0])
        if score < self.config.confidence_threshold:
            warnings.append("Transformer NLP confidence was low; retaining rule-based canonical intent classification.")
            return current_label
        return label
    def _resolve_target(
        self,
        question: str,
        profile: DatasetProfile,
        context: SourceContext | None,
        intent_name: str | None,
    ) -> str | None:
        lowered = question.lower()
        measure_aliases: dict[str, str] = {}
        dimension_aliases: dict[str, str] = {}
        if context:
            for metric_name in context.metric_definitions:
                measure_aliases[metric_name.lower()] = metric_name
        for column_name in profile.measure_columns:
            measure_aliases[column_name.lower()] = column_name
        for column_name in profile.dimension_columns:
            dimension_aliases[column_name.lower()] = column_name
        time_aliases = {column_name.lower(): column_name for column_name in profile.time_columns}
        all_column_aliases = {column.name.lower(): column.name for column in profile.columns}

        if intent_name == "column_type_inventory":
            return self._resolve_single_column_type_target(question, profile)

        for alias, resolved_name in measure_aliases.items():
            if alias in lowered:
                return resolved_name
        measure_token_matches = self._resolve_column_by_tokens(lowered, profile.measure_columns, context)
        if measure_token_matches:
            return measure_token_matches
        if self._extract_aggregation(question):
            for alias, resolved_name in time_aliases.items():
                if alias in lowered:
                    return resolved_name
            time_token_match = self._resolve_column_by_tokens(lowered, profile.time_columns, context)
            if time_token_match:
                return time_token_match
            for alias, resolved_name in dimension_aliases.items():
                if alias in lowered:
                    return resolved_name
            dimension_token_match = self._resolve_column_by_tokens(lowered, profile.dimension_columns, context)
            if dimension_token_match:
                return dimension_token_match
        if intent_name == "existence_check":
            for alias, resolved_name in all_column_aliases.items():
                if alias in lowered:
                    return resolved_name
            any_column_token_match = self._resolve_column_by_tokens(
                lowered,
                [column.name for column in profile.columns],
                context,
            )
            if any_column_token_match:
                return any_column_token_match
        if intent_name == "tabular_query":
            for alias, resolved_name in all_column_aliases.items():
                if alias in lowered:
                    return resolved_name
            any_column_token_match = self._resolve_column_by_tokens(
                lowered,
                [column.name for column in profile.columns],
                context,
            )
            if any_column_token_match:
                return any_column_token_match
        if intent_name == "grouped_tabular_query":
            for alias, resolved_name in measure_aliases.items():
                if alias in lowered:
                    return resolved_name
            measure_token_match = self._resolve_column_by_tokens(lowered, profile.measure_columns, context)
            if measure_token_match:
                return measure_token_match
        if intent_name in {"distinct_values", "representation_ranking"}:
            for alias, resolved_name in dimension_aliases.items():
                if alias in lowered:
                    return resolved_name
            dimension_token_match = self._resolve_column_by_tokens(lowered, profile.dimension_columns, context)
            if dimension_token_match:
                return dimension_token_match
        return None

    def _resolve_column_by_tokens(
        self,
        lowered_question: str,
        column_names: list[str],
        context: SourceContext | None,
    ) -> str | None:
        candidate_names = list(column_names)
        if context:
            candidate_names.extend(context.metric_definitions)
            candidate_names.extend(context.field_descriptions)
        seen: set[str] = set()
        for candidate_name in candidate_names:
            if candidate_name in seen:
                continue
            seen.add(candidate_name)
            tokens = [token for token in re.split(r"[_\s]+", candidate_name.lower()) if len(token) >= 3]
            if tokens and all(re.search(rf"\b{re.escape(token)}\b", lowered_question) for token in tokens):
                return candidate_name
        return None

    def _extract_aggregation(self, question: str) -> str | None:
        lowered = question.lower()
        for aggregation, keywords in AGGREGATION_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return aggregation
        return None

    def _extract_time_reference(self, question: str) -> dict[str, str] | None:
        lowered = question.lower()
        for month_index in range(1, 13):
            month = month_name[month_index].lower()
            abbreviation = month_abbr[month_index].lower()
            if re.search(rf"\b{month}\b", lowered) or re.search(rf"\b{abbreviation}\b", lowered):
                return {"type": "month_name", "value": month, "month": str(month_index)}
        quarter_match = re.search(r"\bq([1-4])\b", lowered)
        if quarter_match:
            return {"type": "quarter", "value": quarter_match.group(0), "quarter": quarter_match.group(1)}
        if "this year" in lowered and "last year" in lowered:
            return {"type": "relative_period", "value": "this_year"}
        if "this year" in lowered:
            return {"type": "relative_period", "value": "this_year"}
        if "last year" in lowered:
            return {"type": "relative_period", "value": "last_year"}
        if "this quarter" in lowered and "last quarter" in lowered:
            return {"type": "relative_period", "value": "this_quarter"}
        if "last quarter" in lowered:
            return {"type": "relative_period", "value": "last_quarter"}
        if "this quarter" in lowered:
            return {"type": "relative_period", "value": "this_quarter"}
        if "this month" in lowered and "last month" in lowered:
            return {"type": "relative_period", "value": "this_month"}
        if "last month" in lowered:
            return {"type": "relative_period", "value": "last_month"}
        if "this month" in lowered:
            return {"type": "relative_period", "value": "this_month"}
        return None

    def _extract_horizon(self, question: str) -> int | None:
        match = re.search(r"\b(\d+)\s+(?:months|month|periods|steps)\b", question.lower())
        if not match:
            return None
        value = int(match.group(1))
        return value if value > 0 else None

    def _extract_group_by(self, question: str, profile: DatasetProfile) -> list[str] | None:
        lowered = question.lower()
        matches: list[str] = []

        if " by " in lowered:
            _, suffix = lowered.split(" by ", 1)
            matches.extend(column for column in profile.dimension_columns if column.lower() in suffix)

        for trigger in ("per ", "across ", "for each "):
            if trigger in lowered:
                _, suffix = lowered.split(trigger, 1)
                matches.extend(column for column in profile.dimension_columns if column.lower() in suffix)

        matches = list(dict.fromkeys(matches))
        return matches or None

    def _extract_selected_columns(
        self,
        question: str,
        profile: DatasetProfile,
        filters: dict[str, object] | None,
    ) -> list[str] | None:
        lowered = question.lower()
        named_columns = self._extract_named_columns(question, profile)
        if not named_columns:
            return None
        if any(phrase in lowered for phrase in {"all rows", "all records", "all entries", "full rows", "entire rows"}):
            return None
        filter_columns = set(filters or {})
        if any(keyword in lowered for keyword in TABULAR_ROW_KEYWORDS):
            if len(named_columns) == 1 and any(keyword in lowered for keyword in TABULAR_SORT_KEYWORDS):
                return None
            non_filter_columns = [column for column in named_columns if column not in filter_columns]
            if non_filter_columns:
                return non_filter_columns
            return None
        return named_columns

    def _extract_sort_request(
        self,
        question: str,
        profile: DatasetProfile,
        target: str | None,
        group_by: list[str] | None,
    ) -> tuple[str | None, str]:
        lowered = question.lower()
        explicit_sort_match = re.search(r"\b(?:sort(?:ed)?|order(?:ed)?)\s+by\s+([a-z0-9_ ]+)", lowered)
        if explicit_sort_match:
            candidate_name = explicit_sort_match.group(1).strip()
            candidate_name = re.split(r"\b(?:ascending|descending|asc|desc)\b", candidate_name, maxsplit=1)[0].strip()
            resolved_column = self._resolve_candidate_column(candidate_name, profile, None)
            if resolved_column:
                direction = "desc" if re.search(r"\b(desc|descending)\b", lowered) else "asc"
                return resolved_column, direction

        if "latest" in lowered and profile.time_columns:
            return profile.time_columns[0], "desc"
        if "earliest" in lowered and profile.time_columns:
            return profile.time_columns[0], "asc"
        if re.search(r"\b(desc|descending)\b", lowered):
            if group_by and target:
                return target, "desc"
            if target:
                return target, "desc"
        if re.search(r"\b(asc|ascending)\b", lowered):
            if group_by and target:
                return target, "asc"
            if target:
                return target, "asc"
        return None, "asc"

    def _extract_tabular_limit(self, question: str) -> int | None:
        lowered = question.lower()
        patterns = [
            r"\b(?:first|last|return|show|list)\s+(\d+)\s+rows?\b",
            r"\b(?:return|show|list)\s+(\d+)\s+records?\b",
            r"\b(?:first|last)\s+(\d+)\b",
            r"\b(?:give me|show|return|list)\s+(\d+)\s+[a-z0-9_ ]+\s+from\s+the\s+data\s*set\b",
            r"\b(?:give me|show|return|list)\s+(\d+)\s+[a-z0-9_ ]+\s+from\s+the\s+dataset\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                value = int(match.group(1))
                return value if value > 0 else None
        ranking_request = self._extract_ranking_request(question)
        if ranking_request is None:
            return None
        _, limit = ranking_request
        return limit

    def _extract_page_number(self, question: str) -> int:
        match = re.search(r"\bpage\s+(\d+)\b", question.lower())
        if not match:
            return 1
        value = int(match.group(1))
        return value if value > 0 else 1

    def _extract_page_size(self, question: str) -> int | None:
        lowered = question.lower()
        patterns = [
            r"\bpage size\s+(\d+)\b",
            r"\b(\d+)\s+per page\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                value = int(match.group(1))
                return value if value > 0 else None
        return None

    def _extract_ranking_request(self, question: str) -> tuple[str, int] | None:
        lowered = question.lower()
        patterns = [
            r"\b(top|bottom)\s+(\d+)\b",
            r"\b(top|bottom)\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            direction = "desc" if match.group(1) == "top" else "asc"
            count_token = match.group(2)
            limit = int(count_token) if count_token.isdigit() else RANKING_NUMBER_WORDS[count_token]
            return direction, limit
        return None

    def _extract_statistical_group_by(
        self,
        question: str,
        profile: DatasetProfile,
        target: str | None,
    ) -> list[str] | None:
        named_columns = self._extract_named_columns(question, profile)
        if not named_columns:
            return None
        return [column for column in named_columns if column != target] or None

    def _extract_filters(
        self,
        question: str,
        profile: DatasetProfile,
        context: SourceContext | None,
    ) -> dict[str, object] | None:
        lowered = question.lower()
        filters: dict[str, object] = {}

        for dimension in profile.dimension_columns:
            pattern = rf"\b{re.escape(dimension)}\s*=\s*([a-z0-9_\- ]+)"
            match = re.search(pattern, question, flags=re.IGNORECASE)
            if match:
                filters[dimension] = match.group(1).strip()

        candidate_values = self._candidate_filter_values(profile, context)
        for column_name, values in candidate_values.items():
            for value in values:
                if not value:
                    continue
                match = re.search(rf"\b{re.escape(value.lower())}\b", lowered)
                if not match:
                    continue
                operator = self._contextual_filter_operator(lowered, match.start())
                if column_name not in filters:
                    filters[column_name] = self._build_filter_value(operator, value)

        for column_name, implied_value in self._flag_filter_aliases(profile).items():
            match = re.search(rf"\b{re.escape(column_name.lower())}\b", lowered)
            if not match:
                continue
            profile_column = f"{column_name}_flag" if f"{column_name}_flag" in {column.name for column in profile.columns} else None
            resolved_column = profile_column or next(
                (
                    column.name
                    for column in profile.columns
                    if column.name.lower() == column_name.lower() or column.name.lower() == f"{column_name.lower()}_flag"
                ),
                None,
            )
            if resolved_column and resolved_column not in filters:
                operator = self._contextual_filter_operator(lowered, match.start())
                filters[resolved_column] = self._build_filter_value(operator, implied_value)

        membership_match = re.search(
            r"\bis\s+([a-z0-9_\- ]+?)\s+in\s+the\s+([a-z0-9_ ]+?)\s+column\b",
            question,
            flags=re.IGNORECASE,
        )
        if membership_match:
            requested_value = membership_match.group(1).strip()
            requested_column = membership_match.group(2).strip().lower()
            profile_columns = {column.name.lower(): column.name for column in profile.columns}
            resolved_column = profile_columns.get(requested_column)
            if resolved_column and requested_value:
                filters[resolved_column] = requested_value

        time_column = profile.time_columns[0] if profile.time_columns else None
        if time_column and self._should_extract_time_filter(lowered):
            year_match = re.search(r"\b(?:in|for|during)\s+((?:19|20)\d{2})\b", lowered)
            if year_match:
                filters[time_column] = {"op": "year_eq", "value": int(year_match.group(1))}
            else:
                time_reference = self._extract_time_reference(question)
                month_match = re.search(
                    r"\b(?:in|for|during)\s+("
                    + "|".join(re.escape(month_name[index].lower()) for index in range(1, 13))
                    + r"|"
                    + "|".join(re.escape(month_abbr[index].lower()) for index in range(1, 13))
                    + r")\b",
                    lowered,
                )
                if month_match and time_reference and time_reference.get("type") == "month_name":
                    filters[time_column] = {
                        "op": "month_eq",
                        "value": int(time_reference["month"]),
                        "label": time_reference["value"],
                    }

        return filters or None

    def _candidate_filter_values(
        self,
        profile: DatasetProfile,
        context: SourceContext | None,
    ) -> dict[str, list[str]]:
        candidate_values: dict[str, list[str]] = {}

        for column in profile.columns:
            if not column.is_dimension_candidate:
                continue
            values = []
            for sample in column.sample_values:
                if isinstance(sample, str):
                    values.append(sample)
            candidate_values[column.name] = values

        if context:
            for field_name in context.field_descriptions:
                candidate_values.setdefault(field_name, [])

        return candidate_values

    def _flag_filter_aliases(self, profile: DatasetProfile) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for column in profile.columns:
            if not column.is_dimension_candidate:
                continue
            if column.name.lower().endswith("_flag"):
                sample_values = {str(value).lower() for value in column.sample_values if isinstance(value, str)}
                if {"yes", "no"}.issubset(sample_values):
                    aliases[column.name[:-5]] = "yes"
        return aliases

    def _contextual_filter_operator(self, lowered_question: str, value_start: int) -> str:
        window_start = max(0, value_start - 24)
        context_window = lowered_question[window_start:value_start]
        if any(keyword in context_window for keyword in {"exclude ", "excluding ", "without ", "except ", "not "}):
            return "neq"
        return "eq"

    def _build_filter_value(self, operator: str, value: str) -> object:
        if operator == "neq":
            return {"op": "neq", "value": value}
        return value

    def _should_extract_time_filter(self, lowered: str) -> bool:
        if any(keyword in lowered for keyword in TIME_COMPARISON_KEYWORDS):
            return False
        if any(keyword in lowered for keyword in {"by month", "by year", "by quarter", "per month", "per year", "per quarter"}):
            return False
        if any(keyword in lowered for keyword in {"why", "drop", "decline", "decrease", "trend"}):
            return False
        return True

    def _validate_task_type(self, task_type_hint: str | None) -> str | None:
        if task_type_hint in TASK_LABELS:
            return task_type_hint
        return None

    def _validate_aggregation(self, aggregation: str | None) -> str | None:
        if aggregation in AGGREGATION_KEYWORDS:
            return aggregation
        return None

    def _apply_statistical_options(
        self,
        question: str,
        profile: DatasetProfile,
        options: dict[str, object],
    ) -> None:
        statistical_test = self._extract_statistical_test(question)
        if statistical_test is None:
            statistical_test = self._infer_statistical_test(question, profile)
        if statistical_test is None:
            return

        options["statistical_test"] = statistical_test
        options["alpha"] = self._extract_alpha(question)
        options["confidence_level"] = self._extract_confidence_level(question)
        options["desired_power"] = self._extract_desired_power(question)

        named_columns = self._extract_named_columns(question, profile)
        if statistical_test == "chi_square" and len(named_columns) >= 2:
            options["comparison_columns"] = named_columns[:2]
        if statistical_test == "regression_significance":
            regression_target, feature_columns = self._extract_regression_columns(question, profile)
            if regression_target and feature_columns:
                options["regression_target"] = regression_target
                options["feature_columns"] = feature_columns
            elif len(named_columns) >= 2:
                options["feature_columns"] = named_columns[1:]

    def _extract_statistical_test(self, question: str) -> str | None:
        lowered = question.lower()
        for test_name, keywords in STATISTICAL_TEST_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return test_name
        return None

    def _infer_statistical_test(self, question: str, profile: DatasetProfile) -> str | None:
        lowered = question.lower()
        named_columns = self._extract_named_columns(question, profile)
        named_measures = [column for column in named_columns if column in profile.measure_columns]
        named_dimensions = [column for column in named_columns if column in profile.dimension_columns]

        if self._looks_like_sample_size_request(lowered) and named_measures and named_dimensions:
            return "sample_size_estimate"
        if self._looks_like_power_analysis_request(lowered) and named_measures and named_dimensions:
            return "power_analysis"
        if self._looks_like_confidence_interval_request(lowered) and named_measures:
            return "confidence_interval"
        regression_target, feature_columns = self._extract_regression_columns(question, profile)
        if regression_target and feature_columns:
            return "regression_significance"
        if self._looks_like_significance_inference_request(lowered, named_measures, named_dimensions):
            return "significance_inference"
        return None

    def _looks_like_significance_inference_request(
        self,
        lowered: str,
        named_measures: list[str],
        named_dimensions: list[str],
    ) -> bool:
        if named_measures and named_dimensions and any(keyword in lowered for keyword in SIGNIFICANCE_COMPARISON_KEYWORDS):
            return True
        return bool(
            named_measures
            and named_dimensions
            and any(keyword in lowered for keyword in NATURAL_SIGNIFICANCE_COMPARISON_KEYWORDS)
        )

    def _looks_like_confidence_interval_request(self, lowered: str) -> bool:
        if any(keyword in lowered for keyword in NATURAL_CONFIDENCE_INTERVAL_KEYWORDS):
            return True
        return "confidence" in lowered and any(keyword in lowered for keyword in {"interval", "range", "bounds"})

    def _looks_like_power_analysis_request(self, lowered: str) -> bool:
        return any(keyword in lowered for keyword in NATURAL_POWER_ANALYSIS_KEYWORDS)

    def _looks_like_sample_size_request(self, lowered: str) -> bool:
        return any(keyword in lowered for keyword in NATURAL_SAMPLE_SIZE_KEYWORDS)

    def _extract_regression_columns(
        self,
        question: str,
        profile: DatasetProfile,
    ) -> tuple[str | None, list[str]]:
        lowered = question.lower()
        for keyword in NATURAL_REGRESSION_SIGNIFICANCE_KEYWORDS:
            if keyword not in lowered:
                continue
            before, after = lowered.split(keyword, 1)
            feature_candidates = self._extract_named_columns(before, profile)
            target_candidates = self._extract_named_columns(after, profile)
            feature_columns = [column for column in feature_candidates if column in profile.measure_columns]
            target_columns = [column for column in target_candidates if column in profile.measure_columns]
            if feature_columns and target_columns:
                return target_columns[0], feature_columns
        return None, []

    def _extract_named_columns(self, question: str, profile: DatasetProfile) -> list[str]:
        lowered = question.lower()
        matches: list[tuple[int, str]] = []
        for column in profile.columns:
            patterns = [rf"\b{re.escape(column.name.lower())}\b"]
            if "_" not in column.name:
                patterns.append(rf"\b{re.escape(column.name.lower())}s\b")
            match = None
            for pattern in patterns:
                match = re.search(pattern, lowered)
                if match:
                    break
            if match:
                matches.append((match.start(), column.name))
        matches.sort(key=lambda item: item[0])
        ordered_names = [column_name for _, column_name in matches]
        return list(dict.fromkeys(ordered_names))

    def _extract_alpha(self, question: str) -> float:
        lowered = question.lower()
        if "1%" in lowered:
            return 0.01
        if "10%" in lowered:
            return 0.10
        return 0.05

    def _extract_confidence_level(self, question: str) -> float:
        match = re.search(r"\b(\d{2})%\s+confidence\b", question.lower())
        if not match:
            return 0.95
        level = int(match.group(1)) / 100.0
        return level if 0.0 < level < 1.0 else 0.95

    def _extract_desired_power(self, question: str) -> float:
        match = re.search(r"\b(\d{2})%\s+power\b", question.lower())
        if not match:
            return 0.80
        power = int(match.group(1)) / 100.0
        return power if 0.0 < power < 1.0 else 0.80

    def _detect_intent_name(self, question: str, profile: DatasetProfile) -> str | None:
        lowered = question.lower()
        if self._looks_like_single_column_type_lookup(question, profile):
            return "column_type_inventory"
        if self._looks_like_column_type_inventory_request(lowered):
            return "column_type_inventory"
        if any(keyword in lowered for keyword in ROW_COUNT_KEYWORDS):
            return "row_count"
        if self._looks_like_tabular_query_request(question, profile):
            return "tabular_query"
        if self._looks_like_existence_request(question, profile):
            return "existence_check"
        if self._looks_like_numeric_column_inventory_request(lowered):
            return "numeric_column_inventory"
        if self._looks_like_categorical_column_inventory_request(lowered):
            return "categorical_column_inventory"
        if any(keyword in lowered for keyword in MISSING_VALUE_INVENTORY_KEYWORDS) and not self._looks_like_column_specific_null_check(question, profile):
            return "missing_value_inventory"
        if any(keyword in lowered for keyword in IDENTIFIER_INVENTORY_KEYWORDS):
            return "identifier_inventory"
        if any(keyword in lowered for keyword in HIGH_CARDINALITY_INVENTORY_KEYWORDS):
            return "high_cardinality_inventory"
        if "columns" in lowered and any(keyword in lowered for keyword in {"available", "what are", "which", "show"}):
            return "column_inventory"
        if any(keyword in lowered for keyword in {"measure columns", "metrics available", "available metrics"}):
            return "measure_inventory"
        if any(keyword in lowered for keyword in {"dimension columns", "available dimensions", "grouping columns"}):
            return "dimension_inventory"
        if self._looks_like_time_column_inventory_request(lowered):
            return "time_column_inventory"
        if self._looks_like_time_bucket_count_request(question):
            return "time_bucket_counts"
        if self._looks_like_time_period_comparison_request(question, profile):
            return "time_period_comparison"
        if self._looks_like_time_bucket_breakdown_request(question, profile):
            return "time_bucket_breakdown"
        if self._looks_like_time_coverage_request(question):
            return "time_coverage"
        if self._looks_like_distinct_values_request(question) or self._looks_like_dimension_category_request(question, profile):
            return "distinct_values"
        if self._looks_like_representation_request(question, profile):
            return "representation_ranking"
        return None

    def _looks_like_column_type_inventory_request(self, lowered: str) -> bool:
        if "schema" in lowered:
            return True
        if not any(keyword in lowered for keyword in COLUMN_TYPE_INVENTORY_KEYWORDS):
            return False
        return any(keyword in lowered for keyword in {"column", "columns", "field", "fields", "data"})

    def _looks_like_single_column_type_lookup(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        named_columns = self._extract_named_columns(question, profile)
        if len(named_columns) != 1:
            return False
        if "schema" in lowered:
            return False
        if any(keyword in lowered for keyword in {"all fields", "all columns", "each field", "each column"}):
            return False
        singular_markers = {
            "what is the data type of",
            "what's the data type of",
            "data type of",
            "dtype of",
            "what is the type of",
            "what's the type of",
            "type of",
            "what type is",
        }
        if any(marker in lowered for marker in singular_markers):
            return True
        if any(keyword in lowered for keyword in COLUMN_TYPE_INVENTORY_KEYWORDS):
            return any(keyword in lowered for keyword in {" column ", " field ", " column?", " field?", " column.", " field."})
        return False

    def _looks_like_numeric_column_inventory_request(self, lowered: str) -> bool:
        if any(keyword in lowered for keyword in NUMERIC_COLUMN_INVENTORY_KEYWORDS):
            return True
        return any(keyword in lowered for keyword in {"numeric", "numerical"}) and any(
            keyword in lowered for keyword in {"column", "columns", "field", "fields"}
        )

    def _looks_like_categorical_column_inventory_request(self, lowered: str) -> bool:
        if any(keyword in lowered for keyword in CATEGORICAL_COLUMN_INVENTORY_KEYWORDS):
            return True
        return any(keyword in lowered for keyword in {"categorical", "category", "text", "string"}) and any(
            keyword in lowered for keyword in {"column", "columns", "field", "fields"}
        )

    def _looks_like_time_column_inventory_request(self, lowered: str) -> bool:
        return any(keyword in lowered for keyword in {"time", "date", "dates", "datetime"}) and any(
            keyword in lowered for keyword in {"column", "columns", "field", "fields"}
        )

    def _looks_like_tabular_query_request(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        has_group_by = bool(self._extract_group_by(question, profile))
        named_columns = self._extract_named_columns(question, profile)
        has_tabular_surface = any(keyword in lowered for keyword in TABULAR_ROW_KEYWORDS | TABULAR_SURFACE_KEYWORDS)
        has_sort_or_limit = any(keyword in lowered for keyword in TABULAR_SORT_KEYWORDS) or self._extract_tabular_limit(question) is not None
        has_tabular_verb = any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in TABULAR_VERBS)
        has_dataset_slice_language = (
            self._extract_tabular_limit(question) is not None
            and has_tabular_verb
            and "from" in lowered
            and any(keyword in lowered for keyword in DATASET_SLICE_KEYWORDS)
        )

        if has_tabular_surface:
            return True
        if has_dataset_slice_language:
            return True
        if has_sort_or_limit and (has_tabular_verb or bool(named_columns)):
            return True
        if has_group_by and "table" in lowered:
            return True
        if not has_group_by and has_tabular_verb and len(named_columns) >= 2:
            return True
        return False

    def _looks_like_representation_request(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        has_representation_language = any(keyword in lowered for keyword in REPRESENTATION_LOW_KEYWORDS | REPRESENTATION_HIGH_KEYWORDS)
        if not has_representation_language and lowered.strip().startswith(("which ", "what ")):
            has_representation_language = any(
                phrase in lowered
                for phrase in {
                    "has the most",
                    "has most",
                    "has the fewest",
                    "has the least",
                    "has highest count",
                    "has lowest count",
                }
            )
        if not has_representation_language:
            return False
        if any(column.lower() in lowered for column in profile.measure_columns):
            return False
        return any(column.lower() in lowered for column in profile.dimension_columns)

    def _representation_direction(self, question: str) -> str:
        lowered = question.lower()
        if any(
            keyword in lowered
            for keyword in REPRESENTATION_LOW_KEYWORDS | {"has the fewest", "has the least", "fewest", "least"}
        ):
            return "asc"
        return "desc"

    def _extract_column_presence_target(self, question: str, profile: DatasetProfile) -> str | None:
        lowered = question.lower()
        if "column" not in lowered and "field" not in lowered:
            return None
        if not any(
            phrase in lowered
            for phrase in {"have", "has", "contains", "contain", "include", "includes", "is there", "are there"}
        ):
            return None

        named_columns = self._extract_named_columns(question, profile)
        if len(named_columns) == 1:
            return named_columns[0]

        patterns = [
            r"\b(?:have|has|contains|contain|include|includes)\s+(?:an?\s+|the\s+)?([a-z0-9_ ]+?)\s+(?:column|field)\b",
            r"\b(?:is there|are there)\s+(?:an?\s+|the\s+)?([a-z0-9_ ]+?)\s+(?:column|field)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            candidate = match.group(1).strip()
            if not candidate:
                continue
            return self._resolve_requested_column_name(candidate, profile)
        return None

    def _extract_property_check_target(self, question: str, profile: DatasetProfile) -> str | None:
        expected_property = self._extract_expected_property(question)
        if expected_property is None:
            return None

        resolved_target = self._resolve_target(question, profile, None, "existence_check")
        if resolved_target is not None:
            return resolved_target

        lowered = question.lower().strip()
        patterns = [
            r"^is\s+([a-z0-9_ ]+?)\s+(?:a|an)\s+(?:datetime|numeric|categorical|identifier|dimension|measure)\b",
            r"^is\s+([a-z0-9_ ]+?)\s+high\s+cardinality\b",
            r"^is\s+([a-z0-9_ ]+?)\s+likely\s+an\s+identifier\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            candidate = match.group(1).strip()
            if candidate:
                return self._resolve_requested_column_name(candidate, profile)
        return None

    def _looks_like_distinct_values_request(self, question: str) -> bool:
        lowered = question.lower()
        return any(keyword in lowered for keyword in DISTINCT_VALUE_KEYWORDS)

    def _looks_like_dimension_category_request(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        if not any(keyword in lowered for keyword in DISTINCT_VALUE_CATEGORY_KEYWORDS):
            return False
        return any(column.lower() in lowered for column in profile.dimension_columns)

    def _looks_like_time_coverage_request(self, question: str) -> bool:
        lowered = question.lower()
        all_keywords = TIME_COVERAGE_YEAR_KEYWORDS | TIME_COVERAGE_MONTH_KEYWORDS | TIME_COVERAGE_RANGE_KEYWORDS
        return any(keyword in lowered for keyword in all_keywords)

    def _looks_like_time_bucket_count_request(self, question: str) -> bool:
        lowered = question.lower()
        has_count_language = any(keyword in lowered for keyword in {"how many", "count", "number of"})
        if not has_count_language:
            return False
        year_request = any(keyword in lowered for keyword in TIME_BUCKET_COUNT_YEAR_KEYWORDS)
        month_request = any(keyword in lowered for keyword in TIME_BUCKET_COUNT_MONTH_KEYWORDS)
        quarter_request = any(keyword in lowered for keyword in TIME_BUCKET_COUNT_QUARTER_KEYWORDS)
        return year_request or month_request or quarter_request

    def _looks_like_time_bucket_breakdown_request(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        if any(keyword in lowered for keyword in TIME_COMPARISON_KEYWORDS):
            return False
        has_measure_language = any(column.lower() in lowered for column in profile.measure_columns) or bool(
            self._extract_aggregation(question)
        )
        if not has_measure_language:
            return False
        return any(keyword in lowered for keyword in (
            TIME_BUCKET_BREAKDOWN_YEAR_KEYWORDS
            | TIME_BUCKET_BREAKDOWN_MONTH_KEYWORDS
            | TIME_BUCKET_BREAKDOWN_QUARTER_KEYWORDS
        ))

    def _looks_like_time_period_comparison_request(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        if not any(keyword in lowered for keyword in TIME_COMPARISON_KEYWORDS):
            return False
        has_measure_language = any(column.lower() in lowered for column in profile.measure_columns) or bool(
            self._extract_aggregation(question)
        )
        if not has_measure_language:
            return False
        time_reference = self._extract_time_reference(question)
        if time_reference is not None:
            return True
        return any(keyword in lowered for keyword in {"month", "quarter", "year"})

    def _looks_like_existence_request(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        starts_like_boolean_check = lowered.strip().startswith(("is ", "are ", "does ", "do "))
        if not starts_like_boolean_check and not any(keyword in lowered for keyword in EXISTENCE_REQUEST_KEYWORDS):
            return False
        if self._extract_column_presence_target(question, profile) is not None:
            return True
        target = self._resolve_target(question, profile, None, "existence_check")
        year_value = self._extract_year_value(question)
        if year_value is not None and profile.time_columns:
            if target in set(profile.time_columns) or "date" in lowered or "dates" in lowered:
                return True
        if self._extract_null_expectation(question) is not None and target is not None:
            return True
        if self._extract_threshold_check_spec(question) is not None and target is not None:
            return True
        if self._extract_property_check_target(question, profile) is not None:
            return True
        filters = self._extract_filters(question, profile, None)
        return bool(filters)

    def _resolve_single_column_type_target(
        self,
        question: str,
        profile: DatasetProfile,
    ) -> str | None:
        if not self._looks_like_single_column_type_lookup(question, profile):
            return None
        named_columns = self._extract_named_columns(question, profile)
        if len(named_columns) != 1:
            return None
        return named_columns[0]

    def _looks_like_column_specific_null_check(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        if self._extract_null_expectation(question) is None:
            return False
        if not lowered.strip().startswith(("is ", "are ", "does ", "do ")):
            return False
        return self._resolve_target(question, profile, None, "existence_check") is not None

    def _time_coverage_mode(self, question: str) -> str:
        lowered = question.lower()
        if any(keyword in lowered for keyword in TIME_COVERAGE_YEAR_KEYWORDS):
            return "years_present"
        if any(keyword in lowered for keyword in TIME_COVERAGE_MONTH_KEYWORDS):
            return "months_present"
        return "date_range"

    def _time_bucket_mode(self, question: str) -> str:
        lowered = question.lower()
        if any(keyword in lowered for keyword in TIME_BUCKET_COUNT_QUARTER_KEYWORDS | TIME_BUCKET_BREAKDOWN_QUARTER_KEYWORDS):
            return "quarter"
        if any(keyword in lowered for keyword in TIME_BUCKET_COUNT_MONTH_KEYWORDS):
            return "month"
        if any(keyword in lowered for keyword in TIME_BUCKET_BREAKDOWN_MONTH_KEYWORDS):
            return "month"
        if any(keyword in lowered for keyword in {"this month", "last month"}):
            return "month"
        if any(keyword in lowered for keyword in {"this quarter", "last quarter"}):
            return "quarter"
        if any(keyword in lowered for keyword in {"this year", "last year"}):
            return "year"
        return "year"

    def _resolve_existence_mode(
        self,
        question: str,
        profile: DatasetProfile,
        target: str | None,
        filters: dict[str, str] | None,
    ) -> str:
        lowered = question.lower()
        if self._extract_year_value(question) is not None and profile.time_columns:
            if target in set(profile.time_columns) or "date" in lowered or "dates" in lowered:
                return "time_value"
        if self._extract_column_presence_target(question, profile) is not None:
            return "column_presence_check"
        if self._extract_null_expectation(question) is not None and target is not None:
            return "null_check"
        if self._extract_threshold_check_spec(question) is not None and target is not None:
            return "threshold_check"
        if self._extract_property_check_target(question, profile) is not None:
            return "column_property_check"
        return "filtered_rows"

    def _extract_null_expectation(self, question: str) -> str | None:
        lowered = question.lower()
        if any(keyword in lowered for keyword in COMPLETE_CHECK_KEYWORDS):
            return "no_nulls"
        if any(keyword in lowered for keyword in NULL_CHECK_KEYWORDS):
            return "has_nulls"
        return None

    def _extract_threshold_check_spec(self, question: str) -> dict[str, object] | None:
        lowered = question.lower()
        between_match = re.search(r"\bbetween\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)\b", lowered)
        if between_match:
            lower_bound = float(between_match.group(1))
            upper_bound = float(between_match.group(2))
            if lower_bound > upper_bound:
                lower_bound, upper_bound = upper_bound, lower_bound
            return {"threshold_operator": "between", "lower_bound": lower_bound, "upper_bound": upper_bound}

        threshold_patterns = {
            "gt": r"\b(?:above|over|greater than|more than)\s+(-?\d+(?:\.\d+)?)\b",
            "gte": r"\b(?:at least|greater than or equal to|no less than)\s+(-?\d+(?:\.\d+)?)\b",
            "lt": r"\b(?:below|under|less than)\s+(-?\d+(?:\.\d+)?)\b",
            "lte": r"\b(?:at most|less than or equal to|no more than)\s+(-?\d+(?:\.\d+)?)\b",
        }
        for operator, pattern in threshold_patterns.items():
            match = re.search(pattern, lowered)
            if match:
                return {"threshold_operator": operator, "threshold_value": float(match.group(1))}
        return None

    def _extract_expected_property(self, question: str) -> str | None:
        lowered = question.lower()
        if any(keyword in lowered for keyword in HIGH_CARDINALITY_PROPERTY_KEYWORDS):
            return "high_cardinality"
        if any(keyword in lowered for keyword in DIMENSION_PROPERTY_KEYWORDS):
            return "dimension"
        if any(keyword in lowered for keyword in MEASURE_PROPERTY_KEYWORDS):
            return "measure"
        if any(keyword in lowered for keyword in IDENTIFIER_PROPERTY_KEYWORDS):
            return "identifier"
        if any(keyword in lowered for keyword in DATETIME_PROPERTY_KEYWORDS):
            return "datetime"
        if any(keyword in lowered for keyword in NUMERIC_PROPERTY_KEYWORDS):
            return "numeric"
        if any(keyword in lowered for keyword in CATEGORICAL_PROPERTY_KEYWORDS):
            return "categorical"
        return None

    def _extract_year_value(self, question: str) -> int | None:
        match = re.search(r"\b(19|20)\d{2}\b", question)
        if not match:
            return None
        return int(match.group(0))

    def _should_list_distinct_values(
        self,
        question: str,
        target: str | None,
        profile: DatasetProfile,
    ) -> bool:
        if not target:
            return False
        if target not in profile.dimension_columns:
            return False
        if self._extract_aggregation(question):
            return False
        return self._looks_like_distinct_values_request(question) or self._looks_like_dimension_category_request(question, profile)

    def _build_request_options(self, dataset_name: str, intent_name: str | None) -> dict[str, object]:
        return {
            "dataset": dataset_name,
            "intent_name": intent_name,
        }

    def _resolve_requested_column_name(self, candidate_name: str, profile: DatasetProfile) -> str:
        normalized = candidate_name.strip().lower()
        profile_columns = {column.name.lower(): column.name for column in profile.columns}
        if normalized in profile_columns:
            return profile_columns[normalized]
        underscored = normalized.replace(" ", "_")
        if underscored in profile_columns:
            return profile_columns[underscored]
        return underscored

    def _resolve_ranking_intent(
        self,
        question: str,
        intent_name: str | None,
        target: str | None,
        group_by: list[str] | None,
        profile: DatasetProfile,
        options: dict[str, object],
    ) -> str | None:
        ranking_request = self._extract_ranking_request(question)
        if ranking_request is None or target is None:
            return intent_name
        direction, limit = ranking_request
        options["ranking_direction"] = direction
        options["ranking_limit"] = limit
        if group_by:
            return "group_ranking"
        if target in profile.measure_columns:
            return "row_ranking"
        return intent_name

    def _resolve_tabular_intent(
        self,
        question: str,
        intent_name: str | None,
        target: str | None,
        group_by: list[str] | None,
        selected_columns: list[str] | None,
        filters: dict[str, object] | None,
        aggregation: str | None,
    ) -> str | None:
        if intent_name in {"row_ranking", "group_ranking", "time_bucket_counts", "time_bucket_breakdown", "time_period_comparison"}:
            return intent_name
        if intent_name != "tabular_query":
            return intent_name
        lowered = question.lower()
        if group_by and ("table" in lowered or "tabular" in lowered or aggregation or target):
            return "grouped_tabular_query"
        if group_by and not any(keyword in lowered for keyword in TABULAR_ROW_KEYWORDS | TABULAR_SURFACE_KEYWORDS):
            return intent_name
        if selected_columns or filters or any(keyword in lowered for keyword in TABULAR_ROW_KEYWORDS | TABULAR_SURFACE_KEYWORDS):
            return "tabular_query"
        return intent_name

    def _looks_like_grouped_entity_count_request(
        self,
        question: str,
        target: str | None,
        group_by: list[str] | None,
        profile: DatasetProfile,
    ) -> bool:
        if not group_by or not target:
            return False
        if target not in set(group_by):
            return False
        if target in set(profile.measure_columns):
            return False

        lowered = question.lower()
        return any(keyword in lowered for keyword in {"count", "how many", "number of", "total"})

    def _resolve_candidate_column(
        self,
        candidate_name: str | None,
        profile: DatasetProfile,
        context: SourceContext | None,
    ) -> str | None:
        if not candidate_name:
            return None
        lowered_candidate = candidate_name.lower().strip()
        measure_map = {column.lower(): column for column in profile.measure_columns}
        if lowered_candidate in measure_map:
            return measure_map[lowered_candidate]
        profile_columns = {column.name.lower(): column.name for column in profile.columns}
        if lowered_candidate in profile_columns:
            return profile_columns[lowered_candidate]
        if context:
            metric_map = {metric_name.lower(): metric_name for metric_name in context.metric_definitions}
            if lowered_candidate in metric_map:
                resolved = metric_map[lowered_candidate]
                return profile_columns.get(resolved.lower(), resolved)
        return None

    def _resolve_candidate_group_by(
        self,
        group_by: list[str] | None,
        profile: DatasetProfile,
    ) -> list[str] | None:
        if not group_by:
            return None
        profile_columns = {column.name.lower(): column.name for column in profile.columns}
        resolved: list[str] = []
        for candidate_name in group_by:
            lowered_candidate = candidate_name.lower().strip()
            if lowered_candidate in profile_columns:
                resolved.append(profile_columns[lowered_candidate])
        return list(dict.fromkeys(resolved)) or None

    def _resolve_candidate_filters(
        self,
        filters: dict[str, object] | None,
        profile: DatasetProfile,
    ) -> dict[str, object] | None:
        if not filters:
            return None
        profile_columns = {column.name.lower(): column.name for column in profile.columns}
        resolved: dict[str, object] = {}
        for column_name, value in filters.items():
            lowered_column = column_name.lower().strip()
            if lowered_column not in profile_columns:
                continue
            if isinstance(value, str) and value.strip():
                resolved[profile_columns[lowered_column]] = value.strip()
                continue
            if isinstance(value, dict):
                operator = value.get("op")
                if operator in {"neq", "year_eq", "month_eq"} and value.get("value") is not None:
                    resolved_value = {"op": operator, "value": value.get("value")}
                    if value.get("label") is not None:
                        resolved_value["label"] = str(value["label"])
                    resolved[profile_columns[lowered_column]] = resolved_value
        return resolved or None

    def _resolve_candidate_time_reference(self, time_reference: dict[str, str] | None) -> dict[str, str] | None:
        if not time_reference:
            return None
        if not isinstance(time_reference, dict):
            return None
        time_type = time_reference.get("type")
        if time_type not in {"month_name", "quarter", "relative_period"}:
            return None
        return {str(key): str(value) for key, value in time_reference.items() if value is not None}


RequestNormalizer = InputCanonicalizer
