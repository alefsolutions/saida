from saida_core.pipelines.query.rag_pipeline import SimpleRetriever


def test_simple_retriever_returns_context():
    retriever = SimpleRetriever()
    out = retriever.retrieve("revenue")
    assert out and out[0]["source"] == "retriever"