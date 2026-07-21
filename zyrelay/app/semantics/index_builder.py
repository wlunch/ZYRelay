import re
from collections import defaultdict

from zyrelay.app.models import (
    DocumentBlock,
    LabelMention,
    SemanticIndexBucket,
    SemanticIndexOccurrence,
)


class SemanticIndexBuilder:
    def build(
        self, mentions: list[LabelMention]
    ) -> dict[str, SemanticIndexBucket]:
        grouped: dict[str, dict[str, list[SemanticIndexOccurrence]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for mention in mentions:
            grouped[mention.label_code][mention.document_id].append(
                SemanticIndexOccurrence(
                    block_id=mention.block_id,
                    page_no=mention.page_no,
                    start_offset=mention.start_offset,
                    end_offset=mention.end_offset,
                    matched_text=mention.matched_text,
                    normalized_value=mention.normalized_value,
                    confidence=mention.confidence,
                )
            )
        return {
            label_code: SemanticIndexBucket(
                label_code=label_code, documents=dict(documents)
            )
            for label_code, documents in sorted(grouped.items())
        }

    def build_raw_token_index(
        self, blocks: list[DocumentBlock], stopwords: set[str] | None = None
    ) -> dict[str, list[dict]]:
        stopwords = stopwords or set()
        index: dict[str, list[dict]] = defaultdict(list)
        for block in blocks:
            for match in re.finditer(
                r"[A-Za-z][A-Za-z0-9_-]{1,39}|[\u4e00-\u9fff]{2,20}",
                block.text,
            ):
                token = match.group(0)
                if token in stopwords:
                    continue
                index[token].append(
                    {
                        "block_id": block.block_id,
                        "page_no": block.page_no,
                        "start_offset": match.start(),
                        "end_offset": match.end(),
                        "matched_text": token,
                    }
                )
        return dict(index)

