from pathlib import Path

from fastapi.testclient import TestClient

from zyrelay.app.core.config import PROJECT_ROOT, Settings
from zyrelay.app.main import create_app


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        data_root=tmp_path / "data",
        label_config=PROJECT_ROOT / "config" / "labels.yaml",
        business_object_config=PROJECT_ROOT / "config" / "business_objects.yaml",
        ground_truth_dir=PROJECT_ROOT / "config" / "ground_truth",
        llm_enabled=False,
    )
    return TestClient(create_app(settings))


def test_upload_query_and_uom(sample_pdf, tmp_path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", sample_pdf.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    document_id = body["document_id"]
    assert body["status"] == "completed"

    metadata = client.get(f"/api/v1/documents/{document_id}")
    assert metadata.status_code == 200
    assert metadata.json()["page_count"] == 2

    labels = client.get(f"/api/v1/documents/{document_id}/labels").json()["mentions"]
    assert {"contract_no", "party", "amount", "date"} <= {
        item["label_code"] for item in labels
    }

    search = client.get(
        "/api/v1/search",
        params={"label_code": "contract_no", "document_id": document_id},
    )
    assert search.status_code == 200
    assert search.json()["results"][0]["normalized_value"] == "HT-2026-001"

    package = client.get(f"/api/v1/documents/{document_id}/uom").json()
    assert package["schema_version"] == "1.0"
    assert package["bom"]["business_objects"][0]["status"] == "detected"
    step_names = [step["name"] for step in package["processing"]["steps"]]
    assert step_names[:8] == [
        "validate_file",
        "extract_document",
        "build_blocks",
        "normalize_text",
        "match_labels",
        "build_semantic_index",
        "build_semantic_candidates",
        "llm_enrichment",
    ]
    assert step_names[-2:] == ["build_uom_package", "save_result"]
    assert package["semantic_objects"]["validation"]["valid"] is True
    assert package["semantic_objects"]["validation"]["evidence_count"] > 0

    objects = client.get(
        f"/api/v1/documents/{document_id}/semantic-objects",
        params={"object_type": "observation"},
    )
    assert objects.status_code == 200
    assert objects.json()["objects"]
    assert all(item["evidence_ids"] for item in objects.json()["objects"])

    evidence = client.get(f"/api/v1/documents/{document_id}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["objects"][0]["attributes"]["matched_text"]

    export = client.get(
        f"/api/v1/documents/{document_id}/semantic-objects/export",
        params={"format": "graph-json"},
    )
    assert export.status_code == 200
    assert export.json()["nodes"]


def test_unsupported_file_type(tmp_path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["error_code"] == "unsupported_file_type"


def test_empty_document(tmp_path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("empty.pdf", b"%PDF-", "application/pdf")},
    )
    assert response.status_code in {400, 422}
    assert response.json()["error_code"] in {"invalid_file", "empty_document"}


def test_health_and_llm_disabled(tmp_path) -> None:
    client = _client(tmp_path)
    assert client.get("/health").json()["status"] == "ok"
