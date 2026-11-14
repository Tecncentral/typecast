"""Production routes exercised offline with explicit, isolated evidence providers."""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from contracts.schemas import Logistics, Property, Shot
from index import production


def plan_request():
    return {
        "scenes": [{"id": "scene1", "heading": "INT. OFFICE", "description": "A quiet interview."}],
        "max_locations": 2, "forbidden_property_ids": [],
        "require_available": False, "trucks": 1, "cars": 10,
    }


def brainstorm_request():
    return {
        "instruction": "Move the actor left for a stronger silhouette.",
        "heading": "INT. OFFICE", "description": "A quiet interview.",
        "shot": {"duration_sec": 5, "dialogue": "Hello.", "actors": [
            {"id": "actor1", "name": "Ada", "pose": "stand", "x0": .4, "y0": .5,
             "x1": .4, "y1": .5, "scale": 1.0},
        ]},
    }


def shot(pid, score=.8):
    return Shot(shot_id=f"shot_{pid}", property_id=pid, model_id=f"model_{pid}",
                sweep_id="sweep1", heading_deg=0, image_path="cache/test.jpg", score=score)


def property_record(pid, status="available"):
    return Property(property_id=pid, address="Fixture address", city="Fixture city",
                    lat=0, lon=0, type="Office", available=status == "available",
                    availability_status=status)


