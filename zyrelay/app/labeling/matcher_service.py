from __future__ import annotations

import hashlib

from zyrelay.app.models import (
    DocumentBlock,
    LabelDefinition,
    LabelMention,
    MatchMethod,
)

from .alias_matcher import AliasMatcher
from .label_repository import LabelRepository
from .regex_matcher import MatchResult, RegexMatcher

METHOD_PRIORITY = {
    MatchMethod.REGEX: 4,
    MatchMethod.ALIAS_EXACT: 3,
    MatchMethod.ALIAS_FUZZY: 2,
    MatchMethod.LLM: 1,
}


class MatcherService:
    def __init__(
        self,
        repository: LabelRepository,
        *,
        fuzzy_enabled: bool = False,
        fuzzy_threshold: float = 88,
        preserve_cross_label_overlaps: bool = False,
    ) -> None:
        self.repository = repository
        self.regex = RegexMatcher()
        self.alias = AliasMatcher(
            fuzzy_enabled=fuzzy_enabled, fuzzy_threshold=fuzzy_threshold
        )
        self.preserve_cross_label_overlaps = preserve_cross_label_overlaps

    def match(
        self, blocks: list[DocumentBlock], labels: list[LabelDefinition]
    ) -> tuple[list[LabelMention], list[str]]:
        mentions: list[LabelMention] = []
        warnings: list[str] = []
        for block in blocks:
            raw_results: list[MatchResult] = []
            for label in labels:
                raw_results.extend(self.regex.match(block, label))
                raw_results.extend(self.alias.match(block, label))

            accepted, conflicts = self._resolve(
                raw_results,
                preserve_cross_label_overlaps=self.preserve_cross_label_overlaps,
            )
            warnings.extend(
                f"block={block.block_id} 标签匹配冲突：{conflict}"
                for conflict in conflicts
            )
            for result in accepted:
                if not self.repository.value_is_valid(
                    result.label_code, result.normalized_value
                ):
                    warnings.append(
                        f"block={block.block_id} label={result.label_code} "
                        f"值未通过 Ground Truth 格式校验：{result.normalized_value}"
                    )
                    continue
                mention_id = self._mention_id(block, result)
                evidence_start = max(0, result.start_offset - 20)
                evidence_end = min(len(block.text), result.end_offset + 20)
                mentions.append(
                    LabelMention(
                        mention_id=mention_id,
                        document_id=block.document_id,
                        block_id=block.block_id,
                        page_no=block.page_no,
                        label_code=result.label_code,
                        matched_text=result.matched_text,
                        normalized_value=result.normalized_value,
                        start_offset=result.start_offset,
                        end_offset=result.end_offset,
                        confidence=result.confidence,
                        match_method=result.match_method,
                        evidence=block.text[evidence_start:evidence_end],
                    )
                )
        mentions.sort(
            key=lambda item: (item.block_id, item.start_offset, item.label_code)
        )
        return mentions, warnings

    @staticmethod
    def _resolve(
        results: list[MatchResult],
        *,
        preserve_cross_label_overlaps: bool = False,
    ) -> tuple[list[MatchResult], list[str]]:
        ordered = sorted(
            results,
            key=lambda item: (
                -METHOD_PRIORITY[item.match_method],
                -(item.end_offset - item.start_offset),
                -item.specificity,
                item.label_code,
            ),
        )
        accepted: list[MatchResult] = []
        conflicts: list[str] = []
        for candidate in ordered:
            overlap = [
                item
                for item in accepted
                if candidate.start_offset < item.end_offset
                and candidate.end_offset > item.start_offset
                and (
                    not preserve_cross_label_overlaps
                    or candidate.label_code == item.label_code
                )
            ]
            if not overlap:
                accepted.append(candidate)
                continue

            same_label_container = any(
                item.label_code == candidate.label_code
                and item.start_offset <= candidate.start_offset
                and item.end_offset >= candidate.end_offset
                for item in overlap
            )
            if same_label_container:
                continue

            winner = overlap[0]
            conflicts.append(
                f"{candidate.label_code}/{candidate.match_method} 与 "
                f"{winner.label_code}/{winner.match_method} 在 "
                f"{candidate.start_offset}:{candidate.end_offset} 重叠，保留后者"
            )
        accepted.sort(
            key=lambda item: (item.start_offset, item.end_offset, item.label_code)
        )
        return accepted, conflicts

    @staticmethod
    def _mention_id(block: DocumentBlock, result: MatchResult) -> str:
        raw = (
            f"{block.document_id}|{block.block_id}|{result.label_code}|"
            f"{result.start_offset}|{result.end_offset}|{result.match_method}"
        ).encode()
        return f"MEN-{hashlib.sha256(raw).hexdigest()[:16]}"
