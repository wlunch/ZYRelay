from __future__ import annotations

import re

from zyrelay.app.models import DocumentBlock

from .models import CodeExample

TOKEN = r"[A-Za-z_$][A-Za-z0-9_.$:/(){}+-]*"


class CodeExampleDetector:
    def inline(
        self, text: str, block_id: str, language: str | None
    ) -> tuple[list[CodeExample], list[CodeExample]]:
        positive: list[CodeExample] = []
        negative: list[CodeExample] = []
        for pattern, target, kind in (
            (
                rf"(?:正确示例|推荐写法|正例|例如)[:：]?\s*[`“\"]?({TOKEN})",
                positive,
                "positive",
            ),
            (
                rf"(?:错误示例|反例|禁止使用|错误写法)[:：]?\s*[`“\"]?({TOKEN})",
                negative,
                "negative",
            ),
        ):
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                target.append(
                    CodeExample(
                        example_type=kind,
                        language=language,
                        code=match.group(1).rstrip("。；;，,"),
                        source_block_id=block_id,
                    )
                )
        return positive, negative

    @staticmethod
    def from_block(
        block: DocumentBlock,
        *,
        example_type: str,
        language: str | None,
    ) -> CodeExample | None:
        text = block.text.strip()
        code_like = bool(
            block.metadata.get("monospace")
            or re.search(
                r"(?:\bclass\b|\bdef\b|\bpublic\b|\bprivate\b|\bimport\b|\breturn\b|[{};])",
                text,
            )
        )
        if not code_like:
            return None
        return CodeExample(
            example_type=example_type,
            language=language,
            code=text,
            source_block_id=block.block_id,
        )
