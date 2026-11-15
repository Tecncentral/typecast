import json
import math

import pytest
from fastapi.testclient import TestClient

from data import vexcel_3d


def _region(w, s, e, n):
    return {"region": [math.radians(w), math.radians(s), math.radians(e), math.radians(n), 0, 100]}


TILESETS = {
    "root": {"asset": {"extras": {"minCaptureDate": "2020/11/21", "maxCaptureDate": "2021/1/20"}},
             "root": {"boundingVolume": _region(-119, 33.9, -117.8, 34.3), "children": [
                 {"boundingVolume": _region(-118.26, 34.05, -118.21, 34.09),
                  "content": {"uri": "./tileset?zoom=13&tile-x=1405&tile-y=3270&childAOI=la-3d"}},
                 {"boundingVolume": _region(-118.8, 34.1, -118.7, 34.2),  # far away: never fetched
                  "content": {"uri": "./tileset?zoom=13&tile-x=1394&tile-y=3268&childAOI=la-3d"}}]}},
    "13": {"root": {"boundingVolume": _region(-118.26, 34.05, -118.21, 34.09), "children": [
        {"boundingVolume": _region(-118.26, 34.05, -118.24, 34.06),
         "content": {"uri": "./tile?zoom=17&tile-x=22481&tile-y=52334&childAOI=la-3d"}},
        {"boundingVolume": _region(-118.2535, 34.0550, -118.2525, 34.0556),
         "content": {"uri": "./tile?zoom=19&tile-x=89925&tile-y=209339&childAOI=la-3d"}},
        {"boundingVolume": _region(-118.2535, 34.0550, -118.2525, 34.0556),
         "content": {"uri": "./tile?zoom=20&tile-x=179851&tile-y=418678&childAOI=la-3d"}}]}},
}


class FakeCity(vexcel_3d.City3D):
    def __init__(self):
        self.fetched = []

    def _fetch(self, endpoint, params, suffix):
        self.fetched.append((endpoint, params))
        if endpoint == "3d/collections":
            return json.dumps({"features": [{"properties": {"collection": "la-3d"}}]}).encode()
        if endpoint == "3d/tileset":
            return json.dumps(TILESETS["root" if "collection" in params else str(params["zoom"])]).encode()
        return b"glTF" + b"\0" * 16


def test_place_walks_to_the_deepest_tiles_near_the_point_up_to_the_target_zoom():
    city = FakeCity()
    place = city.place(34.0553, -118.2530)
    assert place["collection"] == "la-3d" and place["zoom"] == 19
    assert place["tiles"] == [{"zoom": 19, "tile-x": 89925, "tile-y": 209339, "childAOI": "la-3d"}]
    assert place["capture"] == ["2020/11/21", "2021/1/20"]
    assert all(p.get("tile-x") != 1394 for _, p in city.fetched), "a far-away tileset was fetched"


def test_tile_references_are_validated_before_any_request():
    for bad in [(24, 0, 0, "la"), (19, -1, 0, "la"), (3, 8, 0, "la"), (19, 1, 1, "../x"), (19, 1, 1, "")]:
        with pytest.raises(ValueError):
            vexcel_3d.tile_params(*bad)
    assert vexcel_3d.tile_params("19", "89925", "209339", "la-3d")["zoom"] == 19
    city = FakeCity()
    with pytest.raises(ValueError):
        city.tile({"zoom": 19, "tile-x": 1, "tile-y": 1, "childAOI": "bad aoi"})
    assert city.fetched == []


def test_routes_reject_bad_input(monkeypatch):
    from agent.app import app
    c = TestClient(app)
    assert c.get("/api/vexcel3d/tile", params={"zoom": 19, "tile-x": 1, "tile-y": 1, "childAOI": "../x"}).status_code == 400
    assert c.get("/api/vexcel3d/place", params={"lat": 120, "lon": 0}).status_code == 400
