from pathlib import Path
import os
import sys
import threading
import time


EXAMPLE_ROOT = Path(__file__).resolve().parents[1]
PLAYGROUND_ROOT = EXAMPLE_ROOT.parents[0]
PROJECT_ROOT = EXAMPLE_ROOT.parents[1]
SRC_PATH = PROJECT_ROOT / "src"
for path in (SRC_PATH, PLAYGROUND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from _env import load_project_env
from saida import PromptAnalysisFrontend
from saida.config import LlmConfig, SaidaConfig
from saida.sources import CSVSource


EXIT_WORDS = {"exit", "quit", "q"}
DEFAULT_DATASET_PATH = EXAMPLE_ROOT / "data" / "sales_data_800_rows.csv"
DEFAULT_CONTEXT_PATH = EXAMPLE_ROOT / "data" / "sales_data_800_rows.md"


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


def main() -> None:
    load_project_env(PROJECT_ROOT)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    dataset = CSVSource(
        DEFAULT_DATASET_PATH,
        context_path=DEFAULT_CONTEXT_PATH,
        name="sales_data_800_rows",
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
    print("SAIDA Example 1: OpenAI sales CSV 800 rows")
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

        print((getattr(result, "llm_summary", None) or result.summary).strip())
        if result.plan.task_type == "clarification":
            pending_prompt = question
            print("Please answer the clarification above, or type 'exit' to quit.")


if __name__ == "__main__":
    main()
