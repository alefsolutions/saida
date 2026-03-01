from __future__ import annotations

import os
from typing import Any

from saida_core.core.contracts.vector_store import VectorStore


class ChromaVectorStoreAdapter(VectorStore):
    def __init__(
        self,
        collection_name: str | None = None,
        persist_directory: str | None = None,
        client: Any | None = None,
    ):
        self.collection_name = collection_name or os.getenv("SAIDA_CHROMA_COLLECTION", "saida_core")
        self.persist_directory = persist_directory or os.getenv("SAIDA_CHROMA_PERSIST_DIR")
        self._client = client or self._build_client()
        self._collection = self._client.get_or_create_collection(name=self.collection_name)

    def _build_client(self) -> Any:
        try:
            import chromadb
        except Exception as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError("ChromaDB client is unavailable in this Python environment.") from exc

        if self.persist_directory:
            return chromadb.PersistentClient(path=self.persist_directory)
        return chromadb.EphemeralClient()

    def upsert(self, item_id: str, vector: list[float], metadata: dict) -> None:
        document = ""
        if isinstance(metadata, dict):
            value = metadata.get("text")
            if isinstance(value, str):
                document = value
        self._collection.upsert(
            ids=[item_id],
            embeddings=[vector],
            metadatas=[metadata],
            documents=[document],
        )

    def query(self, vector: list[float], top_k: int = 5) -> list[dict]:
        raw = self._collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

        ids = raw.get("ids", [[]])[0] or []
        metadatas = raw.get("metadatas", [[]])[0] or []
        documents = raw.get("documents", [[]])[0] or []
        distances = raw.get("distances", [[]])[0] or []

        rows: list[dict] = []
        for index, item_id in enumerate(ids):
            rows.append(
                {
                    "id": item_id,
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    "document": documents[index] if index < len(documents) else "",
                    "distance": distances[index] if index < len(distances) else None,
                }
            )
        return rows
