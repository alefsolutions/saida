from dataclasses import dataclass, field


@dataclass(slots=True)
class ContextBundle:
    records: list[dict] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)