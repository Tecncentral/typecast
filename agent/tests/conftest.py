import pytest


@pytest.fixture(autouse=True)
def _default_image_editor(monkeypatch):
    """Tests use fake image clients; a machine's .env choosing a live provider or model must not leak in."""
    for name in ("TYPECAST_IMAGE_PROVIDER", "TYPECAST_GEMINI_IMAGE_MODEL", "TYPECAST_OBLIQUE_IMAGE_MODEL",
                 "TYPECAST_OBLIQUE_IMAGE_QUALITY"):
        monkeypatch.delenv(name, raising=False)
