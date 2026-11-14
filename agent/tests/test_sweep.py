"""GET /api/sweep/{shot_id}: the scan point's faces for the 360-degree viewfinder."""
import importlib
import json

from PIL import Image

import pytest
from fastapi.testclient import TestClient

from agent.app import app
from contracts.schemas import Shot
from index import search


def _shot(sweep: str, heading: float, model: str = "m1", property_id: str = "p1") -> Shot:
    shot_id = f"{property_id}-{model}-{sweep}-{heading:.3f}-abc"
    return Shot(shot_id=shot_id, model_id=model, sweep_id=sweep, heading_deg=heading,
                image_path=f"/cache/views/{shot_id}.jpg", property_id=property_id,
                room_area_m2=40.0, ceiling_m=2.7, measure_on_site=True)


class _FakeIndex:
    def __init__(self, shots):
        self.shots = shots

    def get_shot(self, shot_id):
        for shot in self.shots:
            if shot.shot_id == shot_id:
                return shot
        raise KeyError(shot_id)


@pytest.fixture
def client(tmp_path, monkeypatch):
    shots = [_shot("s1", h) for h in (270.0, 0.0, 180.0, 90.0)]
    shots += [_shot("s2", 0.0), _shot("s1", 0.0, model="m2"), _shot("s1", 0.0, property_id="p2")]
    # Synthetic cube fixtures explicitly declare their projection; ordinary mock
    # index views have no such evidence and must remain unsupported.
    module = importlib.import_module("agent.app")
    monkeypatch.setattr(module, "__file__", str(tmp_path / "agent/app.py"))
    viewdir = tmp_path / "cache/views"
    viewdir.mkdir(parents=True)
    provenance = {}
    for shot in shots:
        Image.new("RGB", (8, 8), "navy").save(viewdir / f"{shot.shot_id}.jpg")
        provenance[shot.shot_id] = {"cube_face_index": int(shot.heading_deg / 90) + 1}
    (tmp_path / "cache/view-provenance.json").write_text(json.dumps(provenance))
    search.configure_index(_FakeIndex(shots))
    yield TestClient(app)
    search.configure_index(None)


def test_returns_four_faces_of_the_same_scan_point_in_heading_order(client):
    body = client.get("/api/sweep/p1-m1-s1-90.000-abc").json()
    assert [f["heading_deg"] for f in body["faces"]] == [0, 90, 180, 270]
    assert {f["shot_id"].split("-")[2] for f in body["faces"]} == {"s1"}
    assert {f["shot_id"].split("-")[1] for f in body["faces"]} == {"m1"}
    assert {f["shot_id"].split("-")[0] for f in body["faces"]} == {"p1"}
    assert body["heading_deg"] == 90.0 and body["measure_on_site"] is True and body["depth_m"] is None


def test_unknown_and_invalid_ids(client):
    assert client.get("/api/sweep/p1-m1-s9-0.000-abc").status_code == 404
    assert client.get("/api/sweep/bad%20id").status_code == 422


def test_unavailable_index_is_503(monkeypatch):
    def broken():
        raise RuntimeError("no index")
    monkeypatch.setattr(search, "get_active_index", broken)
    assert TestClient(app).get("/api/sweep/p1-m1-s1-0.000-abc").status_code == 503


def test_generic_perspective_views_have_no_cube_claim(client, monkeypatch):
    module = importlib.import_module("agent.app")
    monkeypatch.setattr(module, "_sweep_provenance", lambda: {})
    response = client.get("/api/sweep/p1-m1-s1-90.000-abc")
    assert response.status_code == 422
    assert "verified horizon cube" in response.json()["detail"]


def test_partial_cube_keeps_holes_and_never_substitutes_other_views(client, monkeypatch):
    module = importlib.import_module("agent.app")
    provenance = module._sweep_provenance()
    del provenance["p1-m1-s1-180.000-abc"]
    monkeypatch.setattr(module, "_sweep_provenance", lambda: provenance)
    body = client.get("/api/sweep/p1-m1-s1-90.000-abc").json()
    assert [face["heading_deg"] for face in body["faces"]] == [0, 90, 270]
    assert body["projection"] == "horizon-cube-90deg"
    assert "scan-relative" in body["heading_reference"]


@pytest.mark.parametrize("image_path", ["https://example.test/face.jpg", "/cache/matterport/raw.jpg", "/cache/views/../private.jpg"])
def test_sweep_rejects_non_view_paths(client, monkeypatch, image_path):
    module = importlib.import_module("agent.app")
    index = search.get_active_index()
    index.shots = [s.model_copy(update={"image_path": image_path}) if s.shot_id == "p1-m1-s1-180.000-abc" else s for s in index.shots]
    body = client.get("/api/sweep/p1-m1-s1-90.000-abc").json()
    assert [face["heading_deg"] for face in body["faces"]] == [0, 90, 270]


def test_cube_requires_matching_face_axis_and_square_image(client):
    module = importlib.import_module("agent.app")
    index = search.get_active_index()
    provenance = module._sweep_provenance()
    shot = index.get_shot("p1-m1-s1-90.000-abc")
    assert module._cube_face(shot.model_copy(update={"heading_deg": 90.1}), provenance) is None
    image = module.pathlib.Path(module.__file__).resolve().parents[1] / shot.image_path.lstrip("/")
    Image.new("RGB", (12, 8), "navy").save(image)
    assert client.get(f"/api/sweep/{shot.shot_id}").status_code == 422
