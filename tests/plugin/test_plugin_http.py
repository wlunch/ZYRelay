import base64
from pathlib import Path

from fastapi.testclient import TestClient

from zyrelay.app.core.config import PROJECT_ROOT, Settings
from zyrelay.app.main import create_app

PLUGIN_URL = "/api/v1/plugins/zyrelay.doc-intelligence"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                data_root=tmp_path / "data",
                label_config=PROJECT_ROOT / "config" / "labels.yaml",
                business_object_config=(
                    PROJECT_ROOT / "config" / "business_objects.yaml"
                ),
                plugin_config=PROJECT_ROOT / "config" / "plugin.yaml",
                ground_truth_dir=PROJECT_ROOT / "config" / "ground_truth",
                llm_enabled=False,
            )
        )
    )


def test_manifest_capabilities_and_schema_http(tmp_path) -> None:
    client = _client(tmp_path)
    assert client.get("/api/v1/plugins").status_code == 200
    assert client.get(PLUGIN_URL).json()["version"] == "1.0.0"
    assert client.get(f"{PLUGIN_URL}/capabilities").json()["features"]["ocr"] is False
    assert "properties" in client.get(f"{PLUGIN_URL}/schemas/input").json()
    assert "properties" in client.get(f"{PLUGIN_URL}/schemas/output").json()
    assert "properties" in client.get(f"{PLUGIN_URL}/schemas/configuration").json()
    assert client.get("/api/v1/plugins/missing.plugin").status_code == 404


def test_http_json_execute_and_result_artifacts(sample_pdf, tmp_path) -> None:
    client = _client(tmp_path)
    payload = {
        "operation": "process_document",
        "input": {
            "source_type": "base64",
            "file_name": "contract.pdf",
            "content_type": "application/pdf",
            "content_base64": base64.b64encode(sample_pdf.read_bytes()).decode(),
        },
        "options": {"mode": "contract", "output_detail": "standard"},
    }
    response = client.post(f"{PLUGIN_URL}/execute", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed"
    execution_id = result["execution_id"]

    saved = client.get(f"{PLUGIN_URL}/executions/{execution_id}")
    assert saved.status_code == 200
    artifacts = client.get(f"{PLUGIN_URL}/executions/{execution_id}/artifacts").json()
    assert len(artifacts) == 1
    artifact = client.get(
        f"{PLUGIN_URL}/executions/{execution_id}/artifacts/"
        f"{artifacts[0]['artifact_id']}"
    )
    assert artifact.status_code == 200
    assert artifact.json()["schema_version"] == "1.0"
    assert client.get(
        f"{PLUGIN_URL}/executions/../../etc/passwd/artifacts"
    ).status_code in {400, 404}


def test_http_multipart_and_file_path_rejection(sample_docx, tmp_path) -> None:
    client = _client(tmp_path)
    response = client.post(
        f"{PLUGIN_URL}/execute-file",
        files={"file": (sample_docx.name, sample_docx.read_bytes(), DOCX_MIME)},
        data={"mode": "auto", "output_detail": "summary"},
    )
    assert response.status_code == 200
    assert response.json()["result"]["blocks"] == []

    rejected = client.post(
        f"{PLUGIN_URL}/execute",
        json={
            "input": {
                "source_type": "file",
                "file_name": sample_docx.name,
                "content_type": DOCX_MIME,
                "file_path": str(sample_docx),
            }
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["errors"][0]["code"] == "invalid_request"
