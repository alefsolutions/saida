"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "datasets",
        sa.Column("dataset_id", sa.String(length=64), primary_key=True),
        sa.Column("source_connector", sa.String(length=64), nullable=False),
        sa.Column("source_resource_id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("parquet_path", sa.Text(), nullable=True),
        sa.Column("text_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_datasets_content_hash", "datasets", ["content_hash"])

    op.create_table(
        "resource_hashes",
        sa.Column("resource_key", sa.Text(), primary_key=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_resource_hashes_content_hash", "resource_hashes", ["content_hash"])

    op.create_table(
        "benchmark_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "semantic_embeddings",
        sa.Column("dataset_id", sa.String(length=64), sa.ForeignKey("datasets.dataset_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding_json", sa.JSON(), nullable=False),
        sa.Column("embedding_vector", sa.JSON(), nullable=True),
        sa.Column("embedding_norm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE semantic_embeddings
            ALTER COLUMN embedding_vector TYPE vector(1536)
            USING embedding_vector::text::vector
            """
        )


def downgrade() -> None:
    op.drop_table("semantic_embeddings")
    op.drop_table("benchmark_reports")
    op.drop_index("ix_resource_hashes_content_hash", table_name="resource_hashes")
    op.drop_table("resource_hashes")
    op.drop_index("ix_datasets_content_hash", table_name="datasets")
    op.drop_table("datasets")
