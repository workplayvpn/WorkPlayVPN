from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_activation_page_uses_external_assets() -> None:
    response = client.get("/activate/example-token")

    assert response.status_code == 200
    assert (
        '/activate/assets/device-activation.css?v=1'
        in response.text
    )
    assert (
        '/activate/assets/device-activation.js?v=1'
        in response.text
    )
    assert "data-activation-token=\"example-token\"" in response.text
    assert "<script>" not in response.text


def test_activation_page_styles_are_available() -> None:
    response = client.get(
        "/activate/assets/device-activation.css"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_activation_page_script_is_available() -> None:
    response = client.get(
        "/activate/assets/device-activation.js"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/javascript"
    )
    assert "DOMContentLoaded" in response.text
