"""Source adapters for loading external data into SAIDA."""

from saida.sources.context import SourceContextParser
from saida.sources.csv_source import CSVAdapter, CSVSource
from saida.sources.discovery import DatasetProfiler, SchemaDiscoveryService
from saida.sources.excel_source import ExcelAdapter, ExcelSource
from saida.sources.interfaces import SQLSourceInterface, SourceInterface
from saida.sources.json_source import JSONAdapter, JSONSource
from saida.sources.pandas_source import PandasAdapter, PandasSource
from saida.sources.relational_access import RelationalAccessPlan, RelationalJoinSpec, RelationalProjectionSpec
from saida.sources.relational_schema import (
    RelationalColumnModel,
    RelationalRelationshipModel,
    RelationalSchemaModel,
    RelationalTableModel,
)
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
    "DatasetProfiler",
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
    "RelationalAccessPlan",
    "RelationalColumnModel",
    "RelationalJoinSpec",
    "RelationalProjectionSpec",
    "RelationalRelationshipModel",
    "RelationalSchemaModel",
    "RelationalTableModel",
    "SQLAdapter",
    "SQLQueryAdapter",
    "SQLQuerySource",
    "SQLSource",
    "SQLSourceInterface",
    "SchemaDiscoveryService",
    "SQLiteAdapter",
    "SQLiteSource",
    "SourceContextParser",
    "SourceInterface",
]
