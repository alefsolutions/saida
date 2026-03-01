from __future__ import annotations


def parse_text(content: str) -> dict:
    return {"text": content, "length": len(content)}