from fastapi.testclient import TestClient

from app.main import create_app


def test_product_overview_is_presentation_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "ParishConnect"
    assert body["status"] == "skeleton-ready"
    assert "attendance" in body["modules"]

