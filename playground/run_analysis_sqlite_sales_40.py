from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from saida import Saida
from saida.sources import SQLiteSource


EXIT_WORDS = {"exit", "quit", "q"}
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "examples" / "sqlite_sales_40" / "sales_sqlite_40.db"
DEFAULT_CONTEXT_PATH = PROJECT_ROOT / "examples" / "sqlite_sales_40" / "sales_sqlite_40.md"
DEFAULT_QUERY = "SELECT * FROM sales_orders"


def main() -> None:
    dataset = SQLiteSource(
        DEFAULT_DATABASE_PATH,
        DEFAULT_QUERY,
        name="sales_sqlite_40",
        context_path=DEFAULT_CONTEXT_PATH,
    ).load()

    engine = Saida()
    print("SAIDA SQLite playground")
    print(f"Dataset: {dataset.name}")
    print("Source: sqlite")
    print("Type a question, or type 'exit' to quit.")

    while True:
        question = input("> ").strip()
        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            break

        result = engine.analyze(dataset, question)
        print(result.summary.strip())
        if result.tables:
            print("Tables:", ", ".join(table.name for table in result.tables))
        if result.warnings:
            print("Warnings:", "; ".join(result.warnings))


if __name__ == "__main__":
    main()
