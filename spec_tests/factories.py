from __future__ import annotations

import json
from typing import Any

import pandas as pd

from saida.core.contracts import Dataset


def build_sales_dataset() -> Dataset:
    return Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "posted_at": [
                    "2025-10-01",
                    "2025-11-01",
                    "2025-12-01",
                    "2026-01-01",
                    "2026-02-01",
                    "2026-03-01",
                ],
                "revenue": [100.0, 120.0, 90.0, 80.0, 110.0, 130.0],
                "region": ["West", "East", "West", "East", "West", "East"],
                "segment": ["SMB", "Enterprise", "SMB", "Enterprise", "SMB", "Enterprise"],
            }
        ),
    )


def build_support_dataset() -> Dataset:
    return Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3", "T4", "T5", "T6", "T7"],
                "created_at": [
                    "2026-01-01",
                    "2026-01-12",
                    "2026-02-03",
                    "2026-02-14",
                    "2026-03-05",
                    "2026-04-16",
                    "2026-05-07",
                ],
                "resolution_hours": [2.1, 5.4, 6.8, 4.2, 7.1, 8.0, 3.5],
                "csat_score": [4.7, None, 3.6, 4.1, 3.5, 3.2, 4.4],
                "team": ["Support", "Support", "Platform", "Platform", "Support", "Platform", "Support"],
                "priority": ["Low", "Medium", "High", "Low", "High", "Medium", "Low"],
                "reopened_flag": ["no", "no", "yes", "yes", "no", "yes", "no"],
            }
        ),
    )


def build_support_schema_dataset() -> Dataset:
    return Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "created_at": ["2026-01-01", "2026-01-02"],
                "team": ["Support", "Platform"],
                "priority": ["High", "Low"],
                "channel": ["Email", "Phone"],
                "resolution_hours": [4.2, 6.1],
                "csat_score": [4.8, 4.1],
                "reopened_flag": ["no", "yes"],
            }
        ),
    )


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))
