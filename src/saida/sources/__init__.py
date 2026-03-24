"""Source adapters for loading external data into SAIDA."""

from saida.sources.csv_source import CSVAdapter, CSVSource
from saida.sources.excel_source import ExcelAdapter, ExcelSource
from saida.sources.interfaces import SQLSourceInterface, SourceInterface
from saida.sources.json_source import JSONAdapter, JSONSource
from saida.sources.pandas_source import PandasAdapter, PandasSource
from saida.sources.sql_source import (
    MySQLAdapter,
    MySQLSource,
    PostgreSQLAdapter,
    PostgreSQLSource,
    SQLAdapter,
    SQLQueryAdapter,
    SQLQuerySource,
    SQLSource,
    SQLiteAdapter,
    SQLiteSource,
)

__all__ = [
    "CSVAdapter",
    "CSVSource",
    "ExcelAdapter",
    "ExcelSource",
    "JSONAdapter",
    "JSONSource",
    "MySQLAdapter",
    "MySQLSource",
    "PandasAdapter",
    "PandasSource",
    "PostgreSQLAdapter",
    "PostgreSQLSource",
    "SQLAdapter",
    "SQLQueryAdapter",
    "SQLQuerySource",
    "SQLSource",
    "SQLSourceInterface",
    "SQLiteAdapter",
    "SQLiteSource",
    "SourceInterface",
]
