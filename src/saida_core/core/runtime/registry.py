from __future__ import annotations

from collections import defaultdict

from saida_core.core.domain.errors import ProviderNotRegisteredError


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, dict[str, object]] = defaultdict(dict)

    def register(self, kind: str, name: str, provider: object) -> None:
        self._providers[kind][name] = provider

    def get(self, kind: str, name: str) -> object:
        provider = self._providers.get(kind, {}).get(name)
        if provider is None:
            raise ProviderNotRegisteredError(f"Provider '{name}' not found for kind '{kind}'.")
        return provider