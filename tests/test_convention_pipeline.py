from pathlib import Path

from zyrelay.app.core.config import PROJECT_ROOT, Settings
from zyrelay.app.services import DocumentService


def _service(tmp_path: Path) -> DocumentService:
    return DocumentService(
        Settings(
            data_root=tmp_path / "data",
            label_config=PROJECT_ROOT / "config" / "labels.yaml",
            business_object_config=PROJECT_ROOT / "config" / "business_objects.yaml",
            code_convention_label_config=(
                PROJECT_ROOT / "config" / "code_convention_labels.yaml"
            ),
            code_rule_pattern_config=(
                PROJECT_ROOT / "config" / "code_rule_patterns.yaml"
            ),
            ground_truth_dir=PROJECT_ROOT / "config" / "ground_truth",
            llm_enabled=False,
        )
    )


def test_end_to_end_convention_extraction(
    sample_convention_docx: Path, tmp_path: Path
) -> None:
    service = _service(tmp_path)
    document_id, _ = service.process(
        sample_convention_docx.name, sample_convention_docx.read_bytes()
    )
    package = service.get_package(document_id)
    conventions = package.som.code_conventions

    assert len(conventions) >= 10
    assert {
        "naming",
        "formatting",
        "comment",
        "logging",
        "security",
        "testing",
        "review",
    } <= {item.category.value for item in conventions}
    assert {"mandatory", "prohibited", "recommended"} <= {
        item.requirement_level.value for item in conventions
    }
    assert all(item.source_evidence for item in conventions)
    assert all(
        package.mom.blocks[
            next(
                index
                for index, block in enumerate(package.mom.blocks)
                if block.block_id == item.source_evidence[0].block_id
            )
        ].text[
            item.source_evidence[0].start_offset : item.source_evidence[0].end_offset
        ]
        == item.source_evidence[0].evidence_text
        for item in conventions
    )

    naming = next(
        item
        for item in conventions
        if item.rule_expression
        and item.rule_expression.target == "class_name"
        and item.requirement_level == "mandatory"
    )
    assert naming.language == ["Java"]
    assert "Spring Boot" in naming.frameworks
    assert naming.rule_expression.parameters["style"] == "PascalCase"
    assert naming.positive_examples[0].code == "OrderService"

    negative = next(item for item in conventions if item.negative_examples)
    assert negative.negative_examples[0].code == "order_service"

    assert "naming" in package.som.convention_index.by_category
    assert document_id in package.som.convention_index.by_document
    assert any(
        item.attributes.get("type") == "TeamCodeConvention"
        for item in package.bom.business_objects
    )


def test_contract_regression_has_no_code_conventions(
    sample_docx: Path, tmp_path: Path
) -> None:
    service = _service(tmp_path)
    document_id, _ = service.process(sample_docx.name, sample_docx.read_bytes())
    package = service.get_package(document_id)
    assert package.som.code_conventions == []


def test_pdf_convention_evidence_has_page_number(
    sample_convention_pdf: Path, tmp_path: Path
) -> None:
    service = _service(tmp_path)
    document_id, _ = service.process(
        sample_convention_pdf.name,
        sample_convention_pdf.read_bytes(),
    )
    conventions = service.get_package(document_id).som.code_conventions
    assert {item.category.value for item in conventions} >= {"naming", "testing"}
    assert {item.source_evidence[0].page_no for item in conventions} == {1, 2}
