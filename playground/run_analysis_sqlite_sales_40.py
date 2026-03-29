from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import threading
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from _env import load_project_env
from saida import PromptAnalysisFrontend
from saida.config import LlmConfig, SaidaConfig
from saida.sources import SQLiteSource


EXIT_WORDS = {"exit", "quit", "q"}
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "examples" / "sqlite_sales_40" / "sales_sqlite_40.db"
DEFAULT_CONTEXT_PATH = PROJECT_ROOT / "examples" / "sqlite_sales_40" / "sales_sqlite_40.md"
DEFAULT_QUERY = "SELECT * FROM sales_orders"
DEFAULT_JSON_WINDOW_PATH = Path(tempfile.gettempdir()) / "saida_sqlite_sales_40_result.json"


def _show_loader(stop_event: threading.Event) -> None:
    frames = [".", "..", "..."]
    index = 0
    while not stop_event.is_set():
        print(f"\rThinking{frames[index % len(frames)]}", end="", flush=True)
        index += 1
        time.sleep(0.4)
    print("\r" + " " * 20 + "\r", end="", flush=True)


def _compose_clarification_follow_up(original_question: str, answer: str) -> str:
    return f"Original request: {original_question}\nClarification answer: {answer}"


def _json_window_enabled(argv: list[str] | None = None) -> bool:
    arguments = argv or sys.argv[1:]
    return "--json-window" in arguments or os.getenv("SAIDA_SQLITE_JSON_WINDOW") == "1"


def _json_output_path() -> Path:
    configured = os.getenv("SAIDA_SQLITE_JSON_PATH")
    return Path(configured) if configured else DEFAULT_JSON_WINDOW_PATH


def _write_analysis_result_json(path: Path, result: object) -> None:
    payload = result.to_response_dict()
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, allow_nan=False),
        encoding="utf-8",
    )


def _spawn_json_window(path: Path) -> None:
    escaped_path = str(path).replace("'", "''")
    viewer_script = (
        "$Host.UI.RawUI.WindowTitle = 'SAIDA AnalysisResult JSON'; "
        f"$path = '{escaped_path}'; "
        "while ($true) { "
        "Clear-Host; "
        "Write-Host 'SAIDA AnalysisResult JSON'; "
        "Write-Host ''; "
        "if (Test-Path -LiteralPath $path) { "
        "Get-Content -LiteralPath $path -Raw "
        "} else { "
        "Write-Host 'Waiting for first result...' "
        "} "
        "Start-Sleep -Milliseconds 750 "
        "}"
    )
    subprocess.Popen(
        [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            viewer_script,
        ],
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )


def main() -> None:
    load_project_env(PROJECT_ROOT)
    json_window_enabled = _json_window_enabled()
    json_output_path = _json_output_path()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    dataset = SQLiteSource(
        DEFAULT_DATABASE_PATH,
        DEFAULT_QUERY,
        name="sales_sqlite_40",
        context_path=DEFAULT_CONTEXT_PATH,
    ).load()

    config = SaidaConfig(
        llm=LlmConfig(
            enabled=True,
            provider="openai",
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            use_for_prompting=True,
            use_for_summary=True,
        )
    )

    engine = PromptAnalysisFrontend(config=config)
    print("SAIDA OpenAI SQLite playground")
    print(f"Dataset: {dataset.name}")
    print("Source: sqlite")
    print("Type a question, or type 'exit' to quit.")
    if json_window_enabled:
        _spawn_json_window(json_output_path)
        print(f"JSON mirror window: enabled -> {json_output_path}")

    pending_prompt: str | None = None
    while True:
        if pending_prompt is None:
            question = input("> ").strip()
        else:
            answer = input("clarification> ").strip()
            if answer.lower() in EXIT_WORDS:
                break
            question = _compose_clarification_follow_up(pending_prompt, answer)
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

        if json_window_enabled:
            _write_analysis_result_json(json_output_path, result)
        print((getattr(result, "llm_summary", None) or result.summary).strip())
        if result.tables:
            print("Tables:", ", ".join(table.name for table in result.tables))
        if result.warnings:
            print("Warnings:", "; ".join(result.warnings))
        if result.plan.task_type == "clarification":
            pending_prompt = question
            print("Please answer the clarification above, or type 'exit' to quit.")


if __name__ == "__main__":
    main()

