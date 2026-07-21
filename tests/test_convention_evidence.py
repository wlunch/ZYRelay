from zyrelay.app.conventions import (
    CodeConventionCandidate,
    EvidenceReference,
    RequirementLevel,
    RuleExpression,
    RuleOperator,
    RuleType,
)
from zyrelay.app.conventions.candidate_validator import ConventionCandidateValidator
from zyrelay.app.conventions.code_example_detector import CodeExampleDetector
from zyrelay.app.models import BlockType, DocumentBlock


def _block(text: str) -> DocumentBlock:
    return DocumentBlock(
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


def _candidate(evidence: str, expression: RuleExpression | None = None):
    return CodeConventionCandidate(
        convention_id="CONV-1",
        title="测试规范",
        description=evidence,
        category=RuleType.TESTING,
        rule_type=RuleType.TESTING,
        requirement_level=RequirementLevel.MANDATORY,
        source_evidence=[
            EvidenceReference(
                document_id="DOC-1",
                block_id="BLK-1",
                page_no=1,
                start_offset=0,
                end_offset=len(evidence),
                evidence_text=evidence,
            )
        ],
        confidence=0.9,
        rule_expression=expression,
    )


def test_validator_rejects_evidence_not_in_block() -> None:
    valid, warnings = ConventionCandidateValidator().validate(
        [_candidate("不存在的规范")],
        [_block("完全不同文本")],
    )
    assert valid == []
    assert "证据文本" in warnings[0]


def test_validator_rejects_numeric_value_not_in_evidence() -> None:
    expression = RuleExpression(
        target="unit_test_coverage",
        operator=RuleOperator.GREATER_THAN_OR_EQUAL,
        expected=80,
        executable=True,
    )
    valid, warnings = ConventionCandidateValidator().validate(
        [_candidate("测试覆盖率必须达标", expression)],
        [_block("测试覆盖率必须达标")],
    )
    assert valid == []
    assert "规则数值" in warnings[0]


def test_inline_positive_and_negative_examples() -> None:
    positive, negative = CodeExampleDetector().inline(
        "例如 OrderService，禁止使用 order_service",
        "BLK-1",
        "Java",
    )
    assert positive[0].code == "OrderService"
    assert negative[0].code == "order_service"


def test_monospace_code_block_example() -> None:
    block = _block("public class OrderService {}").model_copy(
        update={"metadata": {"monospace": True}}
    )
    example = CodeExampleDetector().from_block(
        block,
        example_type="positive",
        language="Java",
    )
    assert example is not None
    assert example.source_block_id == "BLK-1"
