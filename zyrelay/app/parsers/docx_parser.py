from pathlib import Path

import docx
from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph

from zyrelay.app.core.exceptions import InvalidFileError, ParseFailedError
from zyrelay.app.models import BlockType

from .base import ParsedDocument, ParsedElement


class DOCXParser:
    name = "python-docx"
    version = docx.__version__

    def parse(self, path: Path) -> ParsedDocument:
        try:
            document = docx.Document(path)
        except Exception as exc:
            raise InvalidFileError(f"无法打开 DOCX：{path.name}") from exc

        try:
            elements: list[ParsedElement] = []
            for item in document.iter_inner_content():
                if isinstance(item, Paragraph):
                    element = self._paragraph_element(item)
                    if element is not None:
                        elements.append(element)
                elif isinstance(item, Table):
                    text = self._table_text(item)
                    if text.strip():
                        elements.append(
                            ParsedElement(
                                text=text,
                                block_type=BlockType.TABLE,
                                metadata={
                                    "rows": len(item.rows),
                                    "columns": max(
                                        (len(row.cells) for row in item.rows), default=0
                                    ),
                                    "table_rows": [
                                        [cell.text.strip() for cell in row.cells]
                                        for row in item.rows
                                    ],
                                },
                            )
                        )

            metadata = document.core_properties
            warnings = [
                "DOCX 不包含可靠的物理分页信息，page_no 保持为空"
            ]
            return ParsedDocument(
                parser=self.name,
                parser_version=self.version,
                page_count=None,
                elements=elements,
                warnings=warnings,
            )
        except Exception as exc:
            raise ParseFailedError(f"DOCX 解析失败：{path.name}") from exc

    @staticmethod
    def _paragraph_element(paragraph: Paragraph) -> ParsedElement | None:
        text = paragraph.text.replace("\x00", "").strip()
        if not text:
            return None

        style_name = paragraph.style.name if paragraph.style else ""
        lowered = style_name.lower()
        heading_level = None
        block_type = BlockType.PARAGRAPH
        if lowered == "title":
            block_type = BlockType.TITLE
        elif lowered.startswith("heading"):
            block_type = BlockType.HEADING
            suffix = lowered.removeprefix("heading").strip()
            heading_level = int(suffix) if suffix.isdigit() else 1
        elif "list" in lowered:
            block_type = BlockType.LIST

        fonts = sorted(
            {
                run.font.name
                for run in paragraph.runs
                if run.font is not None and run.font.name
            }
        )
        monospace_names = {
            "consolas",
            "courier",
            "courier new",
            "menlo",
            "monaco",
            "monospace",
            "source code pro",
        }
        return ParsedElement(
            text=text,
            block_type=block_type,
            heading_level=heading_level,
            metadata={
                "style": style_name,
                "fonts": fonts,
                "monospace": any(font.casefold() in monospace_names for font in fonts),
            },
        )

    @staticmethod
    def _table_text(table: Table) -> str:
        return "\n".join(
            "\t".join(cell.text.strip() for cell in row.cells) for row in table.rows
        )
