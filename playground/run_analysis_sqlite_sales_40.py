from pathlib import Path
import json
import os
import sys
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
ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_YELLOW = "\033[33m"


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


def _render_analysis_result_json(result: object) -> str:
    payload = result.to_response_dict()
    formatted = json.dumps(payload, indent=2, ensure_ascii=True, allow_nan=False)
    return f"{ANSI_YELLOW}{formatted}{ANSI_RESET}"


def main() -> None:
    load_project_env(PROJECT_ROOT)

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

        llm_response = (getattr(result, "llm_summary", None) or result.summary).strip()
        print(f"{ANSI_RED}{llm_response}{ANSI_RESET}")
        print(_render_analysis_result_json(result))
        if result.plan.task_type == "clarification":
            pending_prompt = question
            print("Please answer the clarification above, or type 'exit' to quit.")


if __name__ == "__main__":
    main()

