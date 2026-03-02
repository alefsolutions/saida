from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - optional dependency in some environments
    Vector = None

DEFAULT_EMBEDDING_DIMENSIONS = 1536


class Base(DeclarativeBase):
    pass


class VectorCompat(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(DEFAULT_EMBEDDING_DIMENSIONS))
        return dialect.type_descriptor(JSON())


class DatasetRow(Base):
    __tablename__ = "datasets"

    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_connector: Mapped[str] = mapped_column(String(64), nullable=False)
    source_resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    parquet_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    embedding: Mapped["SemanticEmbeddingRow"] = relationship(back_populates="dataset", uselist=False)


class ResourceHashRow(Base):
    __tablename__ = "resource_hashes"

    resource_key: Mapped[str] = mapped_column(Text, primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BenchmarkReportRow(Base):
    __tablename__ = "benchmark_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SemanticEmbeddingRow(Base):
    __tablename__ = "semantic_embeddings"

    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.dataset_id", ondelete="CASCADE"), primary_key=True)
    embedding_json: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    embedding_vector: Mapped[list[float] | None] = mapped_column(VectorCompat(), nullable=True)
    embedding_norm: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    dataset: Mapped[DatasetRow] = relationship(back_populates="embedding")
