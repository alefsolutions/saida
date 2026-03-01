from dataclasses import dataclass


@dataclass(slots=True)
class AskRequest:
    question: str
    task_type: str = "general"