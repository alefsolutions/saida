from dataclasses import dataclass, field


@dataclass(slots=True)
class AnalysisResult:
    answer: str
    evidence: list[dict] = field(default_factory=list)