from __future__ import annotations

from saida.core import get_analytics_registry


def test_transform_registry_exposes_graph_native_duckdb_methods() -> None:
    registry = get_analytics_registry()

    expected_methods = {
        "filter_frame": "selection_filtering",
        "select_columns": "selection_filtering",
        "sort_frame": "selection_filtering",
        "limit_frame": "selection_filtering",
        "distinct_frame": "selection_filtering",
        "derive_column": "transformation",
        "group_frame": "transformation",
        "aggregate_frame": "transformation",
        "time_bucket_frame": "transformation",
        "rank_frame": "ranking",
    }

    for method_id, family_id in expected_methods.items():
        method = registry.get_method(method_id)

        assert method is not None
        assert method.family_id == family_id
        assert method.default_tool_family == "duckdb"
        assert method.output_artifact_kinds == ("frame",)
        assert method.default_output_kind == "frame"


def test_transform_registry_declares_required_contracts_for_key_methods() -> None:
    registry = get_analytics_registry()

    select_columns = registry.get_method("select_columns")
    aggregate_frame = registry.get_method("aggregate_frame")
    time_bucket_frame = registry.get_method("time_bucket_frame")

    assert select_columns is not None
    assert select_columns.required_inputs == ("dataset", "selected_columns")
    assert aggregate_frame is not None
    assert aggregate_frame.required_inputs == ("dataset", "aggregation")
    assert time_bucket_frame is not None
    assert time_bucket_frame.required_inputs == ("dataset", "time_column", "bucket")
