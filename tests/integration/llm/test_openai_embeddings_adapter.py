from saida_core.adapters.embeddings.openai_embeddings_adapter import OpenAIEmbeddingAdapter


class _FakeEmbeddings:
    def create(self, **_: dict):
        class _Item:
            embedding = [0.11, 0.22, 0.33]

        class _Resp:
            data = [_Item()]

        return _Resp()


class _FakeClient:
    embeddings = _FakeEmbeddings()


def test_openai_embedding_adapter_uses_embeddings_api():
    adapter = OpenAIEmbeddingAdapter(client=_FakeClient(), model="emb-test")
    assert adapter.embed("hello") == [0.11, 0.22, 0.33]
