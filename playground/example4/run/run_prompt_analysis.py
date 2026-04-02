from pathlib import Path
import json
import os
import sqlite3
import sys
import threading
import time
from typing import Any


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
from saida.sources import SQLiteSource


EXIT_WORDS = {"exit", "quit", "q"}
DEFAULT_DATABASE_PATH = EXAMPLE_ROOT / "data" / "warehouse_relational.sqlite"
DEFAULT_CONTEXT_PATH = EXAMPLE_ROOT / "data" / "warehouse_relational.md"
DEFAULT_QUERY = 'SELECT * FROM "orders"'
ANSI_RESET = "\033[0m"
ANSI_YELLOW = "\033[33m"


def _ensure_database(database_path: Path) -> None:
    if database_path.exists():
        return
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute(
            "create table customers ("
            "customer_id text primary key, "
            "customer_name text not null, "
            "country text not null, "
            "region text not null"
            ")"
        )
        connection.execute(
            "create table products ("
            "product_id text primary key, "
            "product_name text not null, "
            "product_category text not null, "
            "unit_price real not null"
            ")"
        )
        connection.execute(
            "create table orders ("
            "order_id text primary key, "
            "customer_id text not null, "
            "order_date text not null, "
            "sales_channel text not null, "
            "total_sales real not null, "
            "foreign key(customer_id) references customers(customer_id)"
            ")"
        )
        connection.execute(
            "create table order_items ("
            "order_item_id text primary key, "
            "order_id text not null, "
            "product_id text not null, "
            "quantity integer not null, "
            "line_total real not null, "
            "foreign key(order_id) references orders(order_id), "
            "foreign key(product_id) references products(product_id)"
            ")"
        )
        connection.executemany(
            "insert into customers values (?, ?, ?, ?)",
            [
                ("C1", "Acacia Retail", "Australia", "Oceania"),
                ("C2", "Sakura Labs", "Japan", "Asia"),
                ("C3", "Rhein Works", "Germany", "Europe"),
            ],
        )
        connection.executemany(
            "insert into products values (?, ?, ?, ?)",
            [
                ("P1", "Insight Suite", "Software", 45.0),
                ("P2", "Field Kit", "Hardware", 80.0),
                ("P3", "Advisory Hours", "Services", 120.0),
            ],
        )
        connection.executemany(
            "insert into orders values (?, ?, ?, ?, ?)",
            [
                ("O1", "C1", "2026-01-01", "Online", 100.0),
                ("O2", "C1", "2026-01-02", "Retail", 120.0),
                ("O3", "C2", "2026-01-03", "Online", 80.0),
                ("O4", "C3", "2026-01-04", "Partner", 150.0),
            ],
        )
        connection.executemany(
            "insert into order_items values (?, ?, ?, ?, ?)",
            [
                ("OI1", "O1", "P1", 1, 45.0),
                ("OI2", "O1", "P2", 1, 55.0),
                ("OI3", "O2", "P3", 1, 120.0),
                ("OI4", "O3", "P1", 1, 45.0),
                ("OI5", "O3", "P2", 1, 35.0),
                ("OI6", "O4", "P2", 1, 80.0),
                ("OI7", "O4", "P3", 1, 70.0),
            ],
        )
        connection.commit()
    finally:
        connection.close()


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
    return lines


def _display_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _playground_summary(result: object) -> str:
    payload = result.to_response_dict()
    summary_payload = payload.get("summary")
    if isinstance(summary_payload, dict):
        summary = summary_payload.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return result.summary


def main() -> None:
    load_project_env(PROJECT_ROOT)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    _ensure_database(DEFAULT_DATABASE_PATH)
    source = SQLiteSource(
        DEFAULT_DATABASE_PATH,
        DEFAULT_QUERY,
        name="warehouse_sales",
        context_path=DEFAULT_CONTEXT_PATH,
    )
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

    print("SAIDA Example 4: OpenAI relational warehouse sqlite")
    print(f"Dataset: {source.source_name}")
    print("Source: sqlite")
    print("Mode: source-aware relational materialization (multi-table)")
    print("Try prompts like: Show a table of total_sales by country")
    print("Or: Show a table of line_total by product_category")
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
            result = engine.analyze_source(source, question)
        finally:
            stop_event.set()
            loader_thread.join()

        print(f"{ANSI_YELLOW}{_playground_summary(result)}{ANSI_RESET}")
        for line in _render_tabular_lines(result):
            print(line)
        if result.plan.task_type == "clarification":
            pending_prompt = question
            print("Please answer the clarification above, or type 'exit' to quit.")


if __name__ == "__main__":
    main()
