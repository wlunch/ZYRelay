from __future__ import annotations

import hashlib
import re

from zyrelay.app.models import BlockType, DocumentBlock

from .models import ConventionSection


NUMBERED_HEADING = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[、.\s]|[一二三四五六七八九十]+、|"
    r"[（(][一二三四五六七八九十\d]+[）)]|第[一二三四五六七八九十\d]+条)"
)
HEADING_HINTS = ("规范", "要求", "禁止", "建议", "示例", "说明", "原则")


class ConventionSectionDetector:
    def detect(self, blocks: list[DocumentBlock]) -> list[ConventionSection]:
        if not blocks:
            return []

        sections: list[ConventionSection] = []
        current_title = "文档正文"
        current_level = 0
        current_blocks: list[DocumentBlock] = []
        current_confidence = 0.55

        def flush() -> None:
            nonlocal current_blocks
            if not current_blocks:
                return
            pages = [block.page_no for block in current_blocks if block.page_no]
            identity = "|".join(block.block_id for block in current_blocks)
            sections.append(
                ConventionSection(
                    section_id="SEC-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
                    title=self._clean_title(current_title),
                    level=current_level,
                    block_ids=[block.block_id for block in current_blocks],
                    text="\n".join(block.text for block in current_blocks),
                    start_page=min(pages) if pages else None,
                    end_page=max(pages) if pages else None,
                    confidence=current_confidence,
                )
            )
            current_blocks = []

        for block in sorted(blocks, key=lambda item: item.sequence):
            if self._is_heading(block):
                flush()
                current_title = block.text
                current_level = block.heading_level or self._numbered_level(block.text)
                current_confidence = self._heading_confidence(block)
                current_blocks = [block]
            else:
                current_blocks.append(block)
        flush()
        return sections

    @staticmethod
    def _is_heading(block: DocumentBlock) -> bool:
        if block.block_type in {BlockType.TITLE, BlockType.HEADING}:
            return True
        text = block.text.strip()
        return (
            block.block_type == BlockType.PARAGRAPH
            and len(text) <= 80
            and bool(NUMBERED_HEADING.match(text))
            and not any(mark in text for mark in ("。", "；", ";"))
        )

    @staticmethod
    def _numbered_level(text: str) -> int:
        match = re.match(r"^\s*(\d+(?:\.\d+)*)", text)
        return len(match.group(1).split(".")) if match else 1

    @staticmethod
    def _heading_confidence(block: DocumentBlock) -> float:
        score = 0.90 if block.block_type in {BlockType.TITLE, BlockType.HEADING} else 0.75
        if any(hint in block.text for hint in HEADING_HINTS):
            score += 0.05
        return min(score, 0.98)

    @staticmethod
    def _clean_title(text: str) -> str:
        return NUMBERED_HEADING.sub("", text, count=1).strip() or text.strip()
