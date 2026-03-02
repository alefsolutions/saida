from __future__ import annotations

from math import sqrt
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from saida.models.types import DatasetAsset
from saida.storage.db import session_scope
from saida.storage.schema import DEFAULT_EMBEDDING_DIMENSIONS
from saida.storage.schema import DatasetRow, SemanticEmbeddingRow


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    an = sqrt(sum(x * x for x in a[:n]))
    bn = sqrt(sum(x * x for x in b[:n]))
    if an == 0.0 or bn == 0.0:
        return 0.0
    return dot / (an * bn)


class SemanticStore:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    @staticmethod
    def _normalize_vector(values: list[float], dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS) -> list[float]:
        if len(values) == dimensions:
            return values
        if len(values) > dimensions:
            return values[:dimensions]
        return values + ([0.0] * (dimensions - len(values)))

    def upsert_dataset(self, asset: DatasetAsset, embedding: list[float]) -> None:
        norm = sqrt(sum(x * x for x in embedding)) if embedding else 0.0
        normalized = self._normalize_vector(embedding)
        with session_scope(self.session_factory) as session:
            row = session.get(SemanticEmbeddingRow, asset.dataset_id)
            if row is None:
                session.add(
                    SemanticEmbeddingRow(
                        dataset_id=asset.dataset_id,
                        embedding_json=embedding,
                        embedding_vector=normalized,
                        embedding_norm=norm,
                    )
                )
            else:
                row.embedding_json = embedding
                row.embedding_vector = normalized
                row.embedding_norm = norm

    def retrieve(self, query_embedding: list[float], limit: int = 5) -> list[dict]:
        pgvector_rows = self._retrieve_with_pgvector(query_embedding, limit)
        if pgvector_rows is not None:
            return pgvector_rows

        with session_scope(self.session_factory) as session:
            rows: list[tuple[DatasetRow, SemanticEmbeddingRow]] = session.execute(
                select(DatasetRow, SemanticEmbeddingRow).join(
                    SemanticEmbeddingRow, DatasetRow.dataset_id == SemanticEmbeddingRow.dataset_id
                )
            ).all()

        scored: list[dict[str, Any]] = []
        for dataset_row, embedding_row in rows:
            emb = embedding_row.embedding_json or []
            scored.append(
                {
                    "dataset": DatasetAsset(
                        dataset_id=dataset_row.dataset_id,
                        source_connector=dataset_row.source_connector,
                        source_resource_id=dataset_row.source_resource_id,
                        hash=dataset_row.content_hash,
                        kind=dataset_row.kind,
                        parquet_path=dataset_row.parquet_path,
                        text_summary=dataset_row.text_summary,
                        metadata=dataset_row.metadata_json or {},
                    ),
                    "score": _cosine(query_embedding, emb),
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def _retrieve_with_pgvector(self, query_embedding: list[float], limit: int) -> list[dict] | None:
        with session_scope(self.session_factory) as session:
            if session.bind is None or session.bind.dialect.name != "postgresql":
                return None
            vector = self._normalize_vector(query_embedding)
            vector_literal = "[" + ",".join(str(v) for v in vector) + "]"
            sql = text(
                """
                SELECT d.dataset_id,
                       d.source_connector,
                       d.source_resource_id,
                       d.content_hash,
                       d.kind,
                       d.parquet_path,
                       d.text_summary,
                       d.metadata_json,
                       1 - (se.embedding_vector <=> CAST(:q AS vector)) AS score
                FROM semantic_embeddings se
                JOIN datasets d ON d.dataset_id = se.dataset_id
                WHERE se.embedding_vector IS NOT NULL
                ORDER BY se.embedding_vector <=> CAST(:q AS vector)
                LIMIT :lim
                """
            )
            try:
                rows = session.execute(sql, {"q": vector_literal, "lim": limit}).mappings().all()
            except Exception:
                return None

        out: list[dict] = []
        for row in rows:
            out.append(
                {
                    "dataset": DatasetAsset(
                        dataset_id=row["dataset_id"],
                        source_connector=row["source_connector"],
                        source_resource_id=row["source_resource_id"],
                        hash=row["content_hash"],
                        kind=row["kind"],
                        parquet_path=row["parquet_path"],
                        text_summary=row["text_summary"],
                        metadata=row["metadata_json"] or {},
                    ),
                    "score": float(row["score"]),
                }
            )
        return out
