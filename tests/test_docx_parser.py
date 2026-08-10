from zyrelay.app.models import BlockType
from zyrelay.app.parsers import DOCXParser


def test_docx_paragraph_heading_and_table_order(sample_docx) -> None:
    result = DOCXParser().parse(sample_docx)

    assert [element.block_type for element in result.elements] == [
        BlockType.TITLE,
        BlockType.HEADING,
        BlockType.PARAGRAPH,
        BlockType.TABLE,
        BlockType.PARAGRAPH,
    ]
    assert "北京甲方有限公司" in result.elements[3].text
    assert result.elements[1].heading_level == 1
    assert result.page_count is None
