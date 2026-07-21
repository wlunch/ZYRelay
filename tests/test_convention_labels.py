from zyrelay.app.core.config import PROJECT_ROOT
from zyrelay.app.labeling import LabelRepository, MatcherService
from zyrelay.app.models import BlockType, DocumentBlock


def test_convention_matcher_preserves_cross_label_overlap() -> None:
    text = "类名必须使用大驼峰命名"
    block = DocumentBlock(
        block_id="BLK-1",
        document_id="DOC-1",
        page_no=1,
        block_type=BlockType.PARAGRAPH,
        sequence=0,
        text=text,
        normalized_text=text,
        start_offset=0,
        end_offset=len(text),
    )
    repository = LabelRepository(
        PROJECT_ROOT / "config" / "code_convention_labels.yaml",
        PROJECT_ROOT / "config" / "ground_truth",
    )
    labels = repository.load()
    mentions, _ = MatcherService(
        repository,
        preserve_cross_label_overlaps=True,
    ).match([block], labels)

    codes = {mention.label_code for mention in mentions}
    assert "convention_requirement" in codes
    assert "convention_mandatory" in codes
    assert "naming_convention" in codes
