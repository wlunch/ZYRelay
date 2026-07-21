from zyrelay.app.conventions import (
    CodeConventionCandidate,
    ConventionStatus,
    EvidenceReference,
    RequirementLevel,
    RuleType,
)


def test_code_convention_candidate_serializes_and_requires_evidence() -> None:
    candidate = CodeConventionCandidate(
        convention_id="CONV-1",
        title="类名规范",
        description="类名必须使用大驼峰",
        category=RuleType.NAMING,
        rule_type=RuleType.NAMING,
        requirement_level=RequirementLevel.MANDATORY,
        source_evidence=[
            EvidenceReference(
                document_id="DOC-1",
                block_id="BLK-1",
                page_no=1,
                start_offset=0,
                end_offset=9,
                evidence_text="类名必须使用大驼峰",
            )
        ],
        confidence=0.95,
    )
    assert candidate.model_dump(mode="json")["status"] == "detected"

    reviewed = CodeConventionCandidate.model_validate(
        {**candidate.model_dump(), "status": ConventionStatus.CONFIRMED}
    )
    assert reviewed.status == "confirmed"


def test_automatic_candidate_default_is_detected() -> None:
    candidate = CodeConventionCandidate(
        convention_id="CONV-2",
        title="日志规范",
        description="禁止使用 System.out.println",
        category=RuleType.LOGGING,
        rule_type=RuleType.LOGGING,
        requirement_level=RequirementLevel.PROHIBITED,
        source_evidence=[
            EvidenceReference(
                document_id="DOC-1",
                block_id="BLK-1",
                start_offset=0,
                end_offset=25,
                evidence_text="禁止使用 System.out.println",
            )
        ],
        confidence=0.95,
    )
    assert candidate.status == ConventionStatus.DETECTED
