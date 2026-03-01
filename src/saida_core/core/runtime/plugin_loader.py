from __future__ import annotations

from saida_core.core.runtime.registry import ProviderRegistry


def load_builtin_plugins(registry: ProviderRegistry) -> None:
    # Builtins are registered in container.py for now.
    return None