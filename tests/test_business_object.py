from zyrelay.app.core.config import PROJECT_ROOT
from zyrelay.app.models import LabelMention, MatchMethod
from zyrelay.app.semantics import CandidateBuilder


def _mention(code: str, value: str, index: int) -> LabelMention:
    return LabelMention(
        mention_id=f"MEN-{index}",
        document_id="DOC-001",
        block_id=f"BLK-{index}",
        page_no=1,
        label_code=code,
        matched_text=value,
        normalized_value=value,
        start_offset=0,
        end_offset=len(value),
        confidence=0.95,
        match_method=MatchMethod.REGEX,
        evidence=value,
    )


def test_contract_candidate_uses_source_mentions() -> None:
    builder = CandidateBuilder(PROJECT_ROOT / "config" / "business_objects.yaml")
    mentions = [
        _mention("contract_no", "HT-001", 1),
        _mention("party", "北京甲方有限公司", 2),
        _mention("amount", "100000", 3),
    ]

    candidates = builder.build([], mentions)
    contract = next(item for item in candidates if item.name == "合同")

    assert contract.status == "detected"
    assert contract.attributes["contract_no"] == "HT-001"
    assert contract.source_mentions == ["MEN-1", "MEN-2", "MEN-3"]


def test_contract_candidate_not_created_without_required_labels() -> None:
    builder = CandidateBuilder(PROJECT_ROOT / "config" / "business_objects.yaml")
    candidates = builder.build([], [_mention("contract_no", "HT-001", 1)])
    assert all(item.name != "合同" for item in candidates)

