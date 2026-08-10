from zyrelay.app.parsers import PDFParser


def test_pdf_text_extraction_and_pages(sample_pdf) -> None:
    result = PDFParser().parse(sample_pdf)

    assert result.page_count == 2
    assert "HT-2026-001" in result.pages[0].text
    assert "100,000.00" in result.pages[1].text
    assert result.requires_ocr is False
