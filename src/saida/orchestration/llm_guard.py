from __future__ import annotations

import json
import re


class LLMNumericPolicyError(ValueError):
    pass


NUMERIC_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_numeric_tokens(text: str) -> set[str]:
    return set(NUMERIC_PATTERN.findall(text))


def enforce_no_unverified_numbers(query: str, analytics_rows: list[dict], explanation: str) -> None:
    """Enforce that LLM cannot introduce numeric claims beyond verified analytics outputs."""
    allowed = _extract_numeric_tokens(query)
    if analytics_rows:
        allowed.update(_extract_numeric_tokens(json.dumps(analytics_rows, ensure_ascii=True)))

    found = _extract_numeric_tokens(explanation)
    disallowed = sorted(found - allowed)
    if disallowed:
        raise LLMNumericPolicyError(
            f"LLM numeric policy violation: unverified numeric tokens in explanation: {', '.join(disallowed)}"
        )
