from saida_core.adapters.data_sources.sql.connector import SQLDataSource


def test_sql_connector_placeholder():
    source = SQLDataSource()
    rows = source.fetch("select 1")
    assert rows and rows[0]["source"] == "sql"