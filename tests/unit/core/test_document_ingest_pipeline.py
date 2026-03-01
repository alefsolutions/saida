from pathlib import Path

from saida_core.core.contracts.embedding import EmbeddingModel
from saida_core.core.contracts.vector_store import VectorStore
from saida_core.pipelines.ingest.document_ingest import DocumentIngestPipeline


class _FakeEmbedding(EmbeddingModel):
    def embed(self, text: str) -> list[float]:
        return [float(len(text))]


class _FakeVectorStore(VectorStore):
    def __init__(self):
        self.rows: list[dict] = []

    def upsert(self, item_id: str, vector: list[float], metadata: dict) -> None:
        self.rows.append({"id": item_id, "vector": vector, "metadata": metadata})

    def query(self, vector: list[float], top_k: int = 5) -> list[dict]:
        return self.rows[:top_k]


def test_ingest_file_chunks_and_upserts(tmp_path: Path):
    text_path = tmp_path / "input.txt"
    text_path.write_text("hello " * 600, encoding="utf-8")

    store = _FakeVectorStore()
    pipeline = DocumentIngestPipeline(embedding=_FakeEmbedding(), vector_store=store)

    count = pipeline.ingest_file(str(text_path), chunk_size=500, overlap=100)
    assert count > 1
    assert len(store.rows) == count
