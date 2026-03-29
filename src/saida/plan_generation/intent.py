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

    intent_name: str | None = None
    operation: str | None = None
    object_kind: str | None = None
    object_ref: str | None = None
    expected_result_shape: str | None = None
    group_refs: list[str] = field(default_factory=list)
    time_bucket: str | None = None
    presentation: str | None = None
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
        time_bucket_keywords: dict[str, set[str]],
    ) -> None:
        self.aggregation_keywords = aggregation_keywords
        self.unsafe_count_keywords = unsafe_count_keywords
        self.distinct_count_keywords = distinct_count_keywords
        self.row_count_phrases = row_count_phrases
        self.property_keywords = property_keywords
        self.time_bucket_keywords = time_bucket_keywords

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

    def extract_time_bucket(self, surface: EntityExtractionResult) -> str | None:
        for bucket, keywords in self.time_bucket_keywords.items():
            if self.contains_any(surface, keywords):
                return bucket
        return None

    def resolve_group_refs(
        self,
        surface: EntityExtractionResult,
        profile: DatasetProfile,
        group_by: list[str] | None,
        target: str | None,
        ranking_requested: bool,
    ) -> list[str]:
        resolved: list[str] = list(group_by or [])
        dimension_mentions = [
            column
            for column in surface.ordered_columns
            if column in set(profile.dimension_columns) and column != target
        ]
        if not resolved and ranking_requested and dimension_mentions:
            resolved.extend(dimension_mentions)
        return list(dict.fromkeys(resolved))

    def derive_semantic_intent(
        self,
        surface: EntityExtractionResult,
        profile: DatasetProfile,
        intent_name: str | None,
        target: str | None,
        aggregation: str | None,
        group_by: list[str] | None,
        statistical_test: str | None,
        ranking_requested: bool = False,
    ) -> FrontendIntent | None:
        if statistical_test is not None:
            return None

        countish = _contains_phrase(surface.masked_lower_question, "count") or self.contains_unsafe_count_language(surface)
        time_bucket = self.extract_time_bucket(surface)
        resolved_group_refs = self.resolve_group_refs(surface, profile, group_by, target, ranking_requested)
        aggregate_operation = aggregation if aggregation in {"sum", "mean", "max", "min"} else None

        if ranking_requested and target is not None and target in set(profile.measure_columns):
            if resolved_group_refs:
                return FrontendIntent(
                    intent_name="group_ranking",
                    operation=aggregate_operation or "sum",
                    object_kind="measure",
                    object_ref=target,
                    expected_result_shape="table",
                    group_refs=resolved_group_refs,
                    presentation="group_ranking",
                    evidence=["ranking_request", "group_dimension_resolved"],
                )
            return FrontendIntent(
                intent_name="row_ranking",
                operation=aggregate_operation,
                object_kind="measure",
                object_ref=target,
                expected_result_shape="table",
                presentation="row_ranking",
                evidence=["ranking_request"],
            )

        if time_bucket is not None:
            if target is not None and target in set(profile.measure_columns) and (aggregate_operation is not None or intent_name == "time_bucket_breakdown"):
                return FrontendIntent(
                    intent_name="time_bucket_breakdown",
                    operation=aggregate_operation or "sum",
                    object_kind="measure",
                    object_ref=target,
                    expected_result_shape="table",
                    group_refs=resolved_group_refs,
                    time_bucket=time_bucket,
                    presentation="time_bucket_breakdown",
                    evidence=["time_bucket", "aggregate_measure_request"],
                )
            if target is None and (countish or intent_name in {"row_count", "time_bucket_counts"}):
                return FrontendIntent(
                    intent_name="time_bucket_counts",
                    operation="count",
                    object_kind="rows",
                    expected_result_shape="table",
                    time_bucket=time_bucket,
                    presentation="time_bucket_counts",
                    evidence=["time_bucket", "count_request"],
                )

        if (
            resolved_group_refs
            and target is not None
            and target in set(profile.measure_columns)
            and intent_name in {"tabular_query", "grouped_tabular_query"}
        ):
            return FrontendIntent(
                intent_name="grouped_tabular_query",
                operation=aggregate_operation or "sum",
                object_kind="measure",
                object_ref=target,
                expected_result_shape="table",
                group_refs=resolved_group_refs,
                presentation="grouped_aggregate",
                evidence=["group_by", "aggregate_measure_request"],
            )

        grouped_dimension_target = (
            target is not None
            and target in set(resolved_group_refs)
            and target in set(profile.dimension_columns)
        )
        if resolved_group_refs and (
            countish or intent_name in {"row_count", "tabular_query", "grouped_tabular_query"}
        ) and (target is None or grouped_dimension_target):
            return FrontendIntent(
                intent_name="grouped_tabular_query",
                operation="count",
                object_kind="rows",
                expected_result_shape="table",
                group_refs=resolved_group_refs,
                presentation="grouped_count",
                evidence=["group_by", "count_request"],
            )

        if self.contains_any(surface, self.row_count_phrases):
            return FrontendIntent(
                intent_name="row_count",
                operation="count",
                object_kind="rows",
                expected_result_shape="count",
                evidence=["row_count_language"],
            )
        if countish and target is not None and target in set(profile.dimension_columns) and self.contains_any(surface, self.distinct_count_keywords):
            return FrontendIntent(
                intent_name="distinct_value_count",
                operation="count",
                object_kind="distinct_values",
                object_ref=target,
                expected_result_shape="count",
                evidence=["distinct_count_language"],
            )
        if intent_name == "row_count":
            return FrontendIntent(
                intent_name="row_count",
                operation="count",
                object_kind="rows",
                expected_result_shape="count",
                evidence=["intent_name=row_count"],
            )
        if intent_name == "tabular_query":
            return FrontendIntent(
                intent_name="tabular_query",
                operation="list",
                object_kind="rows",
                expected_result_shape="recordset",
                presentation="row_retrieval",
                evidence=["intent_name=tabular_query"],
            )
        if intent_name == "distinct_value_count" and target is not None:
            return FrontendIntent(
                intent_name="distinct_value_count",
                operation="count",
                object_kind="distinct_values",
                object_ref=target,
                expected_result_shape="count",
                evidence=["intent_name=distinct_value_count"],
            )
        if intent_name == "distinct_values" and target is not None:
            return FrontendIntent(
                intent_name="distinct_values",
                operation="list",
                object_kind="distinct_values",
                object_ref=target,
                expected_result_shape="table",
                presentation="dimension_listing",
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
                intent_name=intent_name,
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
                intent_name="grouped_tabular_query",
                operation="count",
                object_kind="rows",
                expected_result_shape="table",
                group_refs=list(group_by),
                presentation="grouped_count",
                evidence=["grouped_row_count_request"],
            )
        return None
