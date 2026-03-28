from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from _env import load_project_env
from saida import PromptAnalysisFrontend
from saida.config import LlmConfig, SaidaConfig
from saida.sources import CSVSource


EXIT_WORDS = {"exit", "quit", "q"}


def _compose_clarification_follow_up(original_question: str, answer: str) -> str:
    return f"Original request: {original_question}\nClarification answer: {answer}"


def main() -> None:
    load_project_env(PROJECT_ROOT)

    dataset = CSVSource(
        PROJECT_ROOT / "examples" / "sales.csv",
        context_path=PROJECT_ROOT / "examples" / "sales_context.md",
    ).load()

    config = SaidaConfig(
        llm=LlmConfig(
            enabled=True,
            provider="ollama",
            model=os.getenv("OLLAMA_MODEL", "llama3.1"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            use_for_prompting=True,
            use_for_reasoning=True,
        )
    )

    engine = PromptAnalysisFrontend(config=config)
    print("SAIDA Ollama playground")
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

        result = engine.analyze(dataset, question)

        print(result.summary)
        if result.tables:
            print("Tables:", ", ".join(table.name for table in result.tables))
        if result.warnings:
            print("Warnings:", "; ".join(result.warnings))

        if result.plan.task_type == "clarification":
            pending_prompt = question
            print("Please answer the clarification above, or type 'exit' to quit.")


if __name__ == "__main__":
    main()

