from zyrelay.app.models import SemanticObjectType
from zyrelay.app.semantics.semantic_objects import validate_semantic_objects


def test_semantic_object_ids_are_stable(sample_pdf, tmp_path) -> None:
    from zyrelay.app.core.config import PROJECT_ROOT, Settings
    from zyrelay.app.services import DocumentService

    settings = Settings(
        data_root=tmp_path / "data",
        label_config=PROJECT_ROOT / "config" / "labels.yaml",
        business_object_config=PROJECT_ROOT / "config" / "business_objects.yaml",
        ground_truth_dir=PROJECT_ROOT / "config" / "ground_truth",
        llm_enabled=False,
    )
    service = DocumentService(settings)
    document_id, _ = service.process("contract.pdf", sample_pdf.read_bytes())
    first = service.get_semantic_objects(document_id)
    second = service.get_semantic_objects(document_id)
    assert [item.object_id for item in first] == [item.object_id for item in second]
    assert any(item.object_type == SemanticObjectType.BUSINESS_OBJECT for item in first)
    assert validate_semantic_objects(first).valid
