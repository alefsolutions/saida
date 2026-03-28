"""Compatibility aliases for the consolidated analytics registry.

The analytics registry is the single canonical registry in SAIDA core. This
module remains only as a thin compatibility layer for older imports that still
refer to the retired capability registry names.
"""

from __future__ import annotations

from saida.core.analytics_registry import (
    AnalyticsConceptSpec,
    AnalyticsRegistry,
    AnalyticsRelationSpec,
    build_default_analytics_registry,
)

CapabilityNode = AnalyticsConceptSpec
CapabilityEdge = AnalyticsRelationSpec
CapabilityRegistry = AnalyticsRegistry


def build_default_capability_registry() -> CapabilityRegistry:
    """Return a fresh analytics registry instance for compatibility callers."""

    return build_default_analytics_registry()


def get_capability_registry() -> CapabilityRegistry:
    """Return a fresh analytics registry instance for compatibility callers."""

    return build_default_capability_registry()


__all__ = [
    "CapabilityEdge",
    "CapabilityNode",
    "CapabilityRegistry",
    "build_default_capability_registry",
    "get_capability_registry",
]
