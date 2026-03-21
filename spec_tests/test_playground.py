from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd

PLAYGROUND_PATH = Path(__file__).resolve().parents[1] / "playground"
if str(PLAYGROUND_PATH) not in sys.path:
    sys.path.insert(0, str(PLAYGROUND_PATH))

import run_analysis_openai as openai_playground
import run_analysis_openai_json_yellow as openai_playground_json_yellow


class _FakeEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def analyze(self, dataset: object, question: str) -> object:
        _ = dataset
        self.calls.append(question)
        payload = {
            "schema_version": "saida.response.v2",
            "result": {
                "value": {
                    "rows": [{"ticket_id": "T1"}],
                }
            },
        }
        return SimpleNamespace(
            summary="Please clarify the target metric.",
            tables=[],
            warnings=[],
            plan=SimpleNamespace(task_type="clarification"),
            to_response_dict=lambda: payload,
        )


def test_openai_playground_exits_cleanly_from_clarification_prompt(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine()
    dataset = SimpleNamespace(name="sales", data=pd.DataFrame({"revenue": [1.0]}))

    monkeypatch.setattr(openai_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(openai_playground.os, "getenv", lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default)
    monkeypatch.setattr(openai_playground.CSVSource, "load", lambda self: dataset)
    monkeypatch.setattr(openai_playground, "Saida", lambda config=None: fake_engine)

    answers = iter(["Hi there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    openai_playground.main()
    output = capsys.readouterr().out

    assert "Please answer the clarification above, or type 'exit' to quit." in output
    assert fake_engine.calls == ["Hi there"]


def test_openai_playground_json_mode_prints_structured_contract(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine()
    dataset = SimpleNamespace(name="sales", data=pd.DataFrame({"revenue": [1.0]}))

    monkeypatch.setattr(openai_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(openai_playground.os, "getenv", lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default)
    monkeypatch.setattr(openai_playground.CSVSource, "load", lambda self: dataset)
    monkeypatch.setattr(openai_playground, "Saida", lambda config=None: fake_engine)
    monkeypatch.setattr(openai_playground.sys, "argv", ["run_analysis_openai.py", "--json"])

    answers = iter(["Hi there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    openai_playground.main()
    output = capsys.readouterr().out

    assert '"schema_version": "saida.response.v2"' in output
    assert "\033[33m" in output
    assert '"ticket_id": "T1"' in output


def test_openai_yellow_json_playground_prints_yellow_structured_contract(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine()
    dataset = SimpleNamespace(name="sales", data=pd.DataFrame({"revenue": [1.0]}))

    monkeypatch.setattr(openai_playground_json_yellow, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(
        openai_playground_json_yellow.os,
        "getenv",
        lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default,
    )
    monkeypatch.setattr(openai_playground_json_yellow.CSVSource, "load", lambda self: dataset)
    monkeypatch.setattr(openai_playground_json_yellow, "Saida", lambda config=None: fake_engine)

    answers = iter(["Hi there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    openai_playground_json_yellow.main()
    output = capsys.readouterr().out

    assert '"schema_version": "saida.response.v2"' in output
    assert "\033[33m" in output
    assert '"ticket_id": "T1"' in output
