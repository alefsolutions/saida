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
import run_analysis_sqlite_sales_40 as sqlite_playground


class _FakeEngine:
    def __init__(
        self,
        *,
        status: str = "ok",
        task_type: str = "descriptive",
        summary: str = "Returned ticket rows.",
    ) -> None:
        self.calls: list[str] = []
        self.status = status
        self.task_type = task_type
        self.summary = summary

    def analyze(self, dataset: object, question: str) -> object:
        _ = dataset
        self.calls.append(question)
        payload = {
            "schema_version": "saida.response.v2",
            "status": self.status,
            "interpretation": {
                "options": {"clarification_reason": "ambiguous_metric_target"},
                "capability_contract": {
                    "status": "supported_with_partial_fallback",
                    "selected_capabilities": ["descriptive"],
                }
            },
            "result": {
                "name": "empty_result" if self.status == "clarify" else "tabular_query",
                "value": {
                    "rows": [{"ticket_id": "T1"}],
                },
            } if self.status != "clarify" else {
                "name": "empty_result",
                "value": None,
            },
            "reasoning": {"summary": self.summary},
        }
        return SimpleNamespace(
            summary=self.summary,
            tables=[],
            warnings=[],
            plan=SimpleNamespace(task_type=self.task_type),
            to_response_dict=lambda: payload,
        )


def test_openai_playground_exits_cleanly_from_clarification_prompt(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine(status="clarify", task_type="clarification", summary="Please clarify the target metric.")
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


def test_openai_playground_reuses_original_request_for_clarification_follow_up(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine(status="clarify", task_type="clarification", summary="Please clarify the target metric.")
    dataset = SimpleNamespace(name="sales", data=pd.DataFrame({"revenue": [1.0]}))

    monkeypatch.setattr(openai_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(openai_playground.os, "getenv", lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default)
    monkeypatch.setattr(openai_playground.CSVSource, "load", lambda self: dataset)
    monkeypatch.setattr(openai_playground, "Saida", lambda config=None: fake_engine)

    answers = iter(["How many columns?", "Count the dataset fields", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    openai_playground.main()
    _ = capsys.readouterr().out

    assert fake_engine.calls == [
        "How many columns?",
        "Original request: How many columns?\nClarification answer: Count the dataset fields",
    ]


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


def test_openai_yellow_json_playground_prints_full_response_payload(
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

    assert "\033[33m" in output
    assert '"schema_version": "saida.response.v2"' in output
    assert '"result"' in output
    assert '"interpretation"' in output
    assert '"ticket_id": "T1"' in output


def test_openai_yellow_json_playground_renders_clarification_summary_in_result_mode(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine(status="clarify", task_type="clarification", summary="Please clarify the target metric.")
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

    assert '"status": "clarify"' in output
    assert '"summary": "Please clarify the target metric."' in output
    assert '"clarification_reason": "ambiguous_metric_target"' in output
    assert '"name": "empty_result"' in output


def test_openai_yellow_json_playground_can_render_capability_contract(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine()
    dataset = SimpleNamespace(name="sales", data=pd.DataFrame({"revenue": [1.0]}))

    monkeypatch.setattr(openai_playground_json_yellow, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(
        openai_playground_json_yellow.os,
        "getenv",
        lambda key, default=None: "contract" if key == "SAIDA_PLAYGROUND_OUTPUT_MODE" else ("test-key" if key == "OPENAI_API_KEY" else default),
    )
    monkeypatch.setattr(openai_playground_json_yellow.CSVSource, "load", lambda self: dataset)
    monkeypatch.setattr(openai_playground_json_yellow, "Saida", lambda config=None: fake_engine)

    answers = iter(["Hi there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    openai_playground_json_yellow.main()
    output = capsys.readouterr().out

    assert '"status": "supported_with_partial_fallback"' in output
    assert '"selected_capabilities"' in output


def test_sqlite_playground_prints_summary_for_loaded_sqlite_dataset(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine(summary="The dataset contains 40 rows.")
    dataset = SimpleNamespace(name="sales_sqlite_40", data=pd.DataFrame({"total_sales": [1.0]}))

    monkeypatch.setattr(sqlite_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(sqlite_playground.os, "getenv", lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default)
    monkeypatch.setattr(sqlite_playground.SQLiteSource, "load", lambda self: dataset)
    monkeypatch.setattr(sqlite_playground, "Saida", lambda config=None: fake_engine)

    answers = iter(["How many rows are there?", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    sqlite_playground.main()
    output = capsys.readouterr().out

    assert "SAIDA OpenAI SQLite playground" in output
    assert "Dataset: sales_sqlite_40" in output
    assert "The dataset contains 40 rows." in output
    assert fake_engine.calls == ["How many rows are there?"]
