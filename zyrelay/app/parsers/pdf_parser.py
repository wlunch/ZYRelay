from pathlib import Path

import fitz

from zyrelay.app.core.exceptions import InvalidFileError, ParseFailedError

from .base import ParsedDocument, ParsedPage


class PDFParser:
    name = "PyMuPDF"
    version = fitz.VersionBind

    def parse(self, path: Path) -> ParsedDocument:
        try:
            pdf = fitz.open(path)
        except Exception as exc:
            raise InvalidFileError(f"无法打开 PDF：{path.name}") from exc

        try:
            if pdf.page_count == 0:
                return ParsedDocument(
                    parser=self.name,
                    parser_version=self.version,
                    page_count=0,
                    requires_ocr=False,
                )

            pages: list[ParsedPage] = []
            empty_pages: list[int] = []
            image_only_pages: list[int] = []
            for index, page in enumerate(pdf):
                text = page.get_text("text", sort=True).replace("\x00", "")
                page_no = index + 1
                has_images = bool(page.get_images(full=True))
                if not text.strip():
                    empty_pages.append(page_no)
                    if has_images:
                        image_only_pages.append(page_no)
                pages.append(
                    ParsedPage(
                        page_no=page_no,
                        text=text,
                        width=float(page.rect.width),
                        height=float(page.rect.height),
                        has_images=has_images,
                        text_source="native" if text.strip() else "none",
                    )
                )

            requires_ocr = bool(image_only_pages)
            warnings = []
            if image_only_pages:
                warnings.append(f"PDF 图片页无可提取文本，需要 OCR：{image_only_pages}")
            blank_pages = sorted(set(empty_pages) - set(image_only_pages))
            if blank_pages:
                warnings.append(f"PDF 页面为空：{blank_pages}")
            return ParsedDocument(
                parser=self.name,
                parser_version=self.version,
                page_count=pdf.page_count,
                pages=pages,
                requires_ocr=requires_ocr,
                warnings=warnings,
            )
        except Exception as exc:
            if isinstance(exc, InvalidFileError):
                raise
            raise ParseFailedError(f"PDF 解析失败：{path.name}") from exc
        finally:
            pdf.close()
