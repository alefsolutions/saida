from __future__ import annotations

from pathlib import Path

import pytest

from saida.sources import SourceContextParser
from saida.exceptions import ContextError


def test_parse_file_raises_for_missing_context_file(tmp_path: Path) -> None:
    parser = SourceContextParser()

    with pytest.raises(ContextError):
        parser.parse_file(tmp_path / "missing.md")


def test_parse_supports_colon_and_equals_syntax() -> None:
    markdown = """
# Dataset: Sales

## Metrics
revenue = total revenue
profit: net profit

## Field Descriptions
posted_at: posting date
customer_id = customer identifier
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.metric_definitions["revenue"] == "total revenue"
    assert context.metric_definitions["profit"] == "net profit"
    assert context.field_descriptions["posted_at"] == "posting date"
    assert context.field_descriptions["customer_id"] == "customer identifier"


def test_parse_collects_rule_and_freshness_alias_sections() -> None:
    markdown = """
# Summary
sales data

## Rules
- cancelled orders must be excluded

## Freshness Expectations
- refresh daily
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.business_rules == ["cancelled orders must be excluded"]
    assert context.freshness_notes == ["refresh daily"]


def test_parse_uses_dataset_title_as_summary_fallback() -> None:
    markdown = """
# Dataset: Sales Facts

## Metrics
revenue: total revenue
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.source_summary == "Sales Facts"


def test_parse_collects_caveats_from_warning_alias() -> None:
    markdown = """
# Summary
sales data

## Warnings
- source backfills weekly
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.caveats == ["source backfills weekly"]


def test_parse_collects_trusted_dates_and_identifiers_from_aliases() -> None:
    markdown = """
# Summary
sales data

## Trusted Dates
- posted_at

## Identifiers
- customer_id
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.trusted_date_fields == ["posted_at"]
    assert context.preferred_identifiers == ["customer_id"]


def test_parse_returns_empty_context_for_blank_markdown() -> None:
    context = SourceContextParser().parse("")

    assert context.source_summary is None
    assert context.metric_definitions == {}
    assert context.business_rules == []


def test_parse_combines_multiple_metric_section_aliases() -> None:
    markdown = """
# Summary
sales data

## Metrics
revenue: total revenue

## Metric Definitions
profit: net profit
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.metric_definitions == {"revenue": "total revenue", "profit": "net profit"}


_SUMMARY_HEADING_CASES = [
    (
        heading,
        expected,
    )
    for heading, expected in [
        ("# Dataset: Sales", "Sales"),
        ("# Dataset: Sales Facts", "Sales Facts"),
        ("# Summary", "sales summary"),
        ("# Source Summary", "warehouse extract"),
        ("# Source", "crm export"),
    ]
    for _ in range(19)
]


@pytest.mark.parametrize(("heading", "expected_summary"), _SUMMARY_HEADING_CASES[:95])
def test_parse_many_summary_heading_variants(heading: str, expected_summary: str) -> None:
    markdown = f"""
{heading}
{expected_summary}

## Metrics
revenue: total revenue
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.source_summary == expected_summary
    assert context.metric_definitions["revenue"] == "total revenue"
