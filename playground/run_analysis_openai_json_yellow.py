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
from saida import Saida
from saida.config import LlmConfig, SaidaConfig
from saida.sources import CSVSource


EXIT_WORDS = {"exit", "quit", "q"}
DEFAULT_DATASET_PATH = PROJECT_ROOT / "examples" / "datasets" / "support_tickets_500.csv"
DEFAULT_CONTEXT_PATH = PROJECT_ROOT / "examples" / "contexts" / "support_tickets_500.md"
ANSI_RESET = "\033[0m"
ANSI_YELLOW = "\033[33m"


def _show_loader(stop_event: threading.Event) -> None:
    frames = [".", "..", "..."]
    index = 0
    while not stop_event.is_set():
        print(f"\rThinking{frames[index % len(frames)]}", end="", flush=True)
        index += 1
        time.sleep(0.4)
    print("\r" + " " * 20 + "\r", end="", flush=True)


def _output_mode(argv: list[str] | None = None) -> str:
    arguments = argv or sys.argv[1:]
    if "--both" in arguments:
        return "both"
    if "--contract" in arguments:
        return "contract"
    env_mode = os.getenv("SAIDA_PLAYGROUND_OUTPUT_MODE")
    if env_mode in {"result", "contract", "both"}:
        return env_mode
    return "result"


def _render_json_output(result: object, output_mode: str) -> str:
    payload = result.to_response_dict()
    contract_payload = payload.get("interpretation", {}).get("capability_contract")
    if output_mode == "contract":
        rendered_payload = contract_payload or {"status": "missing_contract", "message": "No capability contract payload was returned."}
    elif output_mode == "both":
        rendered_payload = {
            "capability_contract": contract_payload,
            "response": payload,
        }
    else:
        rendered_payload = payload
    formatted_json = json.dumps(rendered_payload, indent=2, ensure_ascii=True, allow_nan=False)
    return f"{ANSI_YELLOW}{formatted_json}{ANSI_RESET}"


def _compose_clarification_follow_up(original_question: str, answer: str) -> str:
    return f"Original request: {original_question}\nClarification answer: {answer}"


def main() -> None:
    load_project_env(PROJECT_ROOT)
    output_mode = _output_mode()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    dataset = CSVSource(
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
    print("SAIDA OpenAI JSON yellow playground")
    print(f"Dataset: {dataset.name}")
    print("Type a question, or type 'exit' to quit.")
    print(f"Output mode: {output_mode} JSON")

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

        print(_render_json_output(result, output_mode))

        if result.plan.task_type == "clarification":
            pending_prompt = question
            print("Please answer the clarification above, or type 'exit' to quit.")


if __name__ == "__main__":
    main()
