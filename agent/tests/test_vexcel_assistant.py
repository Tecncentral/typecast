import pytest
from fastapi.testclient import TestClient

from agent import vexcel_assistant as va

LAT, LON = 34.0557, -118.2763


def test_guard_allows_only_read_only_data_tools():
    for name in ("usage_query", "user_profile_query", "property_report", "ortho_extract", "oriented_extract"):
        with pytest.raises(va.AssistantError):
            va.guard(name, {}, LAT, LON)


def test_guard_keeps_geometry_near_the_place_and_clamps_cost():
    with pytest.raises(va.AssistantError):
        va.guard("dtm_elevation", {"wkt": "POINT(-105.27 40.01)"}, LAT, LON)  # Boulder, not LA
    with pytest.raises(va.AssistantError):
        va.guard("dtm_elevation", {"wkt": "POLYGON((-118.27 34.05, -118.0 34.05, -118.27 34.06, -118.27 34.05))"}, LAT, LON)
    args = va.guard("property_metadata_extract", {"wkt": f"POINT({LON} {LAT})", "buffer-meter": 5000,
                                                  "total-records": 2500, "pool": False, "automobile": True,
                                                  "roof-material": "membrane", "min-roof-condition": 0}, LAT, LON)
    assert args == {"wkt": f"POINT({LON} {LAT})", "buffer-meter": 500.0, "total-records": 10, "automobile": True}


def test_guard_defaults_the_place_and_bounds_detection():
    assert va.guard("ortho_estimate_dates", {}, LAT, LON) == {"wkt": f"POINT({LON} {LAT})"}
    assert va.guard("elements_detect", {"buffer-meter": 900}, LAT, LON)["buffer-meter"] == 150
    assert va.guard("embedding_extract", {"search-text": "pool"}, LAT, LON)["total-records"] == 5


def test_tool_results_never_echo_the_key(monkeypatch):
    monkeypatch.setenv("VEXCEL_API_KEY", "secret-key-123")
    mcp = va.VexcelMCP()
    monkeypatch.setattr(mcp, "_rpc", lambda *a, **k: {"content": [{"type": "text", "text": "url?api_key=secret-key-123"},
                                                                  {"type": "image", "data": "..."}]})
    out = mcp.call("dtm_elevation", {})
    assert "secret-key-123" not in out and "[image omitted]" in out


def test_ask_route_validates(monkeypatch):
    from agent.app import app
    c = TestClient(app)
    assert c.post("/api/oblique/ask", json={"search_id": "0" * 16, "index": 0, "question": ""}).status_code == 422
    assert c.post("/api/oblique/ask", json={"search_id": "0" * 16, "index": 0, "question": "hi"}).status_code == 404
