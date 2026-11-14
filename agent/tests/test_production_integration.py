"""Offline shared-server and real Deep Agents tool-graph integration checks."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agent import deep
from agent.deep_tools import ToolSession, make_tools
from agent.interfaces import Requirements, RunContext
from agent.tests.test_deep import DeterministicChat, offline
from contracts.schemas import Logistics, Property, Shot
from index import preview, production, production_integration


@pytest.fixture
def planner_sources(monkeypatch):
    calls = []
    monkeypatch.setattr(production, "get_active_index", lambda: SimpleNamespace(is_mock=True))
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", True)
    monkeypatch.setattr(production.vexcel_tools, "USE_MOCKS", True)

    def search(**kwargs):
        calls.append(kwargs)
        return [Shot(shot_id="production-view", property_id="production-property", model_id="model",
                     sweep_id="sweep", heading_deg=0, image_path="mocks/img/view.jpg", score=.8)]

    monkeypatch.setattr(production, "search_shots", search)
    monkeypatch.setattr(production, "get_property", lambda pid: Property(
        property_id=pid, address="Fixture", city="Los Angeles", lat=0, lon=0, type="Office",
        available=True, availability_status="available"))
    monkeypatch.setattr(production, "plan_logistics", lambda pid, trucks, cars: Logistics(
        property_id=pid, truck_spaces=4, car_spaces=40, parking_status="estimated", estimated=True))
    return calls


def request():
    return {"scenes": [{"id": "s1", "heading": "INT. OFFICE", "description": "Interview"},
                       {"id": "s2", "heading": "INT. LOBBY", "description": "Arrival"}],
            "max_locations": 1, "trucks": 2, "cars": 12}


def test_shared_routes_reuse_same_planner_without_conflicts(planner_sources):
    from agent.app import app

    routes = [(route.path, method) for route in app.routes
              for method in getattr(route, "methods", ())]
    assert len(routes) == len(set(routes))
    with TestClient(app) as client:
        for url, content in [("/director", "text/html"), ("/director.js", "javascript"),
                             ("/director.css", "text/css")]:
            response = client.get(url)
            assert response.status_code == 200 and content in response.headers["content-type"]
        response = client.post("/api/production/plan", json=request())
        assert response.status_code == 200
        assert response.json() == production_integration.run_production_plan(request())
        assert response.json()["plans"][0]["property_ids"] == ["production-property"]
        assert client.post("/api/production/plan", json={**request(), "max_locations": True}).status_code == 422
        assert client.get("/image/not-indexed").status_code == 404
        assert client.get("/api/plan/not-indexed").status_code == 404


def test_indexed_image_containment_and_camera_endpoint(monkeypatch, tmp_path):
    from agent.app import app

    root = tmp_path
    (root / "mocks/img").mkdir(parents=True)
    (root / "mocks/img/view.jpg").write_bytes(b"fixture-image")
    (root / "private.json").write_text("private working state")
    shot = Shot(shot_id="view", property_id="p", model_id="m", sweep_id="s", heading_deg=0,
                image_path="mocks/img/view.jpg")
    monkeypatch.setattr(preview, "ROOT", root)
    monkeypatch.setattr(preview, "get_active_index", lambda: SimpleNamespace(is_mock=True))
    monkeypatch.setattr(preview, "get_shot", lambda sid: shot)
    with TestClient(app) as client:
        response = client.get("/image/view")
        assert response.content == b"fixture-image"
        assert response.headers["cache-control"] == "private, no-store"
        assert client.get("/api/plan/view").json()["shot_id"] == "view"
        assert client.get("/api/plan/view?focal=0").status_code == 422
        shot.image_path = "private.json"
        assert client.get("/image/view").status_code == 404
        shot.image_path = "mocks/img/../../private.json"
        assert client.get("/image/view").status_code == 404


def test_real_graph_executes_registered_production_tool(monkeypatch, planner_sources):
    class ProductionChat(DeterministicChat):
        def _generate(self, messages, **kwargs):
            answer = super()._generate(messages, **kwargs)
            message = answer.generations[0].message
            if any(call["name"] == "build_shortlist" for call in message.tool_calls):
                message.tool_calls.append({"name": "plan_production_shoot", "args": request(),
                                           "id": "actual-production-call", "type": "tool_call"})
            return answer

    model = ProductionChat()
    monkeypatch.setattr(deep, "_chat_model", lambda **kwargs: model)
    sessions = []

    def capture(session):
        sessions.append(session)
        return make_tools(session)

    monkeypatch.setattr(deep, "make_tools", capture)
    events = []
    response = deep.run_deep(RunContext("production-graph", emit=events.append),
                             Requirements(scene="open office"))
    assert response.engine == "deep"
    assert "plan_production_shoot" in sessions[0].calls
    assert sessions[0].production_plan["plans"][0]["property_ids"] == ["production-property"]
    assert len(planner_sources) == 2
    assert any(event.type == "tool" and event.agent == "plan_production_shoot" for event in events)
    assert all("plan_production_shoot" in tools for tools in model._director_tools)


def test_tool_validation_and_sanitized_failure(monkeypatch):
    session = ToolSession(RunContext("production-fail", engine="deep"), Requirements(scene="office"))
    tool = make_tools(session)["plan_production_shoot"]
    with pytest.raises(ValueError):
        tool.invoke({**request(), "trucks": 21})
    events = []
    session.ctx.emit = events.append

    def fail(req):
        raise RuntimeError("private provider payload")

    monkeypatch.setattr(production_integration, "run_production_plan", fail)
    with pytest.raises(RuntimeError):
        tool.invoke(request())
    assert session.failures == ["plan_production_shoot"]
    assert session.production_plan is None
    assert any(event.type == "error" for event in events)
    assert "private provider" not in json.dumps([event.model_dump() for event in events])
