from __future__ import annotations

from dataclasses import asdict
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from _env import load_project_env
from saida import Saida
from saida.adapters import CSVAdapter
from saida.config import LlmConfig, SaidaConfig


EXIT_WORDS = {"exit", "quit", "q"}
DEFAULT_DATASET_PATH = PROJECT_ROOT / "examples" / "datasets" / "support_tickets_500.csv"
DEFAULT_CONTEXT_PATH = PROJECT_ROOT / "examples" / "contexts" / "support_tickets_500.md"


def _show_loader(stop_event: threading.Event) -> None:
    frames = [".", "..", "..."]
    index = 0
    while not stop_event.is_set():
        print(f"\rThinking{frames[index % len(frames)]}", end="", flush=True)
        index += 1
        time.sleep(0.4)
    print("\r" + " " * 20 + "\r", end="", flush=True)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _table_payload(result: Any) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for table in result.tables:
        records = [{key: _json_safe(value) for key, value in row.items()} for row in table.dataframe.to_dict(orient="records")]
        payload.append(
            {
                "name": table.name,
                "description": table.description,
                "columns": list(table.dataframe.columns),
                "row_count": int(len(table.dataframe)),
                "records": records,
            }
        )
    return payload


def _result_payload(result: Any) -> dict[str, Any]:
    response = result.to_response_dict()
    return {
        "schema_version": "saida.playground_query_result.v1",
        "status": response.get("status", "ok"),
        "question": response.get("question"),
        "dataset": response.get("dataset", {}),
        "intent": response.get("intent", {}),
        "plan": response.get("plan", {}),
        "outputs": {
            "summary": result.summary,
            "deterministic_summary": result.deterministic_summary,
            "llm_summary": result.llm_summary,
            "summary_source": result.summary_source,
            "warnings": list(result.warnings),
            "metrics": [_json_safe(asdict(metric)) for metric in result.metrics],
            "tables": _table_payload(result),
        },
        "trace": response.get("outputs", {}).get("trace", []),
    }


def main() -> None:
    load_project_env(PROJECT_ROOT)

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    dataset = CSVAdapter(
        DEFAULT_DATASET_PATH,
        context_path=DEFAULT_CONTEXT_PATH,
    ).load()

    config = SaidaConfig(
        llm=LlmConfig(
            enabled=True,
            provider="openai",
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            use_for_prompting=True,
            use_for_reasoning=True,
        )
    )

    engine = Saida(config=config)
    print("SAIDA OpenAI JSON playground")
    print(f"Dataset: {dataset.name}")
    print("Type a question, or type 'exit' to quit.")

    pending_prompt: str | None = None
    while True:
        if pending_prompt is None:
            question = input("> ").strip()
        else:
            answer = input("clarification> ").strip()
            if answer.lower() in EXIT_WORDS:
                break
            question = answer
            pending_prompt = None

        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            break

        stop_event = threading.Event()
        loader_thread = threading.Thread(target=_show_loader, args=(stop_event,), daemon=True)
        loader_thread.start()
        try:
            result = engine.analyze(dataset, question)
        finally:
            stop_event.set()
            loader_thread.join()

        print(json.dumps(_result_payload(result), indent=2, ensure_ascii=True))

        if result.plan.task_type == "clarification":
            pending_prompt = question
            print("Please answer the clarification above, or type 'exit' to quit.")


if __name__ == "__main__":
    main()
