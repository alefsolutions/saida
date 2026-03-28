from saida.core import AnalysisRequest, ColumnProfile, DatasetProfile, build_default_analytics_registry
from saida.plan_generation import build_prompt_capability_contract


def build_profile() -> DatasetProfile:
    columns = [
        ColumnProfile(
            name="posted_at",
            inferred_type="datetime",
            nullable=False,
            null_ratio=0.0,
            unique_count=12,
            distinct_ratio=1.0,
            sample_values=["2026-01-01"],
            is_time_candidate=True,
        ),
        ColumnProfile(
            name="revenue",
            inferred_type="float",
            nullable=False,
            null_ratio=0.0,
            unique_count=12,
            distinct_ratio=1.0,
            sample_values=[100.0],
            is_measure_candidate=True,
        ),
        ColumnProfile(
            name="region",
            inferred_type="category",
            nullable=False,
            null_ratio=0.0,
            unique_count=4,
            distinct_ratio=0.3,
            sample_values=["West"],
            is_dimension_candidate=True,
        ),
    ]
    return DatasetProfile(
        dataset_name="sales",
        row_count=12,
        column_count=3,
        columns=columns,
        measure_columns=["revenue"],
        dimension_columns=["region"],
        time_columns=["posted_at"],
        identifier_columns=[],
    )


def test_default_analytics_registry_exposes_graph_like_relationships() -> None:
    registry = build_default_analytics_registry()

    assert registry.get_concept("top_n_by_metric") is not None
    assert registry.get_concept("requires_metric") is not None
    assert "requires_metric" in registry.related("top_n_by_metric", "requires")
    assert "ranked_breakdown" in registry.related("top_n_by_metric", "uses")


def test_prompt_capability_contract_marks_supported_time_comparison_as_feasible() -> None:
    contract = build_prompt_capability_contract(
        AnalysisRequest(
            question="Compare revenue this quarter to last quarter",
            intent_name="time_period_comparison",
            task_type_hint="descriptive",
            target="revenue",
            time_reference={"type": "relative_period", "value": "this_quarter"},
        ),
        build_profile(),
    )

    assert contract.status == "supported_and_data_feasible"
    assert "period_over_period_comparison" in contract.selected_capabilities


def test_prompt_capability_contract_marks_missing_grouping_as_partial_fallback() -> None:
    contract = build_prompt_capability_contract(
        AnalysisRequest(
            question="Do regions differ in revenue?",
            task_type_hint="statistical",
            target="revenue",
            options={"statistical_test": "significance_inference"},
        ),
        build_profile(),
    )

    assert contract.status == "supported_with_partial_fallback"
    assert "group_by" in contract.missing_parameters
