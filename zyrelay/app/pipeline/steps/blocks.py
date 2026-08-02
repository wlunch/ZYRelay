import re
import unicodedata

from zyrelay.app.core.exceptions import EmptyDocumentError
from zyrelay.app.models import BlockType, DocumentBlock
from zyrelay.app.pipeline.context import ProcessingContext


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    return normalized.strip()


class BuildBlocksStep:
    name = "build_blocks"

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        if context.document is None or context.parsed_document is None:
            raise RuntimeError("document extraction must run before block building")

        draft: list[tuple[str, BlockType, int | None, int | None, dict]] = []
        parsed = context.parsed_document
        if parsed.elements and not parsed.pages:
            for element in parsed.elements:
                draft.append(
                    (
                        element.text,
                        element.block_type,
                        element.page_no,
                        element.heading_level,
                        element.metadata,
                    )
                )
        elif parsed.pages:
            elements_by_page: dict[int, list] = {}
            for element in parsed.elements:
                if element.page_no is not None:
                    elements_by_page.setdefault(element.page_no, []).append(element)
            for page in parsed.pages:
                ocr_elements = elements_by_page.get(page.page_no, [])
                if ocr_elements:
                    for element in ocr_elements:
                        draft.append(
                            (
                                element.text,
                                element.block_type,
                                element.page_no,
                                element.heading_level,
                                element.metadata,
                            )
                        )
                    continue
                for text in self._split_pdf_page(page.text):
                    draft.append(
                        (
                            text,
                            BlockType.PARAGRAPH,
                            page.page_no,
                            None,
                            {
                                "source_method": "native_pdf_text",
                                "resource_id": "pymupdf-parser",
                                "page_width": page.width,
                                "page_height": page.height,
                            },
                        )
                    )
        else:
            for element in parsed.elements:
                draft.append(
                    (
                        element.text,
                        element.block_type,
                        element.page_no,
                        element.heading_level,
                        element.metadata,
                    )
                )

        if not any(text.strip() for text, *_ in draft) and parsed.requires_ocr:
            context.blocks = []
            return context
        if not any(text.strip() for text, *_ in draft):
            raise EmptyDocumentError("文档没有可处理的文本")

        blocks: list[DocumentBlock] = []
        document_offset = 0
        for sequence, (text, block_type, page_no, heading_level, metadata) in enumerate(
            draft
        ):
            block_id = f"BLK-{sequence + 1:06d}"
            blocks.append(
                DocumentBlock(
                    block_id=block_id,
                    document_id=context.document.document_id,
                    page_no=page_no,
                    block_type=block_type,
                    sequence=sequence,
                    text=text,
                    normalized_text=text,
                    start_offset=document_offset,
                    end_offset=document_offset + len(text),
                    heading_level=heading_level,
                    metadata=metadata,
                )
            )
            document_offset += len(text) + 1
        context.blocks = blocks
        return context

    @staticmethod
    def _split_pdf_page(text: str) -> list[str]:
        clean = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not clean:
            return []
        chunks = [
            chunk.strip()
            for chunk in re.split(r"\n[ \t]*\n+", clean)
            if chunk.strip()
        ]
        return chunks


class NormalizeTextStep:
    name = "normalize_text"

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        context.blocks = [
            block.model_copy(update={"normalized_text": normalize_text(block.text)})
            for block in context.blocks
        ]
        return context
