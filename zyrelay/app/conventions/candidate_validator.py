from __future__ import annotations

import re

from zyrelay.app.models import DocumentBlock

from .models import CodeConventionCandidate


class ConventionCandidateValidator:
    def validate(
        self,
        candidates: list[CodeConventionCandidate],
        blocks: list[DocumentBlock],
    ) -> tuple[list[CodeConventionCandidate], list[str]]:
        block_map = {block.block_id: block for block in blocks}
        valid: list[CodeConventionCandidate] = []
        warnings: list[str] = []
        for candidate in candidates:
            reason = self._invalid_reason(candidate, block_map)
            if reason:
                warnings.append(f"{candidate.convention_id} 被拒绝：{reason}")
            else:
                valid.append(candidate)
        return valid, warnings

    @staticmethod
    def _invalid_reason(
        candidate: CodeConventionCandidate,
        block_map: dict[str, DocumentBlock],
    ) -> str | None:
        for evidence in candidate.source_evidence:
            block = block_map.get(evidence.block_id)
            if block is None:
                return f"证据 block 不存在：{evidence.block_id}"
            if evidence.end_offset > len(block.text):
                return "证据 offset 超出 block"
            if (
                block.text[evidence.start_offset : evidence.end_offset]
                != evidence.evidence_text
            ):
                return "证据文本与原始 block 不一致"

        expression = candidate.rule_expression
        if expression and isinstance(expression.expected, (int, float)):
            evidence_text = " ".join(
                evidence.evidence_text for evidence in candidate.source_evidence
            )
            expected = str(expression.expected)
            expected = expected.removesuffix(".0")
            if not re.search(rf"(?<!\d){re.escape(expected)}(?!\d)", evidence_text):
                return "规则数值未出现在原始证据中"
        return None
