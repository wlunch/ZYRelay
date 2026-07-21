from __future__ import annotations

from collections import defaultdict

from .models import CodeConventionCandidate, ConventionIndex


class ConventionIndexBuilder:
    def build(self, candidates: list[CodeConventionCandidate]) -> ConventionIndex:
        by_category: dict[str, list[dict]] = defaultdict(list)
        by_language: dict[str, list[str]] = defaultdict(list)
        by_level: dict[str, list[str]] = defaultdict(list)
        by_tool: dict[str, list[str]] = defaultdict(list)
        by_document: dict[str, list[str]] = defaultdict(list)

        for candidate in candidates:
            evidence = candidate.source_evidence[0]
            summary = {
                "convention_id": candidate.convention_id,
                "document_id": evidence.document_id,
                "title": candidate.title,
                "requirement_level": candidate.requirement_level.value,
                "languages": candidate.language,
                "block_id": evidence.block_id,
                "page_no": evidence.page_no,
                "confidence": candidate.confidence,
            }
            by_category[candidate.category.value].append(summary)
            by_level[candidate.requirement_level.value].append(candidate.convention_id)
            by_document[evidence.document_id].append(candidate.convention_id)
            for language in candidate.language:
                by_language[language].append(candidate.convention_id)
            for tool in candidate.suggested_tools:
                by_tool[tool].append(candidate.convention_id)

        return ConventionIndex(
            by_category=dict(by_category),
            by_language=dict(by_language),
            by_requirement_level=dict(by_level),
            by_tool=dict(by_tool),
            by_document=dict(by_document),
        )
