from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from saida.models.types import BenchmarkCase


@dataclass(slots=True)
class BenchmarkThresholds:
    ais: float = 95.0
    ses: float = 90.0
    ris: float = 90.0
    sss: float = 95.0


@dataclass(slots=True)
class BenchmarkSuite:
    name: str
    description: str
    thresholds: BenchmarkThresholds
    cases: list[BenchmarkCase]


def load_benchmark_suite(path: str) -> BenchmarkSuite:
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))

    thresholds_in = payload.get("thresholds", {})
    thresholds = BenchmarkThresholds(
        ais=float(thresholds_in.get("ais", 95.0)),
        ses=float(thresholds_in.get("ses", 90.0)),
        ris=float(thresholds_in.get("ris", 90.0)),
        sss=float(thresholds_in.get("sss", 95.0)),
    )

    cases = [
        BenchmarkCase(
            name=str(c["name"]),
            query=str(c["query"]),
            expected_sql_nonempty=bool(c.get("expected_sql_nonempty", False)),
            expected_rows_min=int(c.get("expected_rows_min", 0)),
        )
        for c in payload.get("cases", [])
    ]

    return BenchmarkSuite(
        name=str(payload.get("name", p.stem)),
        description=str(payload.get("description", "")),
        thresholds=thresholds,
        cases=cases,
    )
