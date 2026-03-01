from __future__ import annotations

import argparse

from saida_core.core.domain.query import Query
from saida_core.core.runtime.container import build_container


def main() -> None:
    parser = argparse.ArgumentParser(description="SAIDA Core CLI")
    parser.add_argument("question", nargs="?", default="What changed in revenue this quarter?")
    parser.add_argument("--task", default="general")
    args = parser.parse_args()

    orchestration = build_container()
    result = orchestration.run(Query(text=args.question, task_type=args.task))
    print(result.answer)


if __name__ == "__main__":
    main()