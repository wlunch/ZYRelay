from zyrelay.app.models import LabelMention, MatchMethod
from zyrelay.app.semantics import SemanticIndexBuilder


def _mention(code: str, offset: int) -> LabelMention:
    return LabelMention(
        mention_id=f"MEN-{code}-{offset}",
        document_id="DOC-001",
        block_id="BLK-001",
        page_no=1,
        label_code=code,
        matched_text="合同编号：HT-001",
        normalized_value="HT-001",
        start_offset=offset,
        end_offset=offset + 12,
        confidence=0.95,
        match_method=MatchMethod.REGEX,
        evidence="合同编号：HT-001",
    )


def test_semantic_index_aggregates_by_label_and_document() -> None:
    index = SemanticIndexBuilder().build(
        [_mention("contract_no", 0), _mention("contract_no", 20)]
    )

    assert list(index) == ["contract_no"]
    assert len(index["contract_no"].documents["DOC-001"]) == 2
    assert index["contract_no"].documents["DOC-001"][0].normalized_value == "HT-001"
