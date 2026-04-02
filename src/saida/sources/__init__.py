"""Source adapters for loading external data into SAIDA."""

from saida.sources.context import SourceContextParser
from saida.sources.csv_source import CSVAdapter, CSVSource
from saida.sources.discovery import DatasetProfiler, SchemaDiscoveryService
from saida.sources.excel_source import ExcelAdapter, ExcelSource
from saida.sources.interfaces import SQLSourceInterface, SourceInterface
from saida.sources.json_source import JSONAdapter, JSONSource
from saida.sources.pandas_source import PandasAdapter, PandasSource
from saida.sources.relational_access import (
    RelationalAccessPlan,
    RelationalFilterSpec,
    RelationalJoinSpec,
    RelationalOrderSpec,
    RelationalProjectionSpec,
)
from saida.sources.relational_semantics import RelationalTableSemantics, infer_relational_table_semantics
from saida.sources.relational_schema import (
    RelationalColumnModel,
    RelationalIndexModel,
    RelationalRelationshipModel,
    RelationalSchemaModel,
    RelationalTableModel,
    RelationalUniqueConstraintModel,
)
from saida.sources.sql_rendering import render_relational_access_query
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
    "RelationalFilterSpec",
    "RelationalIndexModel",
    "RelationalJoinSpec",
    "RelationalOrderSpec",
    "RelationalProjectionSpec",
    "RelationalRelationshipModel",
    "RelationalSchemaModel",
    "RelationalTableSemantics",
    "RelationalTableModel",
    "RelationalUniqueConstraintModel",
    "SQLAdapter",
    "SQLQueryAdapter",
    "SQLQuerySource",
    "SQLSource",
    "SQLSourceInterface",
    "render_relational_access_query",
    "SchemaDiscoveryService",
    "SQLiteAdapter",
    "SQLiteSource",
    "SourceContextParser",
    "SourceInterface",
    "infer_relational_table_semantics",
]
