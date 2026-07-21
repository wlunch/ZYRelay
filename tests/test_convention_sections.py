from zyrelay.app.conventions.section_detector import ConventionSectionDetector
from zyrelay.app.models import BlockType, DocumentBlock


def _block(
    index: int,
    text: str,
    block_type: BlockType = BlockType.PARAGRAPH,
    heading_level: int | None = None,
) -> DocumentBlock:
    return DocumentBlock(
        block_id=f"BLK-{index:06d}",
        document_id="DOC-1",
        page_no=1,
        block_type=block_type,
        sequence=index - 1,
        text=text,
        normalized_text=text,
        start_offset=0,
        end_offset=len(text),
        heading_level=heading_level,
    )


def test_heading_and_numbered_section_detection() -> None:
    sections = ConventionSectionDetector().detect(
        [
            _block(1, "Java 开发规范", BlockType.TITLE),
            _block(2, "说明文字"),
            _block(3, "1 命名规范", BlockType.HEADING, 1),
            _block(4, "类名必须使用大驼峰"),
            _block(5, "2.1 日志要求"),
            _block(6, "禁止使用 System.out.println", BlockType.LIST),
        ]
    )

    assert [section.title for section in sections] == [
        "Java 开发规范",
        "命名规范",
        "日志要求",
    ]
    assert sections[1].block_ids[-1] == "BLK-000004"
    assert sections[2].level == 2


def test_empty_blocks_produce_no_sections() -> None:
    assert ConventionSectionDetector().detect([]) == []
