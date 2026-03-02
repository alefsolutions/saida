from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from saida.models.types import DatasetAsset
from saida.storage.db import session_scope
from saida.storage.schema import BenchmarkReportRow, DatasetRow, ResourceHashRow


class ControlPlaneStore:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def is_unchanged(self, resource_key: str, content_hash: str) -> bool:
        with session_scope(self.session_factory) as session:
            row = session.get(ResourceHashRow, resource_key)
            return bool(row and row.content_hash == content_hash)

    def update_hash(self, resource_key: str, content_hash: str) -> None:
        with session_scope(self.session_factory) as session:
            row = session.get(ResourceHashRow, resource_key)
            if row is None:
                row = ResourceHashRow(resource_key=resource_key, content_hash=content_hash)
                session.add(row)
            else:
                row.content_hash = content_hash

    def upsert_dataset(self, asset: DatasetAsset) -> None:
        with session_scope(self.session_factory) as session:
            row = session.get(DatasetRow, asset.dataset_id)
            if row is None:
                row = DatasetRow(
                    dataset_id=asset.dataset_id,
                    source_connector=asset.source_connector,
                    source_resource_id=asset.source_resource_id,
                    content_hash=asset.hash,
                    kind=asset.kind,
                    parquet_path=asset.parquet_path,
                    text_summary=asset.text_summary,
                    metadata_json=asset.metadata,
                )
                session.add(row)
            else:
                row.source_connector = asset.source_connector
                row.source_resource_id = asset.source_resource_id
                row.content_hash = asset.hash
                row.kind = asset.kind
                row.parquet_path = asset.parquet_path
                row.text_summary = asset.text_summary
                row.metadata_json = asset.metadata

    def list_datasets(self) -> list[DatasetAsset]:
        with session_scope(self.session_factory) as session:
            rows = session.scalars(select(DatasetRow).order_by(DatasetRow.created_at.desc())).all()
            return [
                DatasetAsset(
                    dataset_id=row.dataset_id,
                    source_connector=row.source_connector,
                    source_resource_id=row.source_resource_id,
                    hash=row.content_hash,
                    kind=row.kind,
                    parquet_path=row.parquet_path,
                    text_summary=row.text_summary,
                    metadata=row.metadata_json or {},
                )
                for row in rows
            ]

    def save_benchmark_report(self, report: dict) -> None:
        with session_scope(self.session_factory) as session:
            session.add(BenchmarkReportRow(report_json=report))

    def list_benchmark_reports(self) -> list[dict]:
        with session_scope(self.session_factory) as session:
            rows = session.scalars(select(BenchmarkReportRow).order_by(BenchmarkReportRow.created_at.desc())).all()
            return [row.report_json for row in rows]
