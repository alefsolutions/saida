from __future__ import annotations

from saida import Saida
from saida.outputs import JsonOutputAdapter, OutputInterface, SummaryOutputAdapter
from .factories import build_support_dataset


def test_json_output_adapter_implements_output_interface() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.analyze(dataset, "How many rows do we have?")
    adapter = JsonOutputAdapter()

    payload = adapter.render(result)

    assert isinstance(adapter, OutputInterface)
    assert adapter.output_format == "json"
    assert payload == result.to_response_dict()


def test_summary_output_adapter_implements_output_interface() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.analyze(dataset, "How many rows do we have?")
    adapter = SummaryOutputAdapter()

    summary_text = adapter.render(result)

    assert isinstance(adapter, OutputInterface)
    assert adapter.output_format == "summary"
    assert summary_text == result.summary


def test_engine_render_output_uses_registered_json_adapter() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.analyze(dataset, "How many rows do we have?")

    payload = engine.render_output(result, output_format="json")

    assert payload == result.to_response_dict()


def test_engine_render_output_uses_registered_summary_adapter() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    result = engine.analyze(dataset, "How many rows do we have?")

    payload = engine.render_output(result, output_format="summary")

    assert payload == result.summary
