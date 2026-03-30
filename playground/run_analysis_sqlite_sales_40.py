from pathlib import Path
import json
import os
import sys
import threading
import time
from typing import Any


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
ANSI_YELLOW = "\033[33m"
DEFAULT_ANALYST_INSTRUCTION = (
    "You are a professional data analyst interpreting a SAIDA response JSON for a human user. "
    "Return a concise, helpful explanation in plain English. "
    "If the result is scalar, mention the scalar value clearly. "
    "If the result is tabular, summarize what the table represents without listing the rows, because rows are rendered separately."
)


def _llm_provider_name() -> str:
    provider = str(os.getenv("SAIDA_SQLITE_PLAYGROUND_PROVIDER", "openai")).strip().lower()
    return provider if provider in {"openai", "ollama"} else "openai"


def _require_provider_configuration(provider: str) -> None:
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")


def _build_llm_config(provider: str) -> LlmConfig:
    if provider == "ollama":
        return LlmConfig(
            enabled=True,
            provider="ollama",
            model=os.getenv("OLLAMA_MODEL", "gemma3:1b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            use_for_prompting=True,
            use_for_summary=True,
        )
    return LlmConfig(
        enabled=True,
        provider="openai",
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        use_for_prompting=True,
        use_for_summary=True,
    )


def _playground_label(provider: str) -> str:
    return "OpenAI" if provider == "openai" else "Ollama"


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


def _analyst_instruction() -> str:
    return os.getenv("SAIDA_SQLITE_PLAYGROUND_ANALYST_INSTRUCTION", DEFAULT_ANALYST_INSTRUCTION).strip()


def _playground_summary(engine: object, question: str, result: object) -> str:
    payload = result.to_response_dict()
    provider = getattr(getattr(engine, "engine", None), "llm_provider", None)
    summary = _playground_llm_summary(provider, question, payload)
    if summary is None:
        summary = (getattr(result, "llm_summary", None) or result.summary).strip()
    return _ensure_scalar_value_in_summary(summary, payload)


def _playground_llm_summary(provider: object, question: str, payload: dict[str, Any]) -> str | None:
    if provider is None:
        return None
    prompt = (
        f"{_analyst_instruction()}\n"
        "Return JSON only using this schema: "
        '{"status":"ready","summary":"..."}.\n'
        f"User question: {question}\n"
        f"SAIDA response JSON: {json.dumps(payload, ensure_ascii=True, allow_nan=False)}\n"
    )
    try:
        if getattr(provider, "provider_name", None) == "openai" and hasattr(provider, "_responses_json"):
            proposal = provider._responses_json(prompt, max_output_tokens=300)
        elif hasattr(provider, "_generate_json"):
            proposal = provider._generate_json(prompt)
        else:
            return None
    except Exception:
        return None
    if not isinstance(proposal, dict):
        return None
    if str(proposal.get("status", "ready")) != "ready":
        return None
    summary = proposal.get("summary")
    return summary.strip() if isinstance(summary, str) and summary.strip() else None


def _ensure_scalar_value_in_summary(summary: str, payload: dict[str, Any]) -> str:
    result_payload = payload.get("result")
    if not isinstance(result_payload, dict):
        return summary
    physical_shape = result_payload.get("physical_shape")
    value = result_payload.get("value")
    if physical_shape != "scalar":
        return summary
    if value is None:
        return summary
    scalar_text = str(value)
    return summary if scalar_text in summary else f"{summary} Result: {scalar_text}."


def _render_tabular_lines(result: object) -> list[str]:
    payload = result.to_response_dict()
    result_payload = payload.get("result")
    if not isinstance(result_payload, dict):
        return []
    value = result_payload.get("value")
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for index, row in enumerate(value, start=1):
        if isinstance(row, dict):
            parts = [f"{key}={_display_value(item)}" for key, item in row.items()]
            lines.append(f"{index}. " + " | ".join(parts))
        else:
            lines.append(f"{index}. {_display_value(row)}")
    return lines


def _display_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def main() -> None:
    load_project_env(PROJECT_ROOT)
    provider = _llm_provider_name()
    _require_provider_configuration(provider)

    dataset = SQLiteSource(
        DEFAULT_DATABASE_PATH,
        DEFAULT_QUERY,
        name="sales_sqlite_40",
        context_path=DEFAULT_CONTEXT_PATH,
    ).load()

    config = SaidaConfig(
        llm=_build_llm_config(provider)
    )

    engine = PromptAnalysisFrontend(config=config)
    print(f"SAIDA {_playground_label(provider)} SQLite playground")
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

        display_summary = _playground_summary(engine, question, result)
        print(f"{ANSI_YELLOW}{display_summary}{ANSI_RESET}")
        for line in _render_tabular_lines(result):
            print(line)
        if result.plan.task_type == "clarification":
            pending_prompt = question
            print("Please answer the clarification above, or type 'exit' to quit.")


if __name__ == "__main__":
    main()

