from __future__ import annotations

from saida import Saida
from saida.outputs import JsonOutputAdapter, OutputInterface, SummaryOutputAdapter
from .factories import build_basic_row_count_plan, build_support_dataset


def _build_core_result() -> object:
    engine = Saida()
    dataset = build_support_dataset()
    plan = build_basic_row_count_plan(dataset.name)
    return engine.execute_plan(dataset, plan)


def test_json_output_adapter_implements_output_interface() -> None:
    result = _build_core_result()
    adapter = JsonOutputAdapter()

    payload = adapter.render(result)

    assert isinstance(adapter, OutputInterface)
    assert adapter.output_format == "json"
    assert payload == result.to_response_dict()


def test_summary_output_adapter_implements_output_interface() -> None:
    result = _build_core_result()
    adapter = SummaryOutputAdapter()

    summary_text = adapter.render(result)

    assert isinstance(adapter, OutputInterface)
    assert adapter.output_format == "summary"
    assert summary_text == result.summary


def test_engine_render_output_uses_registered_json_adapter() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.execute_plan(dataset, build_basic_row_count_plan(dataset.name))

    payload = engine.render_output(result, output_format="json")

    assert payload == result.to_response_dict()


def test_engine_render_output_uses_registered_summary_adapter() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.execute_plan(dataset, build_basic_row_count_plan(dataset.name))

    payload = engine.render_output(result, output_format="summary")

    assert payload == result.summary
