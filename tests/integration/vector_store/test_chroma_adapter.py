import sys

import pytest

from saida_core.adapters.vector_store.chroma_adapter import ChromaVectorStoreAdapter


def test_chroma_adapter_upsert_and_query():
    if sys.version_info >= (3, 14):
        pytest.skip("ChromaDB currently unsupported on Python 3.14+.")
    try:
        store = ChromaVectorStoreAdapter(collection_name="test_collection")
    except RuntimeError as exc:
        pytest.skip(str(exc))
    store.upsert("1", [0.1, 0.2, 0.3], {"k": "v", "text": "hello world"})
    results = store.query([0.1, 0.2, 0.3], top_k=1)
    assert len(results) == 1
    assert results[0]["id"] == "1"
