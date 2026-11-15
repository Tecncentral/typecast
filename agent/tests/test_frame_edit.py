import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from agent import frame_edit as fe


def _data_url(size=(320, 134), color=(120, 100, 80)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


class Images:
    def __init__(self):
        self.sent = []

    def _post(self, path, files, data, timeout):
        with Image.open(io.BytesIO(files["image"][1])) as image:
            self.sent.append((image.size, image.getpixel((image.width // 2, image.height // 2)), data["size"],
                              data["model"], data["quality"], image.getpixel((5, 5))))
        buf = io.BytesIO()
        Image.new("RGB", (1536, 1024), (10, 20, 30 + 40 * len(self.sent))).save(buf, "PNG")
        return {"data": [{"b64_json": base64.b64encode(buf.getvalue()).decode()}]}


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setattr(fe, "CACHE", tmp_path / "frame-edits")
    monkeypatch.setattr(fe, "ROOT", tmp_path)
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    monkeypatch.delenv("TYPECAST_OBLIQUE_IMAGE_MODEL", raising=False)
    return tmp_path


def test_scan_views_are_not_uploaded_without_the_permission_switch(cache, monkeypatch):
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "0")
    client = Images()
    with pytest.raises(fe.EditUnavailable):
        fe.edit("night", shot_id="s1", image=_data_url(), client=client)
    assert client.sent == []


def test_each_message_builds_on_the_latest_version_and_keeps_the_frame_size(cache):
    client = Images()
    one = fe.edit("1970s precinct", shot_id="275969-abc_1.0", address="3161 E Washington Blvd", image=_data_url(), client=client)
    two = fe.edit("night", edit_id=one["edit_id"], client=client)
    assert [v["message"] for v in two["versions"]] == ["1970s precinct", "night"]
    near = lambda a, b: all(abs(x - y) <= 4 for x, y in zip(a, b))  # JPEG rounding
    assert near(client.sent[0][1], (120, 100, 80)) and near(client.sent[1][1], (10, 20, 70))  # second edit starts from v1
    assert client.sent[0][2] == "1536x1024" and client.sent[0][3] == "gpt-image-1-mini" and client.sent[0][4] == "low"
    with Image.open(cache / two["versions"][1]["path"]) as saved:
        assert saved.size == (320, 134)  # back to the framed shot's own aspect
    assert two["label"] == fe.LABEL


def test_inputs_are_validated(cache):
    for bad in ["", "data:image/gif;base64,AAAA", "data:image/jpeg;base64,!!!!", "http://example.com/a.jpg"]:
        with pytest.raises(ValueError):
            fe.edit("x", shot_id="s1", image=bad, client=Images())
    with pytest.raises(ValueError):
        fe.edit("x", shot_id="../../etc", image=_data_url(), client=Images())
    with pytest.raises(KeyError):
        fe.edit("x", edit_id="../../etc", client=Images())
    with pytest.raises(ValueError):
        fe.edit("   ", shot_id="s1", image=_data_url(), client=Images())


def test_route_maps_errors(monkeypatch):
    from agent.app import app
    c = TestClient(app)
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "0")
    assert c.post("/api/frame/edit", json={"message": "x", "shot_id": "s1", "image": _data_url()}).status_code == 403
    assert c.post("/api/frame/edit", json={"message": "x", "edit_id": "zz"}).status_code == 422
    monkeypatch.setenv("TYPECAST_ALLOW_VISION_UPLOAD", "1")
    assert c.post("/api/frame/edit", json={"message": "x", "edit_id": "0" * 16}).status_code == 404


def test_a_wide_frame_is_letterboxed_for_the_model_not_stretched(cache):
    """A 2.39:1 frame goes on a 3:2 canvas with black bars, and only the frame comes back."""
    class Echo(Images):
        def _post(self, path, files, data, timeout):
            with Image.open(io.BytesIO(files["image"][1])) as image:
                self.sent.append((image.size, image.copy(), data["prompt"]))
                buf = io.BytesIO()
                image.convert("RGB").save(buf, "PNG")
            return {"data": [{"b64_json": base64.b64encode(buf.getvalue()).decode()}]}
    client = Echo()
    out = fe.edit("night", shot_id="s1", image=_data_url((717, 300), (200, 40, 40)), client=client)
    size, sent, prompt = client.sent[0]
    assert size == (1536, 1024) and "letterboxing" in prompt
    assert sent.getpixel((768, 20)) == (0, 0, 0) and sent.getpixel((768, 1003)) == (0, 0, 0)  # bars above and below
    assert abs(sent.getpixel((768, 512))[0] - 200) <= 6  # the view itself, undistorted, in the middle
    with Image.open(cache / out["versions"][0]["path"]) as saved:
        assert saved.size == (717, 300)
        assert all(abs(saved.getpixel(xy)[0] - 200) <= 12 for xy in [(358, 2), (358, 297), (2, 150), (714, 150)])
