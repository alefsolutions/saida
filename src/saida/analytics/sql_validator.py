from __future__ import annotations

import re


class SQLValidationError(ValueError):
    pass


class SQLValidator:
    """Strict SQL validator for deterministic, read-only analytics execution."""

    FORBIDDEN_PATTERN = re.compile(
        r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|call|pragma|truncate|grant|revoke)\b",
        flags=re.IGNORECASE,
    )

    def validate(self, sql: str) -> None:
        normalized = sql.strip()
        if not normalized:
            raise SQLValidationError("SQL is empty.")
        if len(normalized) > 5000:
            raise SQLValidationError("SQL exceeds maximum allowed length.")
        if ";" in normalized:
            raise SQLValidationError("Semicolons are not allowed in analytics SQL.")
        if not normalized.lower().startswith("select"):
            raise SQLValidationError("Only SELECT statements are allowed.")
        if "read_parquet(" not in normalized.lower():
            raise SQLValidationError("SQL must read from parquet via read_parquet().")
        if self.FORBIDDEN_PATTERN.search(normalized):
            raise SQLValidationError("Forbidden SQL keyword detected.")
