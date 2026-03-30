from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

import pandas as pd

PLAYGROUND_PATH = Path(__file__).resolve().parents[3] / "playground"
if str(PLAYGROUND_PATH) not in sys.path:
    sys.path.insert(0, str(PLAYGROUND_PATH))

import run_analysis_openai as openai_playground
import run_analysis_openai_json_yellow as openai_playground_json_yellow


def _load_module(module_name: str, relative_path: str):
    module_path = PLAYGROUND_PATH / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load playground module at {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


example1_playground = _load_module(
    "example1_playground",
    "example1/run/run_prompt_analysis.py",
)
example2_playground = _load_module(
    "example2_playground",
    "example2/run/run_prompt_analysis.py",
)
example3_playground = _load_module(
    "example3_playground",
    "example3/run/run_authored_plan.py",
)


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
                "prompt_contract": {
                    "status": "supported_with_partial_fallback",
                    "selected_capabilities": ["descriptive"],
                },
            },
            "result": {
                "name": "empty_result" if self.status == "clarify" else "tabular_query",
                "value": {
                    "rows": [{"ticket_id": "T1"}],
                },
            }
            if self.status != "clarify"
            else {
                "name": "empty_result",
                "value": None,
            },
            "summary": {"summary": self.summary},
        }
        return SimpleNamespace(
            summary=self.summary,
            tables=[],
            warnings=[],
            plan=SimpleNamespace(task_type=self.task_type),
            to_response_dict=lambda: payload,
        )

    def analyze_source(self, source: object, question: str) -> object:
        return self.analyze(source, question)


