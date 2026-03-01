from saida_core.core.runtime.registry import ProviderRegistry


def test_provider_registry_register_and_get():
    registry = ProviderRegistry()
    provider = object()
    registry.register("llm", "mock", provider)
    assert registry.get("llm", "mock") is provider