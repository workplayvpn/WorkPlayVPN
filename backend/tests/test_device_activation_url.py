import pytest

from app.api.device_activations import build_activation_url
from app.core.config import settings


def test_build_activation_url_uses_configured_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "activation_base_url",
        "https://connect.test.local/activate/",
    )

    activation_url = build_activation_url("test-token")

    assert activation_url == (
        "https://connect.test.local/activate/test-token"
    )