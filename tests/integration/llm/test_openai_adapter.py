from saida_core.adapters.llm.openai_adapter import OpenAILLMAdapter


def test_openai_adapter_placeholder_response():
    adapter = OpenAILLMAdapter()
    output = adapter.generate("hello")
    assert output.startswith("[openai-placeholder]")