@pytest.fixture
def offline(monkeypatch):
    """Replace every production dependency; nothing here can access licensed sources."""
    from agent import models

    class NoProvider:
        def configured(self):
            return False

        def structured(self, *args, **kwargs):
            raise AssertionError("Unconfigured model must never be invoked")

    monkeypatch.setattr(models, "get_provider", lambda **kwargs: NoProvider())
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "1")
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", True)
    monkeypatch.setattr(production.vexcel_tools, "USE_MOCKS", True)
    monkeypatch.setattr(production, "load_property_model_pairs", lambda path: None)
    state = SimpleNamespace(
        shots=[shot("p_available", .9), shot("p_unknown", .85), shot("p_unavailable", .8)],
        properties={pid: property_record(pid, status) for pid, status in [
            ("p_available", "available"), ("p_unknown", "unknown"),
            ("p_unavailable", "not_available")]},
        logistics={pid: Logistics(property_id=pid, truck_spaces=4, car_spaces=40,
                                  parking_status="estimated", estimated=True)
                   for pid in ["p_available", "p_unknown", "p_unavailable"]},
        search_calls=[], logistics_calls=[],
    )

    def search(*args, **kwargs):
        state.search_calls.append((args, kwargs))
        return [s.model_copy(deep=True) for s in state.shots]

    def logistics(pid, trucks=3, cars=30):
        state.logistics_calls.append((pid, trucks, cars))
        return state.logistics[pid].model_copy(deep=True)

    monkeypatch.setattr(production, "get_active_index", lambda: SimpleNamespace(is_mock=True))
    monkeypatch.setattr(production, "search_shots", search)
    monkeypatch.setattr(production, "get_property", lambda pid: state.properties[pid].model_copy(deep=True))
    monkeypatch.setattr(production, "plan_logistics", logistics)
    app = FastAPI()
    app.include_router(production.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        state.client = client
        yield state


def candidates(body):
    return [candidate for scene in body["scenes"] for candidate in scene["candidates"]]


def assignments(body):
    return [assignment for plan in body["plans"] for assignment in plan["assignments"]]


def test_plan_labels_mock_data_and_preserves_scene_and_evidence(offline):
    request = plan_request()
    response = offline.client.post("/api/production/plan", json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "mock"
    assert {key: body["scenes"][0][key] for key in ("id", "heading", "description")} == request["scenes"][0]
    assert offline.search_calls
    assert offline.logistics_calls
    assert all(call[1:] == (1, 10) for call in offline.logistics_calls)
    assert assignments(body)
    for candidate in candidates(body):
        assert {"shot", "property", "logistics", "warnings", "eligible"} <= candidate.keys()
        assert isinstance(candidate["eligible"], bool)
        for warning in candidate["warnings"]:
            assert {"source", "field", "status", "message"} <= warning.keys()


def test_rejection_replans_without_assigning_forbidden_location(offline):
    request = plan_request()
    original = offline.client.post("/api/production/plan", json=request).json()
    assert any(a["property_id"] == "p_available" for a in assignments(original))
    request["forbidden_property_ids"] = ["p_available"]
    response = offline.client.post("/api/production/plan", json=request)
    assert response.status_code == 200, response.text
    assert assignments(response.json())
    assert all(a["property_id"] != "p_available" for a in assignments(response.json()))


def test_required_availability_rejects_unknown_and_unavailable(offline):
    request = plan_request()
    request["require_available"] = True
    response = offline.client.post("/api/production/plan", json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    assert assignments(body)
    assert {a["property_id"] for a in assignments(body)} == {"p_available"}
    for candidate in candidates(body):
        if candidate["shot"]["property_id"] != "p_available":
            assert candidate["eligible"] is False


def test_legacy_available_boolean_does_not_confirm_unknown_availability(offline):
    offline.shots = [shot("p_available")]
    offline.properties["p_available"] = property_record("p_available").model_copy(
        update={"available": True, "availability_status": None})
    request = plan_request()
    request["require_available"] = True
    response = offline.client.post("/api/production/plan", json=request)
    assert response.status_code == 200, response.text
    assert not assignments(response.json())


def test_known_insufficient_parking_prevents_assignment(offline):
    offline.shots = [shot("p_available")]
    offline.logistics["p_available"] = Logistics(
        property_id="p_available", truck_spaces=0, car_spaces=0, parking_status="measured")
    response = offline.client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 200, response.text
    assert not assignments(response.json())
    assert any(w["status"] == "insufficient" for w in candidates(response.json())[0]["warnings"])


def test_mixed_source_modes_fail_closed_before_retrieval(offline, monkeypatch):
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", False)
    response = offline.client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 503, response.text
    assert not offline.search_calls


def test_aligned_live_sources_are_explicitly_labeled(offline, monkeypatch):
    monkeypatch.setattr(production, "get_active_index", lambda: SimpleNamespace(is_mock=False))
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", False)
    monkeypatch.setattr(production.vexcel_tools, "USE_MOCKS", False)
    response = offline.client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 200, response.text
    assert response.json()["mode"] == "live"


def live_sources(monkeypatch):
    monkeypatch.setattr(production, "get_active_index", lambda: SimpleNamespace(is_mock=False))
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", False)
    monkeypatch.setattr(production.vexcel_tools, "USE_MOCKS", False)


@pytest.mark.parametrize("pairs,expected", [
    (None, "unknown"), (set(), "unknown"),
    ({("p_available", "model_p_available")}, "matched"),
    ({("p_available", "different_model")}, "conflict"),
    ({("different_property", "model_p_available")}, "conflict"),
    ({("unrelated_property", "unrelated_model")}, "unknown"),
])
def test_live_property_model_join_confirms_conflicts_and_preserves_unknown(
        offline, monkeypatch, pairs, expected):
    live_sources(monkeypatch)
    offline.shots = [shot("p_available")]
    monkeypatch.setattr(production, "load_property_model_pairs", lambda path: pairs)
    response = offline.client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 200, response.text
    body = response.json()
    candidate = candidates(body)[0]
    warning = [w for w in candidate["warnings"] if w["field"] == "property_id/model_id"]
    assert len(warning) == 1
    assert warning[0]["source"] == "costar"
    assert warning[0]["status"] == expected
    assert candidate["eligible"] is (expected != "conflict")
    assert bool(assignments(body)) is (expected != "conflict")
    if expected == "matched":
        assert assignments(body)[0]["property_id"] == "p_available"
        assert "location grouping" in warning[0]["message"]


def test_mock_plan_never_claims_private_join_evidence(offline, monkeypatch):
    def forbidden_read(path):
        raise AssertionError("Mock plan must not open the private join")

    monkeypatch.setattr(production, "load_property_model_pairs", forbidden_read)
    response = offline.client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 200, response.text
    assert not any(w["status"] == "matched" for c in candidates(response.json()) for w in c["warnings"])


def test_retrieval_failure_sanitizes_private_details(offline, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_INDEX_SENTINEL licensed cache path")

    monkeypatch.setattr(production, "search_shots", fail)
    response = offline.client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 503
    assert "PRIVATE_INDEX_SENTINEL" not in response.text


def test_duplicate_views_do_not_expand_property_pool_or_repeat_evidence_fetches(offline):
    offline.shots = [shot("p_available", .95), shot("p_available", .9), shot("p_unknown", .8)]
    request = plan_request()
    request["scenes"].append({"id": "scene2", "heading": "INT. OFFICE", "description": "Another interview."})
    response = offline.client.post("/api/production/plan", json=request)
    assert response.status_code == 200, response.text
    assert len(offline.logistics_calls) == 2
    assert all(len(plan["property_ids"]) <= request["max_locations"] for plan in response.json()["plans"])


@pytest.mark.parametrize("trucks,cars", [(0, 0), (1, 10)])
def test_unknown_parking_remains_uncertified_and_explicitly_warned(offline, trucks, cars):
    offline.shots = [shot("p_available")]
    offline.logistics["p_available"] = Logistics(property_id="p_available", parking_status="unknown")
    request = plan_request()
    request.update(trucks=trucks, cars=cars)
    response = offline.client.post("/api/production/plan", json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    assert assignments(body)
    candidate = candidates(body)[0]
    assert candidate["eligible"] is True
    assert candidate["logistics"]["enough_parking"] is None
    assert any(w["status"] == "unknown" and "parking" in w["field"] for w in candidate["warnings"])


def test_provider_failure_is_sanitized_and_never_fabricates_property_evidence(offline, monkeypatch):
    secret = "PRIVATE_PROVIDER_TOKEN_SENTINEL"

    def fail(*args, **kwargs):
        raise RuntimeError(f"provider failure {secret} C:/private/cache")

    monkeypatch.setattr(production, "get_property", fail)
    response = offline.client.post("/api/production/plan", json=plan_request())
    assert response.status_code in (200, 503)
    assert secret not in response.text
    assert "C:/private/cache" not in response.text
    if response.status_code == 200:
        for candidate in candidates(response.json()):
            assert candidate["property"] is None
            assert any(w["source"] == "costar" and w["status"] == "unknown"
                       for w in candidate["warnings"])
        request = plan_request()
        request["require_available"] = True
        strict = offline.client.post("/api/production/plan", json=request)
        assert strict.status_code == 200, strict.text
        assert not assignments(strict.json())


@pytest.mark.parametrize("key,value", [
    ("scenes", []),
    ("scenes", [{"id": "duplicate", "heading": "INT.", "description": "Office"}] * 2),
    ("scenes", [{"id": f"s{i}", "heading": "INT.", "description": "Office"} for i in range(9)]),
    ("max_locations", 0), ("max_locations", 5), ("max_locations", True),
    ("max_locations", "2"), ("max_locations", 1.5),
    ("trucks", -1), ("trucks", 21), ("trucks", True), ("trucks", "1"),
    ("cars", -1), ("cars", 201), ("cars", False), ("cars", "10"),
    ("require_available", "false"),
    ("forbidden_property_ids", [f"p{i}" for i in range(25)]),
    ("unexpected_operation", "delete_location"),
])
def test_plan_rejects_invalid_input_before_retrieval(offline, key, value):
    request = plan_request()
    request[key] = value
    response = offline.client.post("/api/production/plan", json=request)
    assert response.status_code == 422, response.text
    assert not offline.search_calls


class FakeProvider:
    def __init__(self, proposal):
        self.proposal = proposal
        self.calls = []

    def configured(self):
        return True

    def structured(self, instructions, text, output_model, **kwargs):
        self.calls.append((instructions, text))
        return output_model.model_validate(self.proposal)


def install_provider(monkeypatch, proposal):
    from agent import models
    provider = FakeProvider(proposal)
    monkeypatch.setattr(models, "get_provider", lambda **kwargs: provider)
    return provider


def test_brainstorm_returns_valid_proposal_without_mutating_request(offline, monkeypatch):
    request = brainstorm_request()
    snapshot = deepcopy(request)
    proposed = deepcopy(request["shot"])
    proposed["actors"][0].update(x0=.2, x1=.2)
    provider = install_provider(monkeypatch, {
        "summary": "Move Ada left.", "creative_note": "A stronger silhouette.", "shot": proposed,
    })
    response = offline.client.post("/api/production/brainstorm", json=request)
    assert response.status_code == 200, response.text
    assert response.json()["shot"] == proposed
    assert response.json()["summary"] == "Move Ada left."
    assert provider.calls
    assert request == snapshot
    # A later proposal starts with the user's original state, never an implicitly saved edit.
    assert "0.4" in provider.calls[0][1]


def test_brainstorm_unconfigured_provider_returns_503(offline):
    response = offline.client.post("/api/production/brainstorm", json=brainstorm_request())
    assert response.status_code == 503, response.text


@pytest.mark.parametrize("field,value", [
    ("x0", -.01), ("x1", 1.01), ("y0", True), ("y1", "0.5"),
    ("scale", .29), ("scale", 2.01), ("pose", "delete"),
])
def test_brainstorm_rejects_invalid_input_actor(offline, field, value):
    request = brainstorm_request()
    request["shot"]["actors"][0][field] = value
    response = offline.client.post("/api/production/brainstorm", json=request)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("value", [True, "5", 0, 31])
def test_brainstorm_rejects_invalid_duration(offline, value):
    request = brainstorm_request()
    request["shot"]["duration_sec"] = value
    response = offline.client.post("/api/production/brainstorm", json=request)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_brainstorm_rejects_nonfinite_coordinates(offline, value):
    request = brainstorm_request()
    request["shot"]["actors"][0]["x0"] = value
    response = offline.client.post("/api/production/brainstorm", content=json.dumps(request),
                                   headers={"Content-Type": "application/json"})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("case", ["coordinate", "operation", "too_many_actors", "duration"])
def test_brainstorm_rejects_malformed_model_proposals(offline, monkeypatch, case):
    proposal = {"summary": "Proposed change", "creative_note": "Creative suggestion",
                "shot": deepcopy(brainstorm_request()["shot"])}
    if case == "coordinate":
        proposal["shot"]["actors"][0]["x0"] = 5
    elif case == "operation":
        proposal["shot"]["operation"] = "write_file"
    elif case == "too_many_actors":
        proposal["shot"]["actors"] *= 4
    else:
        proposal["shot"]["duration_sec"] = 31
    install_provider(monkeypatch, proposal)
    response = offline.client.post("/api/production/brainstorm", json=brainstorm_request())
    assert response.status_code in (422, 502, 503), response.text


def test_brainstorm_provider_error_is_sanitized(offline, monkeypatch):
    from agent import models

    class FailedProvider(FakeProvider):
        def structured(self, *args, **kwargs):
            raise RuntimeError("PRIVATE_MODEL_TOKEN_SENTINEL and full private prompt")

    monkeypatch.setattr(models, "get_provider", lambda **kwargs: FailedProvider(None))
    response = offline.client.post("/api/production/brainstorm", json=brainstorm_request())
    assert response.status_code in (502, 503), response.text
    assert "PRIVATE_MODEL_TOKEN_SENTINEL" not in response.text
    assert "full private prompt" not in response.text
