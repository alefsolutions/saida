from __future__ import annotations


def emit_metric(name: str, value: float) -> dict:
    return {"metric": name, "value": value}