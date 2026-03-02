from __future__ import annotations

from pathlib import Path

import duckdb


class ParquetStore:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def csv_to_parquet(self, csv_path: str, dataset_id: str) -> str:
        out = self.root / f"{dataset_id}.parquet"
        con = duckdb.connect()
        try:
            in_path = csv_path.replace("\\", "/").replace("'", "''")
            out_path = str(out).replace("\\", "/").replace("'", "''")
            con.execute(
                f"COPY (SELECT * FROM read_csv_auto('{in_path}', sample_size=-1, strict_mode=false, header=true)) "
                f"TO '{out_path}' (FORMAT PARQUET)"
            )
        finally:
            con.close()
        return str(out)

    def json_to_parquet(self, json_path: str, dataset_id: str) -> str:
        out = self.root / f"{dataset_id}.parquet"
        con = duckdb.connect()
        try:
            in_path = json_path.replace("\\", "/").replace("'", "''")
            out_path = str(out).replace("\\", "/").replace("'", "''")
            con.execute(f"COPY (SELECT * FROM read_json_auto('{in_path}')) TO '{out_path}' (FORMAT PARQUET)")
        finally:
            con.close()
        return str(out)
