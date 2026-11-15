import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from agent import oblique_search as oblique
from data import vexcel_oblique
from data.vexcel_client import ProviderError


def _png(color=(120, 110, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, "PNG")
    return buf.getvalue()


class FakeClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def search_tiles(self, text, lat, lon, radius_m, k=16):
        FakeClient.calls.append("search")
        return [{"lat": 34.05, "lon": -118.25, "score": 0.2, "collection": "c"},
                {"lat": 34.0501, "lon": -118.2501, "score": 0.19, "collection": "c"},  # same place, 14 m away
                {"lat": 34.06, "lon": -118.26, "score": 0.15, "collection": "c"}]

    def oblique(self, lat, lon, direction, **kwargs):
        FakeClient.calls.append(f"oblique-{direction}")
        if direction == "north" and lat > 34.055:
            raise ProviderError("Vexcel HTTP 404")
        return _png()

    def elevations(self, points, model="dtm"):
        FakeClient.calls.append(model)
        return [100.0 + i for i in range(len(points))] if model == "dtm" else [104.0 + 1.5]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    FakeClient.calls = []
    monkeypatch.setattr(oblique, "ObliqueClient", FakeClient)
    monkeypatch.setattr(oblique, "CACHE", tmp_path / "oblique")
    monkeypatch.setattr(oblique, "ROOT", tmp_path)
    monkeypatch.setattr(oblique, "_score", lambda query, places: None)
    return tmp_path


def test_search_merges_places_fetches_obliques_and_terrain_then_caches(fake):
    result = oblique.search("fountain plaza", "la-downtown", client=FakeClient())
    assert [r["rank"] for r in result["results"]] == [1, 2]
    first, second = sorted(result["results"], key=lambda r: r["index"])
    assert first["image"]["direction"] == "north"
    assert second["image"]["direction"] == "east"  # no north oblique there: the next side is used
    assert first["terrain"]["status"] == "estimated" and first["terrain"]["relief_m"] > 0
    assert first["terrain"]["above_ground_m"] == round(105.5 - first["terrain"]["ground_m"], 1)
    assert "access, permission or clearance" in " ".join(result["notes"])
    calls = len(FakeClient.calls)
    again = oblique.search("Fountain   plaza", "la-downtown", client=FakeClient())
    assert again["search_id"] == result["search_id"] and len(FakeClient.calls) == calls  # cached, no new calls


def test_search_rejects_unknown_area_and_empty_query(fake):
    with pytest.raises(ValueError):
        oblique.search("x", "mars")
    with pytest.raises(ValueError):
        oblique.search("   ", "la-downtown")


def test_view_and_chat_paths_are_validated(fake):
    result = oblique.search("fountain plaza", "la-downtown", client=FakeClient())
    with pytest.raises(KeyError):
        oblique.view("../../etc", 0, "north")
    with pytest.raises(KeyError):
        oblique.view(result["search_id"], 99, "north")
    view = oblique.view(result["search_id"], 0, "south")
    assert view["path"].endswith("0-south.jpg")
    assert oblique.chat(result["search_id"], 0, "south")["versions"] == []


def test_reimagine_builds_on_the_latest_version_and_labels_it(fake, monkeypatch):
    import base64
    result = oblique.search("fountain plaza", "la-downtown", client=FakeClient())
    sent = []

    class Images:
        def _post(self, path, files, data, timeout):
            sent.append((files["image"][1][:8], data["model"], data["quality"]))
            return {"data": [{"b64_json": base64.b64encode(_png((10, 10, 40))).decode()}]}

    monkeypatch.setenv("TYPECAST_OBLIQUE_IMAGE_MODEL", "cheap-model")
    one = oblique.reimagine(result["search_id"], 0, "north", "night", client=Images())
    two = oblique.reimagine(result["search_id"], 0, "north", "add a food truck", client=Images())
    assert [v["message"] for v in two["versions"]] == ["night", "add a food truck"]
    assert two["label"] == oblique.LABEL and sent[0][1] == "cheap-model" and sent[0][2] == "low"
    assert one["versions"][0]["path"].endswith("-v1.jpg") and two["versions"][1]["path"].endswith("-v2.jpg")


def test_terrain_cross_and_summary():
    points = vexcel_oblique.cross_points(34.0, -118.0)
    assert len(points) == 18 and points[4] == points[13] == (34.0, -118.0)
    flat = vexcel_oblique.terrain_summary([10.0] * 18)
    assert flat == {"ground_m": 10.0, "relief_m": 0.0, "max_slope_deg": 0.0}
    hill = vexcel_oblique.terrain_summary([10.0 + 25 * i for i in range(9)] + [210.0] * 9)
    assert hill["relief_m"] == 200.0 and hill["max_slope_deg"] == 45.0


def test_elevation_parsing_and_endpoint_allowlist(monkeypatch):
    monkeypatch.setenv("VEXCEL_API_KEY", "test-key")
    client = vexcel_oblique.ObliqueClient()
    monkeypatch.setattr(client, "_request", lambda method, url, **kw: json.dumps(
        {"wkt": "LINESTRING Z(-118.3 34.1 345.7, -118.3 34.13 464.4)"}).encode())
    assert client.elevations([(34.1, -118.3), (34.13, -118.3)]) == [345.7, 464.4]
    with pytest.raises(ValueError):
        client._call("elements/detect", {})


def test_routes_validate_input(fake):
    from agent.app import app
    c = TestClient(app)
    areas = c.get("/api/oblique/areas").json()
    assert {"id", "label", "city"} <= set(areas["areas"][0]) and areas["image_model"]
    assert c.post("/api/oblique/search", json={"query": "x", "area": "Mars!"}).status_code == 422
    assert c.post("/api/oblique/view", json={"search_id": "0" * 16, "index": 0, "direction": "north"}).status_code == 404
    assert c.post("/api/oblique/view", json={"search_id": "0" * 16, "index": 0, "direction": "up"}).status_code == 422
