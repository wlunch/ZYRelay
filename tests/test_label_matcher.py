from pathlib import Path

from zyrelay.app.core.config import PROJECT_ROOT
from zyrelay.app.labeling import LabelRepository, MatcherService
from zyrelay.app.models import BlockType, DocumentBlock, MatchMethod


def _repository() -> LabelRepository:
    return LabelRepository(
        PROJECT_ROOT / "config" / "labels.yaml",
        PROJECT_ROOT / "config" / "ground_truth",
    )


def test_regex_alias_and_offsets() -> None:
    text = "合同编号：HT-2026-001，甲方。"
    block = DocumentBlock(
        block_id="BLK-000001",
        document_id="DOC-001",
        page_no=1,
        block_type=BlockType.PARAGRAPH,
        sequence=0,
        text=text,
        normalized_text=text,
        start_offset=0,
        end_offset=len(text),
    )
    repository = _repository()
    labels = repository.load()
    mentions, _ = MatcherService(repository).match([block], labels)

    contract = next(item for item in mentions if item.label_code == "contract_no")
    assert contract.match_method == MatchMethod.REGEX
    assert contract.normalized_value == "HT-2026-001"
    assert text[contract.start_offset : contract.end_offset] == contract.matched_text

    party = next(item for item in mentions if item.label_code == "party")
    assert party.match_method == MatchMethod.ALIAS_EXACT
    assert text[party.start_offset : party.end_offset] == "甲方"


def test_label_configuration_is_yaml_driven(tmp_path: Path) -> None:
    label_path = tmp_path / "labels.yaml"
    label_path.write_text(
        """
labels:
  - code: custom
    name: 自定义
    category: field
    value_type: string
    aliases: [自定义字段]
    patterns: []
    description: test
    enabled: true
""",
        encoding="utf-8",
    )
    repository = LabelRepository(label_path, PROJECT_ROOT / "config" / "ground_truth")
    assert [label.code for label in repository.load()] == ["custom"]
