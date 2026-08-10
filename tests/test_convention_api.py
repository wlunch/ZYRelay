from pathlib import Path

from fastapi.testclient import TestClient

from zyrelay.app.core.config import PROJECT_ROOT, Settings
from zyrelay.app.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                data_root=tmp_path / "data",
                label_config=PROJECT_ROOT / "config" / "labels.yaml",
                business_object_config=PROJECT_ROOT
                / "config"
                / "business_objects.yaml",
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
    )


def test_convention_api_filters(sample_convention_docx: Path, tmp_path: Path) -> None:
    client = _client(tmp_path)
    upload = client.post(
        "/api/v1/documents",
        files={
            "file": (
                sample_convention_docx.name,
                sample_convention_docx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert upload.status_code == 201
    document_id = upload.json()["document_id"]

    response = client.get(
        f"/api/v1/documents/{document_id}/code-conventions",
        params={
            "category": "naming",
            "language": "Java",
            "requirement_level": "mandatory",
        },
    )
    assert response.status_code == 200
    assert response.json()["count"] >= 1

    index = client.get(f"/api/v1/documents/{document_id}/convention-index")
    assert index.status_code == 200
    assert "naming" in index.json()["by_category"]

    search = client.get(
        "/api/v1/conventions/search",
        params={
            "document_id": document_id,
            "keyword": "覆盖率",
            "executable": True,
        },
    )
    assert search.status_code == 200
    assert search.json()["count"] == 1
