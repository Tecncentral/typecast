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


def _ok_table(destinations):
    width = destinations + 1
    return {"code": "Ok",
            "durations": [[0, *([600] * destinations)]],
            "distances": [[0, *([1609.344] * destinations)]],
            "sources": [{"distance": 1}],
            "destinations": [{"distance": 1}] * width}


def test_malformed_coordinates_never_call_the_router(monkeypatch):
    """Strings, nulls, empty lists and out-of-range swaps are not sent to OSRM."""
    commute._CACHE.clear()
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: pytest.fail("No provider call expected"))
    assert commute.coordinates({"lat": "34.0", "lon": "-118"}) is None
    assert commute.coordinates({"lat": None, "lon": 1}) is None
    assert commute.coordinates({"lat": [], "lon": 1}) is None
    assert commute.coordinates({"lat": -118.2, "lon": 34.0}) is None
    assert commute.coordinates({"lng": -118.2, "lat": 34.0}) is None
    origin = {"lat": 34.0, "lon": -118.0}
    routed = commute.route_commutes(origin, {
        "blank": None,
        "text": {"lat": "34.1", "lon": "-118.1"},
        "swapped": {"lat": -118.2, "lon": 34.0},
        "empty": {"lat": [], "lon": []},
    })
    assert set(routed) == {"blank", "text", "swapped", "empty"}
    assert all(row["status"] == "unknown" and row["minutes"] is None for row in routed.values())
    assert commute.route_commutes({"lat": float("nan"), "lon": -118.0}, {"p": {"lat": 34.1, "lon": -118.1}})["p"]["minutes"] is None
    assert commute.route_commutes(origin, {}) == {}


def test_router_url_uses_longitude_then_latitude(monkeypatch):
    commute._CACHE.clear()
    monkeypatch.setattr(commute.time, "sleep", lambda _: None)
    seen = []

    def get(url, **kwargs):
        seen.append(url)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: _ok_table(1))

    monkeypatch.setattr(httpx, "get", get)
    commute.route_commutes({"lat": 10, "lon": 20}, {"p": {"lat": 11, "lon": 21}})
    assert seen == ["https://router.project-osrm.org/table/v1/driving/20,10;21,11"]


def test_misaligned_router_table_does_not_publish_partial_estimates(monkeypatch):
    commute._CACHE.clear()
    monkeypatch.setattr(commute.time, "sleep", lambda _: None)
    calls = {"n": 0}

    def get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
                "code": "Ok", "durations": [[0, 600]], "distances": [[0, 1000]],
                "sources": [{"distance": 0}],
                "destinations": [{"distance": 0}, {"distance": 1}]})
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: _ok_table(2))

    monkeypatch.setattr(httpx, "get", get)
    origin = {"lat": 34, "lon": -118}
    props = {"a": {"lat": 34.01, "lon": -118}, "b": {"lat": 34.02, "lon": -118}}
    first = commute.route_commutes(origin, props)
    assert first["a"]["status"] == "unknown" and first["a"]["minutes"] is None
    assert first["b"]["status"] == "unknown" and first["b"]["minutes"] is None
    second = commute.route_commutes(origin, props)
    assert second["a"]["status"] == "estimated" and second["a"]["minutes"] == 10
    assert calls["n"] == 2


def _http_status(code):
    request = httpx.Request("GET", "https://router.project-osrm.org/table/v1/driving/0,0")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(str(code), request=request, response=response)


@pytest.mark.parametrize("failure", [
    httpx.ConnectError("down"),
    httpx.TimeoutException("timed out"),
    _http_status(503),
])
def test_provider_errors_are_not_cached(monkeypatch, failure):
    commute._CACHE.clear()
    monkeypatch.setattr(commute.time, "sleep", lambda _: None)
    calls = {"n": 0}

    def get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise failure
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: _ok_table(1))

    monkeypatch.setattr(httpx, "get", get)
    origin = {"lat": 34, "lon": -118}
    props = {"p": {"lat": 34.1, "lon": -118}}
    first = commute.route_commutes(origin, props)
    assert first["p"]["status"] == "unknown" and first["p"]["minutes"] is None
    assert "unavailable" in first["p"]["note"]
    second = commute.route_commutes(origin, props)
    assert second["p"]["status"] == "estimated" and second["p"]["minutes"] == 10
    assert calls["n"] == 2


def test_cache_hit_returns_every_requested_property(monkeypatch):
    commute._CACHE.clear()
    monkeypatch.setattr(commute.time, "sleep", lambda _: None)
    calls = {"n": 0}

    def get(url, **kwargs):
        calls["n"] += 1
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: _ok_table(1))

    monkeypatch.setattr(httpx, "get", get)
    origin = {"lat": 34, "lon": -118}
    located = {"a": {"lat": 34.01, "lon": -118}}
    first = commute.route_commutes(origin, located)
    assert first["a"]["status"] == "estimated"
    second = commute.route_commutes(origin, {**located, "b": None})
    assert calls["n"] == 1
    assert second["a"]["minutes"] == first["a"]["minutes"]
    assert second["b"]["status"] == "unknown" and second["b"]["minutes"] is None


def test_null_router_waypoints_stay_unknown_without_raising(monkeypatch):
    commute._CACHE.clear()
    monkeypatch.setattr(commute.time, "sleep", lambda _: None)

    def get(url, **kwargs):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "code": "Ok",
            "durations": [[0, 600, 900]],
            "distances": [[0, 1000, 1000]],
            "sources": [{"distance": 1}],
            "destinations": [{"distance": 0}, {"distance": 1}, None]})

    monkeypatch.setattr(httpx, "get", get)
    result = commute.route_commutes(
        {"lat": 34, "lon": -118},
        {"a": {"lat": 34.01, "lon": -118}, "b": {"lat": 34.02, "lon": -118}})
    assert result["a"]["status"] == "estimated" and result["a"]["minutes"] == 10
    assert result["b"]["status"] == "unknown" and result["b"]["minutes"] is None


def test_null_commute_coordinates_are_422_not_500():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from index.production import router

    app = FastAPI()
    app.include_router(router)
    scene = {"id": "s", "heading": "INT. OFFICE", "description": "office"}
    with TestClient(app, raise_server_exceptions=False) as client:
        bodies = []
        for value in (None, [], {}):
            bodies.append({"lat": value, "lon": -118.0, "max_minutes": 30})
            bodies.append({"lat": 34.0, "lon": value, "max_minutes": 30})
            bodies.append({"lat": 34.0, "lon": -118.0, "max_minutes": value})
        for commute_body in bodies:
            response = client.post("/api/production/plan", json={"scenes": [scene], "commute": commute_body})
            assert response.status_code == 422, response.text
            assert response.headers["content-type"].startswith("application/json")
            assert "Traceback" not in response.text
            assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("value", [True, float("inf"), float("nan"), -1, 181])
def test_invalid_commute_bounds(value):
    with pytest.raises(ValidationError):
        PlanRequest(scenes=[{"id":"s","heading":"INT. OFFICE","description":"office"}],
                    commute={"lat":34.0,"lon":-118.0,"max_minutes":value})
