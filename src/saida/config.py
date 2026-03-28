"""Configuration objects for SAIDA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NlpConfig:
    """Configuration for request normalization."""

    enable_transformers: bool = False
    zero_shot_model: str = "facebook/bart-large-mnli"
    confidence_threshold: float = 0.55


@dataclass(slots=True)
class LlmConfig:
    """Configuration for optional model-backed plan generation and summary handling."""

    enabled: bool = False
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    use_for_prompting: bool = True
    use_for_summary: bool = True
    timeout_seconds: int = 20
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SaidaConfig:
    """Top-level configuration for the SAIDA engine."""

    nlp: NlpConfig = field(default_factory=NlpConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
