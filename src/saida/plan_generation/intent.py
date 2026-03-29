"""Intent helpers for schema-aware prompt normalization."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from saida.core.contracts import DatasetProfile
from saida.plan_generation.entities import EntityExtractionResult

_WORD_CHARS = "a-z0-9_"


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![{_WORD_CHARS}]){re.escape(phrase.lower())}(?![{_WORD_CHARS}])", text) is not None


@dataclass(slots=True)
class FrontendIntent:
    """Typed frontend intent derived from a masked prompt surface."""

    operation: str | None = None
    object_kind: str | None = None
    object_ref: str | None = None
    expected_result_shape: str | None = None
    source: str = "rules"
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = {
            "operation": self.operation,
            "object_kind": self.object_kind,
            "object_ref": self.object_ref,
            "expected_result_shape": self.expected_result_shape,
            "source": self.source,
        }
        return {key: value for key, value in payload.items() if value is not None and value != []}


class PromptIntentResolver:
    """Resolve operator-like intent from a masked question surface."""

    def __init__(
        self,
        *,
        aggregation_keywords: dict[str, set[str]],
        unsafe_count_keywords: set[str],
        distinct_count_keywords: set[str],
        row_count_phrases: set[str],
        property_keywords: dict[str, set[str]],
    ) -> None:
        self.aggregation_keywords = aggregation_keywords
        self.unsafe_count_keywords = unsafe_count_keywords
        self.distinct_count_keywords = distinct_count_keywords
        self.row_count_phrases = row_count_phrases
        self.property_keywords = property_keywords

    def contains_any(self, surface: EntityExtractionResult, keywords: set[str]) -> bool:
        return any(_contains_phrase(surface.masked_lower_question, keyword) for keyword in keywords)

    def extract_aggregation(self, surface: EntityExtractionResult) -> str | None:
        for aggregation, keywords in self.aggregation_keywords.items():
            if self.contains_any(surface, keywords):
                return aggregation
        return None

    def contains_unsafe_count_language(self, surface: EntityExtractionResult) -> bool:
        return self.contains_any(surface, self.unsafe_count_keywords)

    def extract_expected_property(self, surface: EntityExtractionResult) -> str | None:
        for property_name, keywords in self.property_keywords.items():
            if self.contains_any(surface, keywords):
                return property_name
        return None

    def derive_semantic_intent(
        self,
        surface: EntityExtractionResult,
        profile: DatasetProfile,
        intent_name: str | None,
        target: str | None,
        aggregation: str | None,
        group_by: list[str] | None,
        statistical_test: str | None,
    ) -> FrontendIntent | None:
        if statistical_test is not None:
            return None

        countish = _contains_phrase(surface.masked_lower_question, "count") or self.contains_unsafe_count_language(surface)
        if self.contains_any(surface, self.row_count_phrases):
            return FrontendIntent(
                operation="count",
                object_kind="rows",
                expected_result_shape="count",
                evidence=["row_count_language"],
            )
        if countish and target is not None and target in set(profile.dimension_columns) and self.contains_any(surface, self.distinct_count_keywords):
            return FrontendIntent(
                operation="count",
                object_kind="distinct_values",
                object_ref=target,
                expected_result_shape="count",
                evidence=["distinct_count_language"],
            )
        if intent_name == "row_count":
            return FrontendIntent(
                operation="count",
                object_kind="rows",
                expected_result_shape="count",
                evidence=["intent_name=row_count"],
            )
        if intent_name == "tabular_query":
            return FrontendIntent(
                operation="list",
                object_kind="rows",
                expected_result_shape="recordset",
                evidence=["intent_name=tabular_query"],
            )
        if intent_name == "distinct_value_count" and target is not None:
            return FrontendIntent(
                operation="count",
                object_kind="distinct_values",
                object_ref=target,
                expected_result_shape="count",
                evidence=["intent_name=distinct_value_count"],
            )
        if intent_name == "distinct_values" and target is not None:
            return FrontendIntent(
                operation="list",
                object_kind="distinct_values",
                object_ref=target,
                expected_result_shape="table",
                evidence=["intent_name=distinct_values"],
            )

        metadata_count_mapping = {
            "column_count": "columns",
            "numeric_column_count": "numeric_columns",
            "categorical_column_count": "categorical_columns",
            "measure_count": "measure_columns",
            "dimension_count": "dimension_columns",
            "time_column_count": "time_columns",
            "identifier_count": "identifier_columns",
            "high_cardinality_count": "high_cardinality_columns",
        }
        object_kind = metadata_count_mapping.get(intent_name or "")
        if object_kind is not None:
            return FrontendIntent(
                operation="count",
                object_kind=object_kind,
                expected_result_shape="count",
                evidence=[f"intent_name={intent_name}"],
            )

        if aggregation in {"sum", "mean", "max", "min"} and target is not None and target in set(profile.measure_columns):
            return FrontendIntent(
                operation=aggregation,
                object_kind="measure",
                object_ref=target,
                expected_result_shape="aggregate",
                evidence=["aggregate_measure_request"],
            )

        if group_by and target is not None and aggregation == "count":
            return FrontendIntent(
                operation="count",
                object_kind="rows",
                expected_result_shape="table",
                evidence=["grouped_row_count_request"],
            )
        return None
