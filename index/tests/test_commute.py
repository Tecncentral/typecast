from types import SimpleNamespace
import httpx
import pytest
from index import commute
from index.production import PlanRequest
from pydantic import ValidationError


def test_bad_coordinates_and_mock_never_call_router(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: pytest.fail("No provider call expected"))
    assert commute.coordinates({"lat": True, "lon": 1}) is None
    assert commute.coordinates({"lat": float("nan"), "lon": 1}) is None
    assert commute.route_commutes({"lat": 34, "lon": -118}, {"p": {"lat":34,"lon":-118}}, mock=True)["p"]["status"] == "unknown"
    assert commute.route_commutes({"lat": 34, "lon": -118}, {"p": None})["p"]["status"] == "unknown"


def test_table_maps_property_ids_preserves_unreachable_and_reuses_cache(monkeypatch):
    commute._CACHE.clear()
    monkeypatch.setattr(commute.time, "sleep", lambda _: None)
    calls=[]
    def get(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(raise_for_status=lambda:None, json=lambda:{"code":"Ok", "durations":[[0,1800,None,300]], "distances":[[0,16093.44,None,100]],
            "sources":[{"distance":0}],"destinations":[{"distance":0},{"distance":5},{"distance":0},{"distance":1001}]})
    monkeypatch.setattr(httpx, "get", get)
    origin={"lat":34,"lon":-118}
    props={k:{"lat":34+i*.01,"lon":-118} for i,k in enumerate(["a","b","c"])}
    result=commute.route_commutes(origin,props)
    assert result["a"]["minutes"] == 30
    assert result["a"]["miles"] == pytest.approx(10)
    assert result["b"]["status"] == result["c"]["status"] == "unknown"
    assert result["a"]["traffic"] is False
    assert commute.route_commutes(origin,props)==result
    assert len(calls)==1


def test_router_failure_never_fabricates_distance_based_drive_time(monkeypatch):
    commute._CACHE.clear()
    monkeypatch.setattr(commute.time,"sleep",lambda _:None)
    def fail(*a,**kw): raise httpx.ConnectError("unavailable")
    monkeypatch.setattr(httpx,"get",fail)
    r=commute.route_commutes({"lat":34,"lon":-118},{"p":{"lat":34.1,"lon":-118}})
    assert r["p"]["minutes"] is None


@pytest.mark.parametrize("value", [True, float("inf"), float("nan"), -1, 181])
def test_invalid_commute_bounds(value):
    with pytest.raises(ValidationError):
        PlanRequest(scenes=[{"id":"s","heading":"INT. OFFICE","description":"office"}],
                    commute={"lat":34.0,"lon":-118.0,"max_minutes":value})