def test_openai_playground_exits_cleanly_from_clarification_prompt(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine(status="clarify", task_type="clarification", summary="Please clarify the target metric.")
    dataset = SimpleNamespace(name="sales", data=pd.DataFrame({"revenue": [1.0]}))

    monkeypatch.setattr(openai_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(openai_playground.os, "getenv", lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default)
    monkeypatch.setattr(openai_playground.CSVSource, "load", lambda self: dataset)
    monkeypatch.setattr(openai_playground, "PromptAnalysisFrontend", lambda config=None: fake_engine)

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
    monkeypatch.setattr(openai_playground, "PromptAnalysisFrontend", lambda config=None: fake_engine)

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
    monkeypatch.setattr(openai_playground, "PromptAnalysisFrontend", lambda config=None: fake_engine)
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
    monkeypatch.setattr(openai_playground_json_yellow, "PromptAnalysisFrontend", lambda config=None: fake_engine)

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
    monkeypatch.setattr(openai_playground_json_yellow, "PromptAnalysisFrontend", lambda config=None: fake_engine)

    answers = iter(["Hi there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    openai_playground_json_yellow.main()
    output = capsys.readouterr().out

    assert '"status": "clarify"' in output
    assert '"summary": "Please clarify the target metric."' in output
    assert '"clarification_reason": "ambiguous_metric_target"' in output
    assert '"name": "empty_result"' in output


def test_openai_yellow_json_playground_can_render_prompt_contract(
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
    monkeypatch.setattr(openai_playground_json_yellow, "PromptAnalysisFrontend", lambda config=None: fake_engine)

    answers = iter(["Hi there", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    openai_playground_json_yellow.main()
    output = capsys.readouterr().out

    assert '"status": "supported_with_partial_fallback"' in output
    assert '"selected_capabilities"' in output


def test_example2_playground_prints_summary_for_loaded_sqlite_dataset(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine(summary="The dataset contains 40 rows.")

    monkeypatch.setattr(example2_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(example2_playground.os, "getenv", lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default)
    monkeypatch.setattr(example2_playground, "PromptAnalysisFrontend", lambda config=None: fake_engine)

    answers = iter(["How many rows are there?", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    example2_playground.main()
    output = capsys.readouterr().out

    assert "SAIDA Example 2: OpenAI sqlite sales 40 rows" in output
    assert "Dataset: sales_sqlite_40" in output
    assert "Mode: source-aware relational materialization" in output
    assert "\033[33m" in output
    assert "The dataset contains 40 rows." in output
    assert '"schema_version": "saida.response.v2"' not in output
    assert fake_engine.calls == ["How many rows are there?"]


def test_example1_playground_prints_summary_for_loaded_csv_dataset(
    monkeypatch: object,
    capsys: object,
) -> None:
    fake_engine = _FakeEngine(summary="Returned the latest sales rows.")
    dataset = SimpleNamespace(name="sales_data_800_rows", data=pd.DataFrame({"revenue": [1.0]}))

    monkeypatch.setattr(example1_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(example1_playground.os, "getenv", lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default)
    monkeypatch.setattr(example1_playground.CSVSource, "load", lambda self: dataset)
    monkeypatch.setattr(example1_playground, "PromptAnalysisFrontend", lambda config=None: fake_engine)

    answers = iter(["Show the latest 5 rows", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    example1_playground.main()
    output = capsys.readouterr().out

    assert "SAIDA Example 1: OpenAI sales CSV 800 rows" in output
    assert "Dataset: sales_data_800_rows" in output
    assert "Returned the latest sales rows." in output
    assert fake_engine.calls == ["Show the latest 5 rows"]


def test_example2_playground_renders_tabular_rows_line_by_line(
    monkeypatch: object,
    capsys: object,
) -> None:
    class _FakeTabularEngine:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def analyze(self, dataset: object, question: str) -> object:
            _ = dataset
            self.calls.append(question)
            payload = {
                "schema_version": "saida.response.v2",
                "status": "ok",
                "interpretation": {"prompt_family": "tabular_record_retrieval"},
                "result": {
                    "name": "tabular_query",
                    "physical_shape": "recordset",
                    "value": [
                        {"order_id": "ORD-040", "country": "United States", "total_sales": 464.5},
                        {"order_id": "ORD-039", "country": "Germany", "total_sales": 323.0},
                    ],
                },
                "summary": {"summary": "Returned the latest sales rows."},
            }
            return SimpleNamespace(
                summary="Returned the latest sales rows.",
                llm_summary=None,
                tables=[],
                warnings=[],
                plan=SimpleNamespace(task_type="descriptive"),
                to_response_dict=lambda: payload,
            )

        def analyze_source(self, source: object, question: str) -> object:
            return self.analyze(source, question)

    fake_engine = _FakeTabularEngine()

    monkeypatch.setattr(example2_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(example2_playground.os, "getenv", lambda key, default=None: "test-key" if key == "OPENAI_API_KEY" else default)
    monkeypatch.setattr(example2_playground, "PromptAnalysisFrontend", lambda config=None: fake_engine)

    answers = iter(["Show the latest 2 rows", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    example2_playground.main()
    output = capsys.readouterr().out

    assert "Returned the latest sales rows." in output
    assert "1. order_id=ORD-040 | country=United States | total_sales=464.50" in output
    assert "2. order_id=ORD-039 | country=Germany | total_sales=323.00" in output


def test_example3_authored_plan_playground_builds_explicit_first_five_rows_plan() -> None:
    plan = example3_playground.build_first_five_rows_plan("sales_sqlite_40")

    assert plan.dataset_refs == ["sales_sqlite_40"]
    assert plan.final_output_ref == "first_five_rows"
    assert len(plan.steps) == 1
    assert plan.steps[0].method_id == "tabular_query"
    assert plan.steps[0].parameters["page_size"] == 5
    assert plan.steps[0].parameters["sort_by"] == "order_date"
    assert plan.steps[0].parameters["sort_direction"] == "asc"


def test_example3_authored_plan_playground_prints_public_response_json(
    monkeypatch: object,
    capsys: object,
) -> None:
    dataset = SimpleNamespace(name="sales_sqlite_40", data=pd.DataFrame({"total_sales": [1.0]}))
    fake_result_payload = {
        "schema_version": "saida.response.v2",
        "status": "ok",
        "result": {"name": "first_five_rows", "value": [{"order_id": "ORD-001"}]},
    }
    fake_engine = SimpleNamespace(
        execute_plan=lambda dataset, plan: SimpleNamespace(
            to_response_dict=lambda: fake_result_payload,
        )
    )

    monkeypatch.setattr(example3_playground, "load_project_env", lambda project_root: None)
    monkeypatch.setattr(example3_playground.SQLiteSource, "load", lambda self: dataset)
    monkeypatch.setattr(example3_playground, "Saida", lambda: fake_engine)

    example3_playground.main()
    output = capsys.readouterr().out

    assert '"schema_version": "saida.response.v2"' in output
    assert '"first_five_rows"' in output
