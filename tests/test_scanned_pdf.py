import base64

import fitz

from zyrelay.app.parsers import PDFParser


def test_image_only_pdf_requires_ocr(tmp_path) -> None:
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    path = tmp_path / "scan.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_image(fitz.Rect(72, 72, 200, 200), stream=png)
    pdf.save(path)
    pdf.close()

    result = PDFParser().parse(path)

    assert result.requires_ocr is True
    assert result.pages[0].has_images is True
    assert result.pages[0].text.strip() == ""
