from __future__ import annotations

from typing import Any

from saida.connectors.gdrive import GoogleDriveConnector
from saida.connectors.mysql import MySQLConnector
from saida.connectors.postgres import PostgresConnector


class _ScalarResult:
    def __init__(self, rows: list[Any]):
        self._rows = rows

    def all(self):
        return self._rows


class _MappingResult:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def all(self):
        return self._rows


class _ExecResult:
    def __init__(self, scalars: list[Any] | None = None, mappings: list[dict] | None = None, scalar_one: Any = None):
        self._scalars = scalars or []
        self._mappings = mappings or []
        self._scalar_one = scalar_one

    def scalars(self):
        return _ScalarResult(self._scalars)

    def mappings(self):
        return _MappingResult(self._mappings)

    def scalar_one_or_none(self):
        return self._scalar_one


class _Conn:
    def __init__(self, handler):
        self._handler = handler

    def execute(self, stmt, params=None):
        return self._handler(str(stmt), params or {})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self, handler):
        self._handler = handler

    def connect(self):
        return _Conn(self._handler)


def test_postgres_connector_discover_and_load():
    def handler(sql: str, params: dict):
        if "information_schema.tables" in sql:
            assert params["schema"] == "public"
            return _ExecResult(scalars=["orders", "users"])
        if 'SELECT * FROM "public"."orders"' in sql:
            return _ExecResult(mappings=[{"id": 1, "amount": 5.5}])
        raise AssertionError(sql)

    conn = PostgresConnector(
        dsn="postgresql+psycopg://u:p@localhost:5432/db", schema="public", engine=_Engine(handler)
    )

    assert conn.discover() == ["public.orders", "public.users"]
    assert conn.load("public.orders") == [{"id": 1, "amount": 5.5}]


def test_mysql_connector_discover_and_load():
    def handler(sql: str, params: dict):
        if "SELECT DATABASE()" in sql:
            return _ExecResult(scalar_one="salesdb")
        if "information_schema.tables" in sql:
            assert params["database"] == "salesdb"
            return _ExecResult(scalars=["orders"])
        if "SELECT * FROM `salesdb`.`orders`" in sql:
            return _ExecResult(mappings=[{"id": 42, "status": "paid"}])
        raise AssertionError(sql)

    conn = MySQLConnector(dsn="mysql+pymysql://u:p@localhost:3306/salesdb", engine=_Engine(handler))

    assert conn.discover() == ["salesdb.orders"]
    assert conn.load("orders") == [{"id": 42, "status": "paid"}]


class _FilesAPI:
    def __init__(self):
        self._meta = {
            "1": {"id": "1", "name": "doc", "mimeType": "application/vnd.google-apps.document", "size": "10"},
            "2": {"id": "2", "name": "bin", "mimeType": "application/pdf", "size": "10"},
        }

    def list(self, **kwargs):
        class _Req:
            def execute(self_nonlocal):
                return {"files": [{"id": "1"}, {"id": "2"}]}

        return _Req()

    def get(self, fileId, fields):
        class _Req:
            def execute(self_nonlocal):
                return self._meta[fileId]

        return _Req()

    def export_media(self, fileId, mimeType):
        return {"type": "export", "fileId": fileId, "mimeType": mimeType}

    def get_media(self, fileId):
        return {"type": "media", "fileId": fileId}


class _DriveService:
    def __init__(self):
        self._files = _FilesAPI()

    def files(self):
        return self._files


class _FakeDownloader:
    def __init__(self, buffer, request):
        payload = b"exported" if request["type"] == "export" else b"binary"
        buffer.write(payload)
        self._done = False

    def next_chunk(self):
        if self._done:
            return (None, True)
        self._done = True
        return (None, True)


def test_gdrive_connector_discover_and_load():
    conn = GoogleDriveConnector(service=_DriveService(), downloader_cls=_FakeDownloader)

    ids = conn.discover()
    assert ids == ["1", "2"]

    doc = conn.load("1")
    binary = conn.load("2")

    assert doc["metadata"]["id"] == "1"
    assert doc["content"] == b"exported"
    assert binary["content"] == b"binary"
