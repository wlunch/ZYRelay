from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from zyrelay.app.models import BlockType, DocumentBlock, LabelMention

from .category_classifier import CategoryClassifier
from .code_example_detector import CodeExampleDetector
from .config_repository import CodeRulePatternConfig
from .models import (
    CodeConventionCandidate,
    ConventionSection,
    EvidenceReference,
    RequirementLevel,
)
from .requirement_classifier import RequirementClassifier
from .rule_expression_parser import RuleExpressionParser

REQUIREMENT_WORDS = re.compile(
    r"必须|应当|应(?=使用|采用|添加|包含|遵循)|需要|禁止|不得|不允许|严禁|建议|推荐|宜|尽量|可以|可选|按需"
)
LEADING_MARKER = re.compile(
    r"^\s*(?:[-•]\s*|\d+(?:\.\d+)*[、.)\s]+|[一二三四五六七八九十]+、|"
    r"[（(][一二三四五六七八九十\d]+[）)]\s*)"
)


@dataclass(frozen=True)
class CandidateUnit:
    block: DocumentBlock
    text: str
    start_offset: int
    end_offset: int
    table_context: bool = False


class CodeConventionCandidateBuilder:
    def __init__(self, config: CodeRulePatternConfig) -> None:
        self.config = config
        self.requirements = RequirementClassifier()
        self.categories = CategoryClassifier(config)
        self.expressions = RuleExpressionParser(config)
        self.examples = CodeExampleDetector()

    def build(
        self,
        sections: list[ConventionSection],
        blocks: list[DocumentBlock],
        mentions: list[LabelMention],
    ) -> list[CodeConventionCandidate]:
        block_map = {block.block_id: block for block in blocks}
        mentions_by_block: dict[str, list[LabelMention]] = {}
        for mention in mentions:
            mentions_by_block.setdefault(mention.block_id, []).append(mention)

        document_languages = self._global_values(
            mentions, blocks, "programming_language"
        )
        document_frameworks = self._values(mentions, "framework_scope")
        result: list[CodeConventionCandidate] = []
        for section in sections:
            section_blocks = [
                block_map[block_id]
                for block_id in section.block_ids
                if block_id in block_map
            ]
            section_mentions = [
                mention
                for block in section_blocks
                for mention in mentions_by_block.get(block.block_id, [])
            ]
            heading_block = next(
                (
                    block
                    for block in section_blocks
                    if block.block_type in {BlockType.TITLE, BlockType.HEADING}
                ),
                None,
            )
            heading_mentions = (
                mentions_by_block.get(heading_block.block_id, [])
                if heading_block is not None
                else []
            )
            section_candidates: list[CodeConventionCandidate] = []
            for unit in self._units(section_blocks):
                candidate = self._candidate(
                    section,
                    unit,
                    mentions_by_block.get(unit.block.block_id, []),
                    section_mentions,
                    heading_block,
                    heading_mentions,
                    document_languages,
                    document_frameworks,
                )
                if candidate is not None:
                    section_candidates.append(candidate)
            self._attach_block_examples(
                section_candidates,
                section_blocks,
                document_languages,
            )
            result.extend(section_candidates)
        result.sort(
            key=lambda item: (
                item.source_evidence[0].block_id,
                item.source_evidence[0].start_offset,
                item.convention_id,
            )
        )
        return result

    def _candidate(
        self,
        section: ConventionSection,
        unit: CandidateUnit,
        block_mentions: list[LabelMention],
        section_mentions: list[LabelMention],
        heading_block: DocumentBlock | None,
        heading_mentions: list[LabelMention],
        document_languages: list[str],
        document_frameworks: list[str],
    ) -> CodeConventionCandidate | None:
        text = unit.text.strip()
        if not text:
            return None

        scoped_mentions = [
            mention
            for mention in block_mentions
            if mention.start_offset < unit.end_offset
            and mention.end_offset > unit.start_offset
        ]
        category = self.categories.classify(
            text,
            scoped_mentions,
            heading=section.title,
            heading_mentions=heading_mentions,
        )
        level = self.requirements.classify(text)
        expression = self.expressions.parse(f"{section.title}\n{text}")

        has_signal = (
            level != RequirementLevel.UNKNOWN
            or expression is not None
            or (unit.table_context and category.value != "general")
            or (unit.block.block_type == BlockType.LIST and category.value != "general")
        )
        if not has_signal:
            return None
        if unit.table_context and level == RequirementLevel.UNKNOWN:
            level = RequirementLevel.MANDATORY

        languages = self._values(scoped_mentions, "programming_language")
        if not languages:
            languages = self._values(section_mentions, "programming_language")
        if not languages:
            languages = document_languages
        frameworks = self._values(scoped_mentions + section_mentions, "framework_scope")
        if not frameworks:
            frameworks = document_frameworks
        tools = self._values(scoped_mentions, "tool_mapping")
        language = languages[0] if len(languages) == 1 else None
        positive, negative = self.examples.inline(text, unit.block.block_id, language)

        evidence_text = unit.block.text[unit.start_offset : unit.end_offset]
        evidence_mentions = [
            mention.mention_id
            for mention in scoped_mentions
            if mention.start_offset >= unit.start_offset
            and mention.end_offset <= unit.end_offset
        ]
        source_evidence = [
            EvidenceReference(
                document_id=unit.block.document_id,
                block_id=unit.block.block_id,
                page_no=unit.block.page_no,
                start_offset=unit.start_offset,
                end_offset=unit.end_offset,
                evidence_text=evidence_text,
                mention_ids=evidence_mentions,
            )
        ]
        if heading_block is not None and heading_block.block_id != unit.block.block_id:
            heading_mention_ids = [mention.mention_id for mention in heading_mentions]
            source_evidence.append(
                EvidenceReference(
                    document_id=heading_block.document_id,
                    block_id=heading_block.block_id,
                    page_no=heading_block.page_no,
                    start_offset=0,
                    end_offset=len(heading_block.text),
                    evidence_text=heading_block.text,
                    mention_ids=heading_mention_ids,
                )
            )
            evidence_mentions = list(
                dict.fromkeys([*evidence_mentions, *heading_mention_ids])
            )
        identity = (
            f"{unit.block.document_id}|{unit.block.block_id}|"
            f"{unit.start_offset}|{unit.end_offset}|{category.value}"
        )
        confidence = self._confidence(level, expression, unit.table_context)
        title = self._title(section.title, text, category.value)
        return CodeConventionCandidate(
            convention_id="CONV-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
            title=title,
            description=self._clean_description(text),
            category=category,
            rule_type=category,
            requirement_level=level,
            language=languages,
            frameworks=frameworks,
            applicable_scope=[expression.target] if expression else [],
            positive_examples=positive,
            negative_examples=negative,
            suggested_tools=tools,
            source_mentions=evidence_mentions,
            source_evidence=source_evidence,
            confidence=confidence,
            rule_expression=expression,
            metadata={
                "section_id": section.section_id,
                "section_title": section.title,
                "table_row": unit.table_context,
            },
        )

    def _attach_block_examples(
        self,
        candidates: list[CodeConventionCandidate],
        blocks: list[DocumentBlock],
        document_languages: list[str],
    ) -> None:
        if not candidates:
            return
        block_order = {block.block_id: block.sequence for block in blocks}
        ordered_candidates = sorted(
            candidates,
            key=lambda item: (
                block_order.get(item.source_evidence[0].block_id, -1),
                item.source_evidence[0].start_offset,
            ),
        )
        marker = "neutral"
        for block in sorted(blocks, key=lambda item: item.sequence):
            if re.fullmatch(
                r"\s*(?:正确示例|推荐写法|正例)\s*[:：]?\s*",
                block.text,
            ):
                marker = "positive"
            elif re.fullmatch(
                r"\s*(?:错误示例|反例|禁止写法|错误写法)\s*[:：]?\s*",
                block.text,
            ):
                marker = "negative"
            else:
                continue

            following = [
                item
                for item in blocks
                if item.sequence > block.sequence
                and item.block_type not in {BlockType.TITLE, BlockType.HEADING}
            ]
            if not following:
                continue
            code_block = following[0]
            language = document_languages[0] if len(document_languages) == 1 else None
            example = self.examples.from_block(
                code_block,
                example_type=marker,
                language=language,
            )
            if example is None:
                continue
            prior = [
                item
                for item in ordered_candidates
                if block_order.get(item.source_evidence[0].block_id, -1)
                <= block.sequence
            ]
            target = prior[-1] if prior else ordered_candidates[0]
            if marker == "positive":
                target.positive_examples.append(example)
            elif marker == "negative":
                target.negative_examples.append(example)

    def _units(self, blocks: list[DocumentBlock]) -> list[CandidateUnit]:
        units: list[CandidateUnit] = []
        for block in blocks:
            if block.block_type in {BlockType.TITLE, BlockType.HEADING}:
                continue
            if block.block_type == BlockType.TABLE:
                rows = block.metadata.get("table_rows")
                if not rows:
                    rows = [line.split("\t") for line in block.text.splitlines()]
                cursor = 0
                for row_index, cells in enumerate(rows):
                    row_text = "\t".join(str(cell).strip() for cell in cells)
                    start = block.text.find(row_text, cursor)
                    if start < 0 or not row_text.strip():
                        continue
                    end = start + len(row_text)
                    cursor = end
                    if row_index == 0 and self._is_table_header(cells):
                        continue
                    units.append(
                        CandidateUnit(
                            block=block,
                            text=row_text,
                            start_offset=start,
                            end_offset=end,
                            table_context=True,
                        )
                    )
                continue

            units.extend(self._text_units(block))
        return units

    @staticmethod
    def _text_units(block: DocumentBlock) -> list[CandidateUnit]:
        text = block.text
        units: list[CandidateUnit] = []
        for sentence in re.finditer(r"[^。；;\n]+[。；;\n]?", text):
            raw = sentence.group(0)
            boundaries = [0]
            if len(REQUIREMENT_WORDS.findall(raw)) > 1:
                for comma in re.finditer(r"[，,]", raw):
                    following = raw[comma.end() :].lstrip()
                    if REQUIREMENT_WORDS.match(following):
                        boundaries.append(comma.end())
            boundaries.append(len(raw))
            for start, end in zip(boundaries, boundaries[1:]):
                piece = raw[start:end]
                left = len(piece) - len(piece.lstrip())
                right = len(piece.rstrip())
                if right <= left:
                    continue
                units.append(
                    CandidateUnit(
                        block=block,
                        text=piece[left:right],
                        start_offset=sentence.start() + start + left,
                        end_offset=sentence.start() + start + right,
                    )
                )
        return units

    @staticmethod
    def _is_table_header(cells: list[object]) -> bool:
        text = " ".join(str(cell) for cell in cells)
        return "规范要求" in text or (
            "分类" in text and ("工具" in text or "规范" in text)
        )

    @staticmethod
    def _values(mentions: list[LabelMention], code: str) -> list[str]:
        return list(
            dict.fromkeys(
                mention.normalized_value
                for mention in mentions
                if mention.label_code == code
            )
        )

    def _global_values(
        self,
        mentions: list[LabelMention],
        blocks: list[DocumentBlock],
        code: str,
    ) -> list[str]:
        title_ids = {
            block.block_id
            for block in blocks
            if block.sequence == 0
            or block.block_type in {BlockType.TITLE, BlockType.HEADING}
        }
        return self._values(
            [mention for mention in mentions if mention.block_id in title_ids],
            code,
        )

    @staticmethod
    def _confidence(
        level: RequirementLevel, expression: object | None, table_context: bool
    ) -> float:
        confidence = 0.78
        if level != RequirementLevel.UNKNOWN:
            confidence += 0.08
        if expression is not None:
            confidence += 0.08
        if table_context:
            confidence += 0.03
        if level == RequirementLevel.RECOMMENDED:
            confidence = min(confidence, 0.88)
        return min(confidence, 0.95)

    @staticmethod
    def _clean_description(text: str) -> str:
        return LEADING_MARKER.sub("", text).strip()

    @staticmethod
    def _title(section_title: str, text: str, category: str) -> str:
        clean_section = LEADING_MARKER.sub("", section_title).strip()
        if clean_section and clean_section not in {"文档正文", "规范要求"}:
            return clean_section[:80]
        preview = LEADING_MARKER.sub("", text).strip().rstrip("。；;")
        return preview[:60] or f"{category} 规范"
