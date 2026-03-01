from saida_core.adapters.llm.openai_adapter import OpenAILLMAdapter


class _FakeResponses:
    def create(self, **_: dict):
        class _Resp:
            output_text = "synthetic response"

        return _Resp()


class _FakeClient:
    responses = _FakeResponses()


def test_openai_adapter_uses_client_responses_api():
    adapter = OpenAILLMAdapter(client=_FakeClient(), model="gpt-test")
    assert adapter.generate("hello") == "synthetic response"
