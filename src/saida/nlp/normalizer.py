"""Structured request normalization with a transformer hook."""

from __future__ import annotations

import re
from calendar import month_name
from calendar import month_abbr

from saida.config import NlpConfig
from saida.exceptions import ValidationError
from saida.llm import IntentProposal
from saida.schemas import AnalysisRequest, Dataset, DatasetProfile, SourceContext

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


class RequestNormalizer:
    """Convert raw text into a structured AnalysisRequest."""

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
        self._apply_statistical_options(question, profile, options)
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
        if intent_name == "time_coverage":
            options["time_coverage_mode"] = self._time_coverage_mode(question)
            target = None
            aggregation = None
            group_by = None
        if options.get("statistical_test") in {"chi_square", "regression_significance"}:
            group_by = self._extract_statistical_group_by(question, profile, target)

        if intent_name == "representation_ranking" and target is not None:
            group_by = [target]
            aggregation = "count"
            options["ranking_direction"] = self._representation_direction(question)

        if target is None and profile.measure_columns and intent_name not in {"row_count", "column_inventory", "measure_inventory", "dimension_inventory", "time_column_inventory", "time_coverage"}:
            warnings.append("No explicit metric matched the prompt; using the first measure candidate.")
            target = profile.measure_columns[0]
        if target is None and not profile.measure_columns and intent_name not in {"row_count", "column_inventory", "measure_inventory", "dimension_inventory", "time_column_inventory", "time_coverage"}:
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
        return request, warnings

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
        if rule_intent_name == "time_coverage":
            options["time_coverage_mode"] = self._time_coverage_mode(question)
            target = None
            aggregation = None
            group_by = None
        if options.get("statistical_test") in {"chi_square", "regression_significance"}:
            group_by = self._extract_statistical_group_by(question, profile, target)
        if rule_intent_name == "representation_ranking" and target is not None:
            group_by = [target]
            aggregation = "count"
            options["ranking_direction"] = self._representation_direction(question)

        if target is None and profile.measure_columns and rule_intent_name not in {"row_count", "column_inventory", "measure_inventory", "dimension_inventory", "time_column_inventory", "time_coverage"}:
            warnings.append("No explicit metric matched the prompt; using the first measure candidate.")
            target = profile.measure_columns[0]
        if target is None and not profile.measure_columns and rule_intent_name not in {"row_count", "column_inventory", "measure_inventory", "dimension_inventory", "time_column_inventory", "time_coverage"}:
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
                "nlp_backend": "llm+validation",
                "llm_status": proposal.status,
                "distinct_values": distinct_values,
            },
        )
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
            warnings.append("Transformers pipeline not available; falling back to deterministic request rules.")
            return current_label

        try:
            classifier = pipeline("zero-shot-classification", model=self.config.zero_shot_model)
            result = classifier(question, TASK_LABELS, multi_label=False)
        except Exception:
            warnings.append("Transformer classification failed; falling back to deterministic request rules.")
            return current_label

        label = result["labels"][0]
        score = float(result["scores"][0])
        if score < self.config.confidence_threshold:
            warnings.append("Transformer NLP confidence was low; retaining rule-based intent classification.")
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

        for alias, resolved_name in measure_aliases.items():
            if alias in lowered:
                return resolved_name
        if intent_name in {"distinct_values", "representation_ranking"}:
            for alias, resolved_name in dimension_aliases.items():
                if alias in lowered:
                    return resolved_name
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
        if "last quarter" in lowered:
            return {"type": "relative_period", "value": "last_quarter"}
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
    ) -> dict[str, str] | None:
        lowered = question.lower()
        filters: dict[str, str] = {}

        for dimension in profile.dimension_columns:
            pattern = rf"\b{re.escape(dimension.lower())}\s*=\s*([a-z0-9_\- ]+)"
            match = re.search(pattern, lowered)
            if match:
                filters[dimension] = match.group(1).strip()

        candidate_values = self._candidate_filter_values(profile, context)
        for column_name, values in candidate_values.items():
            for value in values:
                if value and re.search(rf"\b{re.escape(value.lower())}\b", lowered):
                    filters[column_name] = value

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
            match = re.search(rf"\b{re.escape(column.name.lower())}\b", lowered)
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
        if "columns" in lowered and any(keyword in lowered for keyword in {"available", "what are", "which", "show"}):
            return "column_inventory"
        if any(keyword in lowered for keyword in {"measure columns", "metrics available", "available metrics"}):
            return "measure_inventory"
        if any(keyword in lowered for keyword in {"dimension columns", "available dimensions", "grouping columns"}):
            return "dimension_inventory"
        if any(keyword in lowered for keyword in {"time columns", "date columns", "datetime columns"}):
            return "time_column_inventory"
        if self._looks_like_time_coverage_request(question):
            return "time_coverage"
        if any(keyword in lowered for keyword in ROW_COUNT_KEYWORDS):
            return "row_count"
        if self._looks_like_distinct_values_request(question) or self._looks_like_dimension_category_request(question, profile):
            return "distinct_values"
        if self._looks_like_representation_request(question, profile):
            return "representation_ranking"
        return None

    def _looks_like_representation_request(self, question: str, profile: DatasetProfile) -> bool:
        lowered = question.lower()
        has_representation_language = any(keyword in lowered for keyword in REPRESENTATION_LOW_KEYWORDS | REPRESENTATION_HIGH_KEYWORDS)
        if not has_representation_language:
            return False
        return any(column.lower() in lowered for column in profile.dimension_columns)

    def _representation_direction(self, question: str) -> str:
        lowered = question.lower()
        if any(keyword in lowered for keyword in REPRESENTATION_LOW_KEYWORDS):
            return "asc"
        return "desc"

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

    def _time_coverage_mode(self, question: str) -> str:
        lowered = question.lower()
        if any(keyword in lowered for keyword in TIME_COVERAGE_YEAR_KEYWORDS):
            return "years_present"
        if any(keyword in lowered for keyword in TIME_COVERAGE_MONTH_KEYWORDS):
            return "months_present"
        return "date_range"

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
        filters: dict[str, str] | None,
        profile: DatasetProfile,
    ) -> dict[str, str] | None:
        if not filters:
            return None
        profile_columns = {column.name.lower(): column.name for column in profile.columns}
        resolved: dict[str, str] = {}
        for column_name, value in filters.items():
            lowered_column = column_name.lower().strip()
            if lowered_column in profile_columns and isinstance(value, str) and value.strip():
                resolved[profile_columns[lowered_column]] = value.strip()
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
