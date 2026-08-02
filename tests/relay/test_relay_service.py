from pathlib import Path

from fastapi.testclient import TestClient

from zyrelay.app.main import create_app
from zyrelay.relay.models import RelayInput, RelayRequest, RelayStatus


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_relay_docx_builds_provenance(relay_service, sample_convention_docx: Path) -> None:
    result = relay_service.process(
        RelayRequest(
            input=RelayInput(
                file_name=sample_convention_docx.name,
                content_type=DOCX_MIME,
                file_path=str(sample_convention_docx),
            ),
            output_detail="full",
        )
    )
    assert result.status == RelayStatus.COMPLETED
    assert result.result["code_conventions"]
    convention = result.result["code_conventions"][0]
    assert convention["provenance_id"]
    provenance = relay_service.get_provenance(convention["provenance_id"])
    assert provenance.source_block_ids
    assert provenance.ground_snapshot_id == result.ground["snapshot_id"]
    assert provenance.resource_plan_id == result.resources["plan_id"]
    assert all(
        block["metadata"]["source_method"] == "docx_xml"
        for block in result.result["blocks"]
    )
    execution = relay_service.get_execution(result.execution_id)
    assert execution.status == RelayStatus.COMPLETED


def test_relay_api_and_traceback_endpoints(sample_convention_docx: Path, tmp_path) -> None:
    from zyrelay.app.core.config import PROJECT_ROOT, Settings

    client = TestClient(
        create_app(
            Settings(
                data_root=tmp_path / "data",
                label_config=PROJECT_ROOT / "config" / "labels.yaml",
                business_object_config=PROJECT_ROOT / "config" / "business_objects.yaml",
                code_convention_label_config=PROJECT_ROOT / "config" / "code_convention_labels.yaml",
                code_rule_pattern_config=PROJECT_ROOT / "config" / "code_rule_patterns.yaml",
                plugin_config=PROJECT_ROOT / "config" / "plugin.yaml",
                ground_config_dir=PROJECT_ROOT / "config" / "ground",
                enterprise_config_dir=PROJECT_ROOT / "config" / "enterprises",
                model_config=PROJECT_ROOT / "config" / "models.yaml",
                ground_truth_dir=PROJECT_ROOT / "config" / "ground_truth",
            )
        )
    )
    response = client.post(
        "/api/v1/relay/process",
        files={"file": (sample_convention_docx.name, sample_convention_docx.read_bytes(), DOCX_MIME)},
        data={"mode": "code_convention", "output_detail": "standard"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    execution_id = body["execution_id"]
    assert client.get(f"/api/v1/relay/executions/{execution_id}/ground").status_code == 200
    assert client.get(f"/api/v1/relay/executions/{execution_id}/resources").status_code == 200
    provenance_id = body["result"]["code_conventions"][0]["provenance_id"]
    assert client.get(f"/api/v1/relay/provenance/{provenance_id}").status_code == 200
