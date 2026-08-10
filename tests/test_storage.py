import json
from hashlib import sha256

from zyrelay.app.models import (
    DocumentStatus,
    ProcessingRecord,
    SourceDocument,
    UOMPackage,
)
from zyrelay.app.models.uom import BOMSection, MOMSection, SOMSection
from zyrelay.app.storage import LocalStorage


def test_atomic_package_storage_and_serialization(tmp_path) -> None:
    digest = sha256(b"x").hexdigest()
    source = SourceDocument(
        document_id=f"DOC-{digest[:16].upper()}",
        file_name="x.pdf",
        file_type="pdf",
        file_size=1,
        sha256=digest,
        status=DocumentStatus.COMPLETED,
    )
    package = UOMPackage(
        package_id="PKG-1",
        source=source,
        mom=MOMSection(document=source, blocks=[]),
        som=SOMSection(labels=[], mentions=[], semantic_index={}, candidates=[]),
        bom=BOMSection(business_objects=[]),
        processing=ProcessingRecord(
            pipeline_version="0.1.0",
            ground_truth_version="1",
            label_config_hash=digest,
            business_object_config_hash=digest,
        ),
    )
    storage = LocalStorage(tmp_path)
    path = storage.save_package(package)

    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "1.0"
    assert storage.load_package(source.document_id) == package
