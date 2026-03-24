"""Backend routing for canonical plan steps."""

from __future__ import annotations

from saida.exceptions import PlanningError


class BackendRouter:
    """Route plan steps to the correct backend adapter."""

    def __init__(
        self,
        *,
        duckdb_adapter: object,
        metadata_adapter: object,
        stats_adapter: object,
        ml_adapter: object,
    ) -> None:
        self._adapters = {
            "duckdb": duckdb_adapter,
            "metadata": metadata_adapter,
            "stats": stats_adapter,
            "ml": ml_adapter,
        }

    def route(self, tool_family: str) -> object:
        """Return the backend adapter for a tool family."""
        adapter = self._adapters.get(tool_family)
        if adapter is None:
            raise PlanningError(f"No backend adapter is registered for tool family '{tool_family}'.")
        return adapter
