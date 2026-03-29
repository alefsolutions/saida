"""Schema-aware prompt entity extraction for optional plan generation."""

from __future__ import annotations

from calendar import month_abbr, month_name
from dataclasses import dataclass, field
import re

from saida.core.contracts import DatasetProfile, SourceContext

_WORD_CHARS = "a-z0-9_"
_FIELD_PLACEHOLDER = "[ENTITY]"


def _bounded_pattern(value: str) -> str:
    return rf"(?<![{_WORD_CHARS}]){re.escape(value)}(?![{_WORD_CHARS}])"


@dataclass(slots=True)
class PromptEntity:
    """Resolved entity span extracted from a prompt."""

    kind: str
    value: str
    raw_text: str
    start: int
    end: int


@dataclass(slots=True)
class EntityExtractionResult:
    """Structured prompt surface produced before intent inference."""

    question: str
    masked_question: str
    column_entities: list[PromptEntity] = field(default_factory=list)
    literal_entities: list[PromptEntity] = field(default_factory=list)

    @property
    def masked_lower_question(self) -> str:
        return self.masked_question.lower()

    @property
    def ordered_columns(self) -> list[str]:
        ordered = [entity.value for entity in self.column_entities]
        return list(dict.fromkeys(ordered))

    def summary_text(self) -> str:
        column_summary = ", ".join(self.ordered_columns) if self.ordered_columns else "none"
        literal_summary = ", ".join(f"{entity.kind}:{entity.value}" for entity in self.literal_entities) or "none"
        return (
            f"Resolved fields: {column_summary}. "
            f"Masked question: {self.masked_question}. "
            f"Resolved literals: {literal_summary}."
        )


class PromptEntityExtractor:
    """Resolve schema entities before any operator or intent inference."""

    def extract(
        self,
        question: str,
        profile: DatasetProfile,
        context: SourceContext | None = None,
    ) -> EntityExtractionResult:
        lowered = question.lower()
        column_entities = self._extract_column_entities(question, lowered, profile, context)
        masked_question = self._mask_question(question, column_entities)
        literal_entities = self._extract_literal_entities(question, masked_question.lower())
        return EntityExtractionResult(
            question=question,
            masked_question=masked_question,
            column_entities=column_entities,
            literal_entities=literal_entities,
        )

    def _extract_column_entities(
        self,
        question: str,
        lowered: str,
        profile: DatasetProfile,
        context: SourceContext | None,
    ) -> list[PromptEntity]:
        candidates: list[tuple[str, str]] = []
        seen_candidates: set[tuple[str, str]] = set()
        profile_columns = {column.name.lower(): column.name for column in profile.columns}

        for column in profile.columns:
            for alias in self._column_aliases(column.name):
                candidate = (alias, column.name)
                if candidate in seen_candidates:
                    continue
                seen_candidates.add(candidate)
                candidates.append(candidate)

        if context is not None:
            for context_name in (*context.field_descriptions.keys(), *context.metric_definitions.keys()):
                resolved_name = profile_columns.get(context_name.lower())
                if resolved_name is None:
                    continue
                for alias in self._column_aliases(resolved_name):
                    candidate = (alias, resolved_name)
                    if candidate in seen_candidates:
                        continue
                    seen_candidates.add(candidate)
                    candidates.append(candidate)

        candidates.sort(key=lambda item: (-len(item[0]), item[0]))
        reserved_spans: list[tuple[int, int]] = []
        entities: list[PromptEntity] = []
        for alias, resolved_name in candidates:
            pattern = _bounded_pattern(alias)
            for match in re.finditer(pattern, lowered):
                span = (match.start(), match.end())
                if any(span[0] < end and span[1] > start for start, end in reserved_spans):
                    continue
                raw_text = question[match.start() : match.end()]
                entities.append(
                    PromptEntity(
                        kind="column",
                        value=resolved_name,
                        raw_text=raw_text,
                        start=match.start(),
                        end=match.end(),
                    )
                )
                reserved_spans.append(span)

        entities.sort(key=lambda entity: entity.start)
        return entities

    def _mask_question(self, question: str, column_entities: list[PromptEntity]) -> str:
        if not column_entities:
            return question
        parts: list[str] = []
        cursor = 0
        for entity in column_entities:
            parts.append(question[cursor : entity.start])
            parts.append(_FIELD_PLACEHOLDER)
            cursor = entity.end
        parts.append(question[cursor:])
        return "".join(parts)

    def _extract_literal_entities(self, question: str, masked_lowered: str) -> list[PromptEntity]:
        literals: list[PromptEntity] = []
        for match in re.finditer(r"\b(19|20)\d{2}\b", question):
            literals.append(
                PromptEntity(
                    kind="year_literal",
                    value=match.group(0),
                    raw_text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )

        month_tokens = [month_name[index].lower() for index in range(1, 13)] + [month_abbr[index].lower() for index in range(1, 13)]
        for token in month_tokens:
            for match in re.finditer(_bounded_pattern(token), masked_lowered):
                literals.append(
                    PromptEntity(
                        kind="month_literal",
                        value=token,
                        raw_text=question[match.start() : match.end()],
                        start=match.start(),
                        end=match.end(),
                    )
                )

        for match in re.finditer(r"\bq([1-4])\b", masked_lowered):
            literals.append(
                PromptEntity(
                    kind="quarter_literal",
                    value=match.group(0),
                    raw_text=question[match.start() : match.end()],
                    start=match.start(),
                    end=match.end(),
                )
            )
        for match in re.finditer(r"\b-?\d+(?:\.\d+)?\b", masked_lowered):
            literals.append(
                PromptEntity(
                    kind="numeric_literal",
                    value=match.group(0),
                    raw_text=question[match.start() : match.end()],
                    start=match.start(),
                    end=match.end(),
                )
            )

        literals.sort(key=lambda entity: entity.start)
        deduped: list[PromptEntity] = []
        seen = set()
        for entity in literals:
            key = (entity.kind, entity.start, entity.end, entity.value)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entity)
        return deduped

    def _column_aliases(self, column_name: str) -> list[str]:
        lowered = column_name.lower()
        aliases = [lowered]
        spaced = lowered.replace("_", " ")
        if spaced != lowered:
            aliases.append(spaced)
        if "_" not in lowered and not lowered.endswith("s"):
            aliases.append(f"{lowered}s")
        if " " in spaced and not spaced.endswith("s"):
            aliases.append(f"{spaced}s")
        return list(dict.fromkeys(alias for alias in aliases if alias))
