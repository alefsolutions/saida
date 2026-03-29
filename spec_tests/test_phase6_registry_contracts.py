from __future__ import annotations

from saida.core import get_analytics_registry


def test_registry_methods_expose_artifact_contract_fields_for_scalar_method() -> None:
    registry = get_analytics_registry()

    method = registry.get_method("row_count")

    assert method is not None
    assert method.input_artifact_kinds == ("dataset", "frame")
    assert method.output_artifact_kinds == ("scalar",)
    assert method.consumes == ("dataset",)
    assert method.node_kind == "source"
    assert method.default_output_kind == "scalar"


def test_registry_methods_expose_mixed_output_contracts_for_diagnostic_summary() -> None:
    registry = get_analytics_registry()

    method = registry.get_method("dataset_summary")

    assert method is not None
    assert method.output_shapes == ("table", "scalar")
    assert method.output_artifact_kinds == ("frame", "scalar")
    assert method.default_output_kind == "frame"


def test_registry_methods_map_special_output_shapes_to_runtime_artifact_kinds() -> None:
    registry = get_analytics_registry()

    verification_method = registry.get_method("row_existence")
    statistical_method = registry.get_method("significance_inference")
    forecast_method = registry.get_method("forecast")

    assert verification_method is not None
    assert verification_method.output_artifact_kinds == ("verification",)
    assert statistical_method is not None
    assert statistical_method.output_artifact_kinds == ("frame",)
    assert forecast_method is not None
    assert forecast_method.output_artifact_kinds == ("forecast",)
    assert forecast_method.default_output_kind == "forecast"


def test_registry_method_to_dict_includes_artifact_contract_fields() -> None:
    registry = get_analytics_registry()

    payload = registry.get_method("grouped_tabular_query").to_dict()

    assert payload["input_artifact_kinds"] == ["dataset", "frame"]
    assert payload["output_artifact_kinds"] == ["frame"]
    assert payload["consumes"] == ["dataset"]
    assert payload["node_kind"] == "source"
    assert payload["default_output_kind"] == "frame"
