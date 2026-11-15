"""Strike: blending keeps the real scan, decision gates, cache validation, the route and key safety."""
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from agent.app import app
from contracts.schemas import Shot
from index import search
from strike import core

KEY = "sk-test-STRIKE-SECRET-123"


def _room(size=512):
    x = np.linspace(0, 255, size, dtype=np.float32)
    rgb = np.stack([np.tile(x, (size, 1)), np.tile(x[:, None], (1, size)), np.full((size, size), 140, np.float32)], axis=2)
    return Image.fromarray(rgb.astype(np.uint8))


def test_blend_keeps_unchanged_pixels_from_the_real_scan():
    real = _room(512)
    edited = np.asarray(real.resize((256, 256)), dtype=np.uint8).copy()
    edited[150:230, 60:180] = (205, 200, 190)          # the "sofa" region repainted as floor
    out, changed = core.blend(real, Image.fromarray(edited))
    a, b = np.asarray(real), np.asarray(out)
    assert (a[:120, :] == b[:120, :]).all()             # far from the edit: the real pixels, untouched
    assert np.abs(a[340:440, 160:330].astype(int) - b[340:440, 160:330].astype(int)).mean() > 20
    assert 0.1 < changed < 0.5


class _FakeClient:
    def __init__(self, furnished=0.95, kept=0.9, empty=0.9):
        self.p = {"furnished": furnished, "kept": kept, "empty": empty}
        self.edits = 0

    def predicates(self, images, questions):
        if questions == [core.Q_FURNISHED]:
            return [self.p["furnished"]]
        return [self.p["kept"], self.p["empty"]]

    def remove_furniture(self, image):
        self.edits += 1
        out = np.asarray(image.resize((256, 256))).copy()
        out[150:230, 60:180] = 200
        return Image.fromarray(out)


def test_gates_skip_empty_rooms_reject_changed_architecture_and_accept_good_edits():
    room = _room(512)
    skip = _FakeClient(furnished=0.1)
    assert core.strike_face(room, skip)["status"] == "already_empty" and skip.edits == 0
    bad = core.strike_face(room, _FakeClient(kept=0.3))
    assert bad["status"] == "rejected" and bad["image"] is None and bad["reason"] == "architecture_changed"
    good = core.strike_face(room, _FakeClient())
    assert good["status"] == "struck" and good["image"].size == (512, 512) and good["architecture_kept_p"] == 0.9


def _write(tmp_path, model="m1", sweep="s1", faces=None):
    d = tmp_path / model / sweep
    d.mkdir(parents=True)
    _room(64).save(d / "struck_000.jpg")
    faces = faces if faces is not None else [
        {"heading_deg": 0, "status": "struck", "struck": "struck_000.jpg", "architecture_kept_p": 0.97, "empty_p": 0.9},
        {"heading_deg": 90, "status": "already_empty", "furnished_p": 0.02},
        {"heading_deg": 180, "status": "struck", "struck": "../escape.jpg"},
    ]
    (d / "strike.json").write_text(json.dumps({"model_id": model, "sweep_id": sweep, "faces": faces,
                                               "label": "forged label", "edit_model": "x"}))
    return d


def test_loader_validates_the_cache_and_never_trusts_its_label(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPECAST_STRIKE_DIR", str(tmp_path))
    _write(tmp_path)
    record = core.load_strike("m1", "s1")
    assert record["label"] == core.LABEL
    urls = {f["heading_deg"]: f["struck_url"] for f in record["faces"]}
    assert urls == {0: "/cache/strike/m1/s1/struck_000.jpg", 90: None, 180: None}
    assert core.load_strike("m1", "other") is None and core.load_strike("../m1", "s1") is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    shot = Shot(shot_id="p1-m1-s1-0.000-abc", model_id="m1", sweep_id="s1", heading_deg=0.0,
                image_path="/cache/views/p1-m1-s1-0.000-abc.jpg", property_id="p1")
    other = Shot(shot_id="p1-m1-s2-0.000-abc", model_id="m1", sweep_id="s2", heading_deg=0.0,
                 image_path="/cache/views/p1-m1-s2-0.000-abc.jpg", property_id="p1")

    class _Index:
        shots = [shot, other]

        def get_shot(self, shot_id):
            for s in self.shots:
                if s.shot_id == shot_id:
                    return s
            raise KeyError(shot_id)

    search.configure_index(_Index())
    monkeypatch.setenv("TYPECAST_STRIKE_DIR", str(tmp_path))
    _write(tmp_path)
    yield TestClient(app)
    search.configure_index(None)


def test_route_returns_the_shot_face_and_404_422_and_disable(client, monkeypatch):
    body = client.get("/api/strike/p1-m1-s1-0.000-abc").json()
    assert body["label"] == "AI-edited: furniture removed, not the real room"
    assert body["face"]["struck_url"] == "/cache/strike/m1/s1/struck_000.jpg"
    assert client.get("/api/strike/p1-m1-s2-0.000-abc").status_code == 404
    assert client.get("/api/strike/bad%20id").status_code == 422
    monkeypatch.setenv("TYPECAST_ENABLE_STRIKE", "0")
    assert client.get("/api/strike/p1-m1-s1-0.000-abc").status_code == 404


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class _Session:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return self.replies.pop(0)


def test_decisions_client_parses_probabilities_and_never_leaks_the_key():
    session = _Session([_Resp(200, {"answers": [{"type": "predicate", "probability": 0.83}]}),
                        _Resp(401, {"error": {"message": f"bad key {KEY}"}})])
    c = core.OpenAIClient(api_key=KEY, session=session, sleep=lambda s: None)
    assert c.predicates([_room(64)], ["q?"]) == [0.83]
    sent = session.calls[0][1]["json_body"] if "json_body" in session.calls[0][1] else session.calls[0][1]["json"]
    assert sent["questions"] == [{"type": "predicate", "instructions": "q?"}]
    assert sent["input"][0]["content"][0]["type"] == "input_image"
    with pytest.raises(core.StrikeError) as err:
        c.predicates([_room(64)], ["q?"])
    assert "401" in str(err.value) and KEY not in str(err.value)
    assert all(kw["allow_redirects"] is False for _, kw in session.calls)
