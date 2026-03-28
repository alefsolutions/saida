from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from saida import PromptAnalysisFrontend
from saida.sources import CSVSource


def main() -> None:
    dataset = CSVSource(
        PROJECT_ROOT / "examples" / "sales.csv",
        context_path=PROJECT_ROOT / "examples" / "sales_context.md",
    ).load()

    engine = PromptAnalysisFrontend()
    result = engine.analyze(dataset, "Why did revenue drop in March by region?")

    print(result.summary)
    print("Tables:", ", ".join(table.name for table in result.tables))
    if result.warnings:
        print("Warnings:", "; ".join(result.warnings))


if __name__ == "__main__":
    main()

