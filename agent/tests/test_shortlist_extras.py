import json

import pytest
from fastapi.testclient import TestClient

from agent import shortlist_extras as sx
from data import cost_model

PICKS = [{"property_id": "p1", "address": "1 Main St", "lat": 34.0185, "lon": -118.2190},
         {"property_id": "p2", "address": "2 Oak Ave", "lat": 34.9000, "lon": -118.2000}]


@pytest.fixture
def rents(tmp_path, monkeypatch):
    monkeypatch.setattr(cost_model, "RENT_DIR", tmp_path)

    def write(pid, **record):
        (tmp_path / f"{pid}.json").write_text(json.dumps({"property_id": pid, "caveats": [], **record}))
    return write


def test_costs_show_alternatives_once_and_label_every_rent(rents):
    rents("p1", tier="A", type="Industrial", usd_per_sf_year=12.84, source="active lease listing", date="2026-10-01", age_years=0.1)
    rents("p2", tier="A", type="Multifamily", usd_per_sf_year=30.0, source="active lease listing",
          caveats=["Rate is for commercial space in a multifamily building, not apartment rent."])
    out = sx.costs(PICKS, 2000, 2, {"p1": 21, "p2": 70})
    assert out["dollar_line"] == "Scenario estimate from public pricing ranges and CoStar rent data, not verified savings."
    assert set(out["alternatives"]) == {"build_set", "standing_set", "cgi"}
    for option in [*out["alternatives"].values(), *(p["found_location"] for p in out["picks"])]:
        assert option["total_low_usd"] <= option["total_usd"] <= option["total_high_usd"]
    p1, p2 = out["picks"]
    assert p1["rent"]["shown"] and p1["rent"]["label"] == "This building's CoStar rent"
    assert p2["rent"]["shown"] and p2["rent"]["label"].startswith("Ground-floor retail rent")
    # Longer crew travel costs more; the benchmark day rate itself is the same for both.
    assert p2["found_location"]["total_usd"] > p1["found_location"]["total_usd"]


def test_unpriced_and_multifamily_median_rents_are_hidden(rents):
    rents("p1", tier="C", type="Multifamily", usd_per_sf_year=None, source="no reliable price",
          caveats=["Commercial-space rents are not apartment rent."])
    rents("p2", tier="C", type="Office", usd_per_sf_year=40.0, source="median of 9 tier A listings, Los Angeles Office")
    p1, p2 = sx.costs(PICKS, 2000, 2)["picks"]
    assert p1["rent"] == {"shown": False, "tier": "C",
                          "reason": "No reliable rent for this building: Commercial-space rents are not apartment rent."}
    assert p2["rent"]["label"].startswith("Area median rent")


def test_commutes_use_road_minutes_and_label_straight_line_fallback(monkeypatch):
    from index import commute
    seen = {}

    def fake(origin, properties, *, mock=False):
        seen.update(origin=origin, ids=list(properties), mock=mock)
        return {"p1": {"status": "estimated", "minutes": 21.4, "miles": 13.07, "source": "OSRM / OpenStreetMap"},
                "p2": {"status": "unknown", "minutes": None, "miles": None,
                       "note": "Road routing unavailable; no distance-to-time fallback used"}}
    monkeypatch.setattr(commute, "route_commutes", fake)
    out = sx.commutes("la-studio-zone", PICKS)
    assert seen == {"origin": {"lat": 34.0762, "lon": -118.3767}, "ids": ["p1", "p2"], "mock": False}
    p1, p2 = out["rows"]["p1"], out["rows"]["p2"]
    assert p1["minutes"] == 21 and p1["miles"] == 13.1 and p1["studio_zone"]["inside"] is True
    assert p2["minutes"] is None and p2["straight_line_label"] == "straight-line distance, not drive time"
    assert p2["straight_line_km"] > 90 and p2["studio_zone"]["inside"] is False
    hou = sx.commutes("hou-downtown", PICKS)
    assert all("studio_zone" not in row for row in hou["rows"].values())
    with pytest.raises(ValueError):
        sx.commutes("nowhere", PICKS)


def test_routes_validate_input(monkeypatch):
    from agent.app import app
    c = TestClient(app)
    assert {b["id"] for b in c.get("/api/shortlist/bases").json()["bases"]} == set(sx.BASES)
    assert c.post("/api/shortlist/costs", json={"picks": [], "scene_sqft": 2000, "shoot_days": 2}).status_code == 422
    assert c.post("/api/shortlist/costs", json={"picks": [{"property_id": "../x"}], "scene_sqft": 2000,
                                                "shoot_days": 2}).status_code == 422
    assert c.post("/api/shortlist/costs", json={"picks": [{"property_id": "p1"}], "scene_sqft": 2000,
                                                "shoot_days": 61}).status_code == 422
    assert c.post("/api/shortlist/commutes", json={"base": "nowhere", "picks": PICKS}).status_code == 400
    assert c.post("/api/shortlist/commutes", json={"base": "../etc", "picks": PICKS}).status_code == 422
