from fastapi.testclient import TestClient

from zyrelay.app.main import create_app


def test_relay_demo_page_and_assets_are_served() -> None:
    client = TestClient(create_app())

    page = client.get("/demo")
    assert page.status_code == 200
    assert "Document Intelligence Demo" in page.text
    assert "/demo-assets/demo.js" in page.text

    script = client.get("/demo-assets/demo.js")
    assert script.status_code == 200
    assert "loadExecutionData" in script.text
    assert "/api/v1/relay/process" in script.text

    style = client.get("/demo-assets/demo.css")
    assert style.status_code == 200
    assert "timeline" in style.text
