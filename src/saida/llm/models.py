"""Typed objects for optional LLM integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class IntentProposal:
    """Structured prompt interpretation proposed by an optional LLM."""

    status: str = "ready"
    canonical_question: str | None = None
    prompt_family_hint: str | None = None
    confidence: float | None = None
    operation: str | None = None
    object_kind: str | None = None
    object_ref: str | None = None
    expected_result_shape: str | None = None
    candidate_capabilities: list[str] | None = None
    task_type_hint: str | None = None
    target: str | None = None
    aggregation: str | None = None
    horizon: int | None = None
    filters: dict[str, Any] | None = None
    group_by: list[str] | None = None
    time_reference: dict[str, str] | None = None
    message: str | None = None
    warnings: list[str] = field(default_factory=list)
    raw_response: str | None = None


@dataclass(slots=True)
class SummaryProposal:
    """Structured summary text proposed by an optional LLM."""

    status: str = "ready"
    summary: str | None = None
    message: str | None = None
    warnings: list[str] = field(default_factory=list)
    raw_response: str | None = None


@dataclass(slots=True)
class SummaryContext:
    """Deterministic payload passed to an optional LLM summary provider."""

    question: str
    dataset_name: str
    task_type: str
    deterministic_summary: str
    context_summary: str | None
    metric_lookup: dict[str, Any]
    table_index: dict[str, dict[str, Any]]
    warnings: list[str]
