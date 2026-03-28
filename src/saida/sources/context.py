"""Markdown semantic context parsing for source-side dataset metadata."""

from __future__ import annotations

from pathlib import Path

from saida.core.contracts import SourceContext
from saida.exceptions import ContextError


class SourceContextParser:
    """Parse semantic markdown into a SourceContext."""

    SUMMARY_SECTIONS = ("dataset", "summary", "source summary", "source")
    TABLE_SECTIONS = ("table descriptions", "tables", "table description")
    FIELD_SECTIONS = ("field descriptions", "fields", "field description", "columns", "column descriptions")
    METRIC_SECTIONS = ("metrics", "metric definitions", "metric definition")
    BUSINESS_RULE_SECTIONS = ("important rules", "business rules", "rules")
    CAVEAT_SECTIONS = ("caveats", "warnings")
    TRUSTED_DATE_SECTIONS = ("trusted date field", "trusted date fields", "date fields", "trusted dates")
    IDENTIFIER_SECTIONS = ("preferred identifiers", "identifiers", "preferred identifier")
    FRESHNESS_SECTIONS = ("freshness", "freshness notes", "freshness expectations")

    def parse_file(self, path: str | Path) -> SourceContext:
        """Load and parse a markdown context file."""
        markdown_path = Path(path)
        if not markdown_path.exists():
            raise ContextError(f"Context file not found: {markdown_path}")

        try:
            markdown = markdown_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ContextError(f"Failed to read context file: {markdown_path}") from exc

        return self.parse(markdown)

    def parse(self, markdown: str) -> SourceContext:
        """Parse markdown text into a tolerant semantic context object."""
        sections = self._split_sections(markdown)
        return SourceContext(
            raw_markdown=markdown,
            source_summary=self._parse_summary(sections),
            table_descriptions=self._parse_mapping_sections(sections, self.TABLE_SECTIONS),
            field_descriptions=self._parse_mapping_sections(sections, self.FIELD_SECTIONS),
            metric_definitions=self._parse_mapping_sections(sections, self.METRIC_SECTIONS),
            business_rules=self._parse_list_sections(sections, self.BUSINESS_RULE_SECTIONS),
            caveats=self._parse_list_sections(sections, self.CAVEAT_SECTIONS),
            trusted_date_fields=self._parse_list_sections(sections, self.TRUSTED_DATE_SECTIONS),
            preferred_identifiers=self._parse_list_sections(sections, self.IDENTIFIER_SECTIONS),
            freshness_notes=self._parse_list_sections(sections, self.FRESHNESS_SECTIONS),
        )

    def _split_sections(self, markdown: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {"dataset": []}
        current_section = "dataset"
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if line.startswith("#"):
                raw_heading = line.lstrip("#").strip()
                current_section = self._normalize_heading(raw_heading)
                sections.setdefault(current_section, [])
                if current_section.startswith("dataset:"):
                    sections.setdefault("__dataset_titles__", []).append(raw_heading.split(":", 1)[1].strip())
                continue
            if line:
                sections.setdefault(current_section, []).append(line)
        return sections

    def _parse_mapping(self, lines: list[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for line in lines:
            cleaned = line.lstrip("-* ").strip()
            if "=" in cleaned:
                key, value = cleaned.split("=", 1)
            elif ":" in cleaned:
                key, value = cleaned.split(":", 1)
            else:
                continue
            mapping[key.strip()] = value.strip()
        return mapping

    def _parse_list(self, lines: list[str]) -> list[str]:
        values: list[str] = []
        for line in lines:
            cleaned = line.lstrip("-* ").strip()
            if cleaned:
                values.append(cleaned)
        return values

    def _parse_summary(self, sections: dict[str, list[str]]) -> str | None:
        for section_name in self.SUMMARY_SECTIONS:
            summary = self._join_section(sections.get(section_name))
            if summary:
                return summary

        dataset_titles = sections.get("__dataset_titles__", [])
        if dataset_titles:
            return dataset_titles[0]

        return None

    def _parse_mapping_sections(
        self,
        sections: dict[str, list[str]],
        section_names: tuple[str, ...],
    ) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for section_name in section_names:
            section_lines = sections.get(section_name, [])
            mapping.update(self._parse_mapping(section_lines))
        return mapping

    def _parse_list_sections(
        self,
        sections: dict[str, list[str]],
        section_names: tuple[str, ...],
    ) -> list[str]:
        values: list[str] = []
        for section_name in section_names:
            values.extend(self._parse_list(sections.get(section_name, [])))
        return values

    def _normalize_heading(self, heading: str) -> str:
        return heading.strip().lower()

    def _join_section(self, lines: list[str] | None) -> str | None:
        if not lines:
            return None
        return " ".join(line.strip() for line in lines if line.strip()) or None
