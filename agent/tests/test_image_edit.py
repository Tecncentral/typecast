import base64
import io

import pytest
from PIL import Image

from agent import image_edit


def _png(color=(10, 20, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(buf, "PNG")
    return buf.getvalue()


class Response:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def test_openai_is_the_default_and_uses_the_injected_client():
    class Client:
        def _post(self, path, files, data, timeout):
            assert path == "/images/edits" and data["model"] == "gpt-image-1-mini" and data["quality"] == "low"
            return {"data": [{"b64_json": base64.b64encode(_png()).decode()}]}

    content, model, quality = image_edit.edit_image(_png(), "night", "1536x1024", client=Client())
    assert content[:4] == b"\x89PNG" and (model, quality) == ("gpt-image-1-mini", "low")


def test_gemini_sends_the_image_and_aspect_and_reads_inline_data(monkeypatch):
    monkeypatch.setenv("TYPECAST_IMAGE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-gemini")
    sent = {}

    def post(url, headers, json, timeout, allow_redirects):
        sent.update(url=url, headers=headers, body=json, redirects=allow_redirects)
        return Response(200, {"candidates": [{"content": {"parts": [{"text": "here"},
                                                                    {"inlineData": {"mimeType": "image/png",
                                                                                    "data": base64.b64encode(_png((1, 2, 3))).decode()}}]}}]})

    monkeypatch.setattr(image_edit.requests, "post", post)
    content, model, quality = image_edit.edit_image(_png(), "add solar", "1024x1536")
    assert model == "gemini-3.1-flash-lite-image" and quality == "gemini"
    assert sent["url"].endswith("/models/gemini-3.1-flash-lite-image:generateContent")
    assert sent["headers"] == {"x-goog-api-key": "secret-gemini"} and sent["redirects"] is False
    assert "secret-gemini" not in sent["url"]
    parts = sent["body"]["contents"][0]["parts"]
    assert parts[1]["text"] == "add solar" and parts[0]["inline_data"]["mime_type"] == "image/png"
    assert sent["body"]["generationConfig"]["imageConfig"]["aspectRatio"] == "2:3"
    assert Image.open(io.BytesIO(content)).getpixel((0, 0)) == (1, 2, 3)


def test_gemini_errors_are_sanitized(monkeypatch):
    monkeypatch.setenv("TYPECAST_IMAGE_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(image_edit.ImageEditError, match="GEMINI_API_KEY is not set"):
        image_edit.edit_image(_png(), "x", "1536x1024")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-gemini")
    monkeypatch.setattr(image_edit.requests, "post", lambda *a, **k: Response(400, {"error": "secret-gemini bad"}))
    with pytest.raises(image_edit.ImageEditError) as error:
        image_edit.edit_image(_png(), "x", "1536x1024")
    assert str(error.value) == "Gemini HTTP 400"
    monkeypatch.setattr(image_edit.requests, "post", lambda *a, **k: Response(200, {"candidates": []}))
    with pytest.raises(image_edit.ImageEditError, match="no image"):
        image_edit.edit_image(_png(), "x", "1536x1024")
