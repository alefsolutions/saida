from __future__ import annotations

from pathlib import Path

from saida_core.adapters.data_sources.local_fs.parser import chunk_text, parse_file
from saida_core.core.contracts.embedding import EmbeddingModel
from saida_core.core.contracts.vector_store import VectorStore


class DocumentIngestPipeline:
    def __init__(self, embedding: EmbeddingModel, vector_store: VectorStore):
        self.embedding = embedding
        self.vector_store = vector_store

    def ingest(self, item_id: str, text: str, metadata: dict | None = None) -> None:
        vec = self.embedding.embed(text)
        payload = metadata.copy() if metadata else {}
        payload.setdefault("text", text)
        self.vector_store.upsert(item_id, vec, payload)

    def ingest_file(self, path: str, chunk_size: int = 1200, overlap: int = 200) -> int:
        file_path = Path(path)
        parsed = parse_file(file_path)
        text = parsed.get("text", "")
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        count = 0
        for index, chunk in enumerate(chunks):
            chunk_id = f"{file_path.name}:{index}"
            metadata = {
                "source": "local_fs",
                "path": str(file_path),
                "extension": parsed.get("extension"),
                "chunk_index": index,
                "text": chunk,
            }
            self.ingest(chunk_id, chunk, metadata)
            count += 1
        return count
