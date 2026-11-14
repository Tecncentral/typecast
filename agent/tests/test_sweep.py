"""GET /api/sweep/{shot_id}: the scan point's faces for the 360-degree viewfinder."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agent.app import app
from contracts.schemas import Shot
from index import search


def _shot(sweep: str, heading: float, model: str = "m1") -> Shot:
    shot_id = f"p1-{model}-{sweep}-{heading:.3f}-abc"
    return Shot(shot_id=shot_id, model_id=model, sweep_id=sweep, heading_deg=heading,
                image_path=f"/cache/views/{shot_id}.jpg", property_id="p1",
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
def client():
    shots = [_shot("s1", h) for h in (270.0, 0.0, 180.0, 90.0)]
    shots += [_shot("s2", 0.0), _shot("s1", 0.0, model="m2")]
    search.configure_index(_FakeIndex(shots))
    yield TestClient(app)
    search.configure_index(None)


def test_returns_four_faces_of_the_same_scan_point_in_heading_order(client):
    body = client.get("/api/sweep/p1-m1-s1-90.000-abc").json()
    assert [f["heading_deg"] for f in body["faces"]] == [0, 90, 180, 270]
    assert {f["shot_id"].split("-")[2] for f in body["faces"]} == {"s1"}
    assert {f["shot_id"].split("-")[1] for f in body["faces"]} == {"m1"}
    assert body["heading_deg"] == 90.0 and body["measure_on_site"] is True and body["depth_m"] is None


def test_unknown_and_invalid_ids(client):
    assert client.get("/api/sweep/p1-m1-s9-0.000-abc").status_code == 404
    assert client.get("/api/sweep/bad%20id").status_code == 422


def test_unavailable_index_is_503(monkeypatch):
    def broken():
        raise RuntimeError("no index")
    monkeypatch.setattr(search, "get_active_index", broken)
    assert TestClient(app).get("/api/sweep/p1-m1-s1-0.000-abc").status_code == 503
