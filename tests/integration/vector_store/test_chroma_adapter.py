from saida_core.adapters.vector_store.chroma_adapter import ChromaVectorStoreAdapter


def test_chroma_adapter_upsert_and_query():
    store = ChromaVectorStoreAdapter()
    store.upsert("1", [0.1], {"k": "v"})
    results = store.query([0.1], top_k=1)
    assert len(results) == 1