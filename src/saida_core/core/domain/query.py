from dataclasses import dataclass


@dataclass(slots=True)
class Query:
    text: str
    task_type: str = "general"