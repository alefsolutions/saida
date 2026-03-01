from __future__ import annotations

from saida_core.core.domain.query import Query
from saida_core.core.runtime.container import build_container


def run_query(question: str, task_type: str = "general") -> str:
    orchestration = build_container()
    result = orchestration.run(Query(text=question, task_type=task_type))
    return result.answer