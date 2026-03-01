from dataclasses import dataclass, field


@dataclass(slots=True)
class AskResponse:
    answer: str
    evidence: list[dict] = field(default_factory=list)