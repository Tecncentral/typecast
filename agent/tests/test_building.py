import json

import pytest

from agent import building as bd

LAT, LON = 34.0557, -118.2763


def _square(cx_m, cy_m, half_m):
    """A square footprint WKT centred cx_m east / cy_m north of the place."""
    import math
    kx = 111_320.0 * math.cos(math.radians(LAT))
    pts = [(cx_m - half_m, cy_m - half_m), (cx_m + half_m, cy_m - half_m), (cx_m + half_m, cy_m + half_m),
           (cx_m - half_m, cy_m + half_m), (cx_m - half_m, cy_m - half_m)]
    return "MULTIPOLYGON (((" + ", ".join(f"{LON + x / kx} {LAT + y / 110_574.0}" for x, y in pts) + ")))"


def _feature(wkt, area, distance, **extra):
    return {"properties": {"footprint.wkt": wkt, "footprint.area": area, "structure-distance": distance,
                           "building-type.class": "commercial", "roof-characteristics.height": 11.26,
                           "roof-characteristics.shape.value": "flat", "roof-characteristics.material.class": "membrane",
                           "roof-objects.ac-unit.count": 1, "roof-objects.roof-vent.count": 23,
                           "roof-objects.skylight.count": 4, "roof-objects.solar.value": False,
                           "roof-defects.discoloration.types.water-pooling.detected": True,
                           "roof-defects.discoloration.types.water-pooling.percent": 31.35,
                           "roof-defects.rust.detected": False, "metadata.ortho-date-estimate": 1783107444000,
                           **extra}}


class FakeMCP:
    def __init__(self, features):
        self.features = features
        self.calls = 0

    def connect(self):
        return []

    def _rpc(self, method, params):
        self.calls += 1
        return {"content": [{"type": "text", "text": json.dumps({"features": self.features})}]}


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "CACHE", tmp_path)
    return tmp_path


def test_the_building_containing_the_point_wins_over_vexcels_distance_field(cache):
    beside = _feature(_square(0, -30, 15), 900.0, 0.7)  # Vexcel says nearest, but it is 15 m away
    under = _feature(_square(10, 5, 40), 2214.85, 0.8)  # contains the point
    mcp = FakeMCP([beside, under])
    record = bd.building(LAT, LON, mcp=mcp)
    assert record["found"] and record["contains_point"] and record["footprint_m2"] == 2214.85
    assert record["distance_m"] == 0.0 and record["others_nearby"] == 1
    assert bd.building(LAT, LON, mcp=mcp) == record and mcp.calls == 1  # cached


def test_without_a_containing_building_the_closest_outline_is_used(cache):
    far = _feature(_square(0, 60, 10), 400.0, 0.1)
    near = _feature(_square(0, -20, 10), 400.0, 9.0)
    record = bd.building(LAT, LON, mcp=FakeMCP([far, near]))
    assert record["contains_point"] is False and 9.5 < record["distance_m"] < 10.5


def test_summary_lists_only_detected_things_and_dates_the_imagery(cache):
    record = bd.building(LAT, LON, mcp=FakeMCP([_feature(_square(0, 0, 20), 1600.0, 1.0)]))
    assert [(o["label"], o["count"]) for o in record["roof_objects"]] == [("AC unit", 1), ("vent", 23), ("skylight", 4)]
    assert [d["label"] for d in record["roof_defects"]] == ["water pooling"]
    assert record["imagery"]["date"] == "2026-07-03" and record["height_m"] == 11.26
    assert bd.prompt_facts(record) == ("The building at the centre is a commercial building; footprint about 1,600 m²; "
                                       "about 11 m tall; flat membrane roof; on the roof: 1 AC unit, 23 vents, 4 skylights.")


def test_no_structure_is_reported_not_guessed(cache):
    record = bd.building(LAT, LON, mcp=FakeMCP([]))
    assert record == {"found": False, "reason": "Vexcel has no structure record within 25 m of this place."}
    assert bd.prompt_facts(record) == ""


@pytest.mark.parametrize("reply", [
    {"isError": True, "content": [{"type": "text", "text": "Upstream timeout"}]},
    {"content": [{"type": "text", "text": "Internal error: rate limited"}]},
    {"content": [{"type": "text", "text": json.dumps({"message": "Bad request"})}]},
    {},
])
def test_a_vexcel_failure_is_reported_and_never_cached_as_no_building(cache, reply):
    from agent.vexcel_assistant import AssistantError

    class Failing(FakeMCP):
        def _rpc(self, method, params):
            self.calls += 1
            return reply
    mcp = Failing([])
    with pytest.raises(AssistantError):
        bd.building(LAT, LON, mcp=mcp)
    assert list(cache.iterdir()) == []
    good = FakeMCP([_feature(_square(0, 0, 10), 400.0, 1.0)])
    assert bd.building(LAT, LON, mcp=good)["found"] is True and good.calls == 1
