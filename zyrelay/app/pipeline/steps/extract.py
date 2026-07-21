from zyrelay.app.core.exceptions import UnsupportedFileTypeError
from zyrelay.app.parsers import DOCXParser, PDFParser
from zyrelay.app.pipeline.context import ProcessingContext


class ExtractDocumentStep:
    name = "extract_document"

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        suffix = context.input_path.suffix.lower()
        if suffix == ".pdf":
            parser = PDFParser()
        elif suffix == ".docx":
            parser = DOCXParser()
        else:
            raise UnsupportedFileTypeError(f"不支持的文件类型：{suffix or 'unknown'}")

        parsed = parser.parse(context.input_path)
        context.parsed_document = parsed
        context.warnings.extend(parsed.warnings)
        if context.document is not None:
            context.document.parser = parsed.parser
            context.document.parser_version = parsed.parser_version
            context.document.page_count = parsed.page_count
            context.document.requires_ocr = parsed.requires_ocr
        return context

