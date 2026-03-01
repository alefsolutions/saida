from __future__ import annotations


def build_keyword_query(keyword: str, table: str = "events") -> str:
    return f"SELECT * FROM {table} WHERE name LIKE '%{keyword}%';"