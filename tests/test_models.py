from hashlib import sha256

from zyrelay.app.models import (
    BlockType,
    DocumentBlock,
    DocumentStatus,
    SourceDocument,
)


def test_core_models_serialize() -> None:
    digest = sha256(b"sample").hexdigest()
    document = SourceDocument(
        document_id=f"DOC-{digest[:16]}",
        file_name="sample.pdf",
        file_type="pdf",
        file_size=6,
        sha256=digest,
        status=DocumentStatus.COMPLETED,
    )
    block = DocumentBlock(
        block_id="BLK-000001",
        document_id=document.document_id,
        page_no=1,
        block_type=BlockType.PARAGRAPH,
        sequence=0,
        text="合同编号：HT-001",
        normalized_text="合同编号:HT-001",
        start_offset=0,
        end_offset=13,
    )

    assert document.model_dump(mode="json")["status"] == "completed"
    assert block.model_dump(mode="json")["block_type"] == "paragraph"
