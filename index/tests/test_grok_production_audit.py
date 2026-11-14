"""Adversarial audit of the production planner, join loader, and solver.

Tests exercise the routes mounted by the preview app and the pure helpers behind
them. Cases that reproduce a current defect are marked
``pytest.mark.xfail(strict=True, reason='BUG: ...')`` so the suite stays green
until the defect is fixed. Public fixtures only; no network and no licensed cache.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from contracts.schemas import Logistics, Shot
from index import production
from index.production_join import load_property_model_pairs
from index.production_solver import solve_plans

ROOT = Path(__file__).resolve().parents[2]
SECRET_KEYS = (
    "LLM_API_KEY", "VISION_API_KEY", "FALLBACK_API_KEY", "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
)


def plan_request(**overrides):
    body = {
        "scenes": [{"id": "scene1", "heading": "INT. OFFICE", "description": "A quiet interview."}],
        "max_locations": 2,
        "forbidden_property_ids": [],
        "require_available": False,
        "trucks": 1,
        "cars": 10,
    }
    body.update(overrides)
    return body


def brainstorm_request(**overrides):
    body = {
        "instruction": "Move the actor left for a stronger silhouette.",
        "heading": "INT. OFFICE",
        "description": "A quiet interview.",
        "shot": {
            "duration_sec": 5,
            "dialogue": "Hello.",
            "actors": [{
                "id": "actor1", "name": "Ada", "pose": "stand",
                "x0": 0.4, "y0": 0.5, "x1": 0.4, "y1": 0.5, "scale": 1.0,
            }],
        },
    }
    body.update(overrides)
    return body


def make_shot(property_id, model_id=None, score=0.8, **updates):
    payload = dict(
        shot_id=f"shot-{property_id.strip() or 'blank'}",
        property_id=property_id,
        model_id=model_id or f"model-{property_id.strip() or 'blank'}",
        sweep_id="sweep",
        heading_deg=0.0,
        image_path="mocks/img/audit.jpg",
        score=score,
        room_area_m2=40.0,
        ceiling_m=3.0,
        depth_m=6.0,
        measure_on_site=False,
    )
    payload.update(updates)
    return Shot(**payload)


def candidate(scene_id, property_id, shot_id, score):
    return {
        "scene_id": scene_id,
        "property_id": property_id,
        "shot_id": shot_id,
        "score": score,
    }


def assert_no_leak(text, *needles):
    """Fail if a response exposes a traceback, a local path, or a test sentinel."""
    for token in (
        "Traceback (most recent call last)",
        'File "',
        "site-packages",
        "/workspace",
        "cache/join.parquet",
        "property_models.parquet",
        *needles,
    ):
        assert token not in text, f"response leaked {token!r}"


def assert_client_error(response):
    """Invalid requests share one JSON error shape and never become 500s."""
    assert response.status_code in {400, 422}, response.status_code
    assert "json" in response.headers.get("content-type", "")
    body = response.json()
    assert isinstance(body, dict) and isinstance(body.get("detail"), list) and body["detail"]
    for item in body["detail"]:
        assert set(item) == {"type", "loc", "msg"}
        assert isinstance(item["type"], str) and item["type"]
        assert isinstance(item["loc"], list)
        assert all(isinstance(part, (str, int)) for part in item["loc"])
        assert isinstance(item["msg"], str) and item["msg"]
    assert_no_leak(response.text)
    return body


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(production.router)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def mocks(monkeypatch):
    """Force the exact mock flag and drop any cached live index."""
    from index import search

    monkeypatch.setenv("TYPECAST_USE_MOCKS", "1")
    for key in SECRET_KEYS:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("TYPECAST_AUDIT_SENTINEL", "audit-sentinel-not-a-secret")
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", True)
    monkeypatch.setattr(production.vexcel_tools, "USE_MOCKS", True)
    monkeypatch.setattr(search, "USE_MOCKS", True)
    monkeypatch.setattr(search, "_INITIAL_USE_MOCKS", True)
    monkeypatch.setattr(search, "_ACTIVE_INDEX", None)
    monkeypatch.setattr(search, "_CACHE_DIR_OVERRIDE", None)


def install_sources(monkeypatch, shots, logistics, prop=None):
    monkeypatch.setattr(production, "get_active_index", lambda: SimpleNamespace(is_mock=True))
    monkeypatch.setattr(production, "search_shots", lambda **kwargs: list(shots))

    def _logistics(property_id, trucks, cars):
        return logistics(property_id, trucks, cars)

    monkeypatch.setattr(production, "plan_logistics", _logistics)
    monkeypatch.setattr(
        production, "get_property",
        prop or (lambda property_id: {
            "property_id": property_id,
            "availability_status": "unknown",
        }),
    )


def scene_candidates(body):
    return [item for scene in body["scenes"] for item in scene["candidates"]]


def assignments(body):
    return [item for plan in body["plans"] for item in plan["assignments"]]


# ---------------------------------------------------------------------------
# Request limits and error shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mutate", [
    "empty_scenes",
    "nine_scenes",
    "duplicate_ids",
    "duplicate_ids_after_strip",
    "blank_heading",
    "huge_description",
    "huge_heading",
    "huge_id",
    "max_locations_low",
    "max_locations_high",
    "max_locations_bool",
    "max_locations_str",
    "max_locations_float",
    "max_locations_null",
    "trucks_high",
    "trucks_bool",
    "trucks_str",
    "trucks_null",
    "cars_high",
    "cars_bool",
    "require_available_str",
    "require_available_int",
    "forbidden_too_many",
    "forbidden_blank",
    "forbidden_huge_id",
    "forbidden_not_a_list",
    "extra_candidates",
    "extra_variants",
    "scene_not_object",
    "scenes_not_a_list",
])
def test_plan_rejects_oversized_and_mistyped_requests(client, mocks, mutate):
    body = plan_request()
    huge = "D" * 5000
    if mutate == "empty_scenes":
        body["scenes"] = []
    elif mutate == "nine_scenes":
        body["scenes"] = [
            {"id": f"s{i}", "heading": "INT. ROOM", "description": "Office"} for i in range(9)
        ]
    elif mutate == "duplicate_ids":
        body["scenes"] = [
            {"id": "same", "heading": "INT. ROOM", "description": "Office"},
            {"id": "same", "heading": "INT. HALL", "description": "Corridor"},
        ]
    elif mutate == "duplicate_ids_after_strip":
        body["scenes"] = [
            {"id": " scene1 ", "heading": "INT. ROOM", "description": "Office"},
            {"id": "scene1", "heading": "INT. HALL", "description": "Corridor"},
        ]
    elif mutate == "blank_heading":
        body["scenes"][0]["heading"] = "   "
    elif mutate == "huge_description":
        body["scenes"][0]["description"] = huge
    elif mutate == "huge_heading":
        body["scenes"][0]["heading"] = "H" * 121
    elif mutate == "huge_id":
        body["scenes"][0]["id"] = "i" * 61
    elif mutate == "max_locations_low":
        body["max_locations"] = 0
    elif mutate == "max_locations_high":
        body["max_locations"] = 5
    elif mutate == "max_locations_bool":
        body["max_locations"] = True
    elif mutate == "max_locations_str":
        body["max_locations"] = "2"
    elif mutate == "max_locations_float":
        body["max_locations"] = 2.0
    elif mutate == "max_locations_null":
        body["max_locations"] = None
    elif mutate == "trucks_high":
        body["trucks"] = 21
    elif mutate == "trucks_bool":
        body["trucks"] = False
    elif mutate == "trucks_str":
        body["trucks"] = "1"
    elif mutate == "trucks_null":
        body["trucks"] = None
    elif mutate == "cars_high":
        body["cars"] = 201
    elif mutate == "cars_bool":
        body["cars"] = True
    elif mutate == "require_available_str":
        body["require_available"] = "false"
    elif mutate == "require_available_int":
        body["require_available"] = 1
    elif mutate == "forbidden_too_many":
        body["forbidden_property_ids"] = [f"p{i}" for i in range(25)]
    elif mutate == "forbidden_blank":
        body["forbidden_property_ids"] = ["  "]
    elif mutate == "forbidden_huge_id":
        body["forbidden_property_ids"] = ["p" * 65]
    elif mutate == "forbidden_not_a_list":
        body["forbidden_property_ids"] = "p1"
    elif mutate == "extra_candidates":
        body["candidates"] = [{"property_id": f"p{i}"} for i in range(30)]
    elif mutate == "extra_variants":
        body["variants"] = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    elif mutate == "scene_not_object":
        body["scenes"] = [1, "office"]
    elif mutate == "scenes_not_a_list":
        body["scenes"] = {"id": "scene1", "heading": "INT.", "description": "Office"}
    response = client.post("/api/production/plan", json=body)
    assert_client_error(response)
    if mutate == "huge_description":
        assert huge not in response.text
        assert len(response.text) < 2000


@pytest.mark.parametrize("payload,content_type", [
    ("{", "application/json"),
    ("", "application/json"),
    ("null", "application/json"),
    ("[]", "application/json"),
    ('"plan"', "application/json"),
    ("\xff", "application/json"),
    ("{]", "application/json"),
])
def test_plan_rejects_malformed_json(client, mocks, payload, content_type):
    response = client.post(
        "/api/production/plan",
        content=payload.encode("utf-8", errors="surrogateescape"),
        headers={"Content-Type": content_type},
    )
    assert_client_error(response)


def test_plan_rejects_nonfinite_numbers_without_a_traceback(client, mocks):
    body = brainstorm_request()
    raw = json.dumps(body).replace('"x0": 0.4', '"x0": NaN')
    response = client.post(
        "/api/production/brainstorm",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert_client_error(response)
    raw = json.dumps(body).replace('"duration_sec": 5', '"duration_sec": Infinity')
    response = client.post(
        "/api/production/brainstorm",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert_client_error(response)


def test_brainstorm_actor_limits_are_client_errors(client, mocks):
    cases = []
    too_many = brainstorm_request()
    actor = too_many["shot"]["actors"][0]
    too_many["shot"]["actors"] = [{**actor, "id": f"a{i}", "name": f"N{i}"} for i in range(4)]
    cases.append(too_many)
    duplicate = brainstorm_request()
    duplicate["shot"]["actors"] = [actor, dict(actor)]
    cases.append(duplicate)
    long_name = brainstorm_request()
    long_name["shot"]["actors"][0]["name"] = "N" * 41
    cases.append(long_name)
    long_id = brainstorm_request()
    long_id["shot"]["actors"][0]["id"] = "a" * 31
    cases.append(long_id)
    long_dialogue = brainstorm_request()
    long_dialogue["shot"]["dialogue"] = "x" * 801
    cases.append(long_dialogue)
    long_instruction = brainstorm_request()
    long_instruction["instruction"] = "y" * 2001
    cases.append(long_instruction)
    bad_pose = brainstorm_request()
    bad_pose["shot"]["actors"][0]["pose"] = "fly"
    cases.append(bad_pose)
    bad_scale = brainstorm_request()
    bad_scale["shot"]["actors"][0]["scale"] = True
    cases.append(bad_scale)
    actors_string = brainstorm_request()
    actors_string["shot"]["actors"] = "Ada"
    cases.append(actors_string)
    variants = brainstorm_request()
    variants["variants"] = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
    cases.append(variants)
    for body in cases:
        assert_client_error(client.post("/api/production/brainstorm", json=body))


def test_unknown_method_does_not_leak_a_stack(client, mocks):
    response = client.get("/api/production/plan")
    assert response.status_code == 405
    assert_no_leak(response.text)


# ---------------------------------------------------------------------------
# Data mode
# ---------------------------------------------------------------------------


def test_mock_flag_is_exactly_the_string_one():
    """Adapters and the index agree: only TYPECAST_USE_MOCKS=1 is mock mode."""
    script = r"""
import importlib, os
values = ["1", "0", "true", "yes", "TRUE", "on", "1 ", " 1", "", "01", "2"]
for val in values:
    os.environ["TYPECAST_USE_MOCKS"] = val
    import data.costar_tools as costar
    import data.vexcel_tools as vexcel
    import index.search as search
    importlib.reload(costar)
    importlib.reload(vexcel)
    importlib.reload(search)
    expect = val == "1"
    assert costar.USE_MOCKS is expect, (val, costar.USE_MOCKS)
    assert vexcel.USE_MOCKS is expect, (val, vexcel.USE_MOCKS)
    assert search.USE_MOCKS is expect, (val, search.USE_MOCKS)
    assert search._use_mocks_enabled() is expect, (val, search._use_mocks_enabled())
print("ok")
"""
    env = os.environ.copy()
    for key in SECRET_KEYS:
        env[key] = ""
    env["TYPECAST_USE_MOCKS"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-500:]
    assert completed.stdout.strip() == "ok"


def test_missing_live_index_is_a_sanitized_503(client, mocks, monkeypatch, tmp_path):
    from index import search

    monkeypatch.setenv("TYPECAST_USE_MOCKS", "0")
    monkeypatch.setenv("TYPECAST_INDEX_DIR", str(tmp_path))
    monkeypatch.setattr(search, "_ACTIVE_INDEX", None)
    response = client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 503, response.status_code
    assert response.json()["detail"] == "Shot retrieval index unavailable"
    assert_no_leak(response.text, str(tmp_path))
    assert "mock" not in response.text


def test_aligned_modes_label_mock_and_live(client, mocks, monkeypatch):
    response = client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 200, response.status_code
    assert response.json()["mode"] == "mock"

    monkeypatch.setattr(production, "get_active_index", lambda: SimpleNamespace(is_mock=False))
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", False)
    monkeypatch.setattr(production.vexcel_tools, "USE_MOCKS", False)
    monkeypatch.setattr(production, "search_shots", lambda **kwargs: [make_shot("p1")])
    monkeypatch.setattr(production, "ROOT", Path("/tmp/typecast-audit-missing-cache"))
    response = client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 200, response.status_code
    body = response.json()
    assert body["mode"] == "live"
    warnings = [item for item in scene_candidates(body)[0]["warnings"] if item["field"] == "property_id/model_id"]
    assert warnings and warnings[0]["status"] == "unknown"
    assert_no_leak(response.text)


def test_mismatched_source_flags_fail_closed(client, mocks, monkeypatch):
    monkeypatch.setattr(production.vexcel_tools, "USE_MOCKS", False)
    response = client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)
    assert_no_leak(response.text, "audit-sentinel-not-a-secret")


# ---------------------------------------------------------------------------
# Property/model join
# ---------------------------------------------------------------------------


def write_parquet(tmp_path, definition, rows):
    import duckdb

    path = tmp_path / "property_models.parquet"
    with duckdb.connect(":memory:") as connection:
        connection.execute(f"CREATE TABLE fixture ({definition})")
        if rows:
            placeholders = ",".join("?" for _ in rows[0])
            connection.executemany(f"INSERT INTO fixture VALUES ({placeholders})", rows)
        connection.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(path)])
    return path


def test_join_keeps_distinct_properties_and_rejects_partial_conflicts(tmp_path):
    reversed_columns = write_parquet(
        tmp_path, "model_id VARCHAR, property_id VARCHAR", [("m1", "p1"), ("m2", "p2")],
    )
    assert load_property_model_pairs(reversed_columns) == {("p1", "m1"), ("p2", "m2")}

    path = write_parquet(
        tmp_path,
        "property_id VARCHAR, model_id VARCHAR, note VARCHAR",
        [("p1", "m1", "ALPHA-ONLY"), ("p2", "m2", "BETA-ONLY"), ("p1", "m1", "ALPHA-ONLY")],
    )
    loaded = load_property_model_pairs(path)
    assert loaded == {("p1", "m1"), ("p2", "m2")}
    assert ("p1", "m2") not in loaded
    assert ("p2", "m1") not in loaded
    assert all("ALPHA" not in pair[0] and "BETA" not in pair[1] for pair in loaded)

    multi = write_parquet(
        tmp_path,
        "property_id VARCHAR, model_id VARCHAR",
        [("p1", "m1"), ("p1", "m2"), ("p10", "m2")],
    )
    assert load_property_model_pairs(multi) == {("p1", "m1"), ("p1", "m2"), ("p10", "m2")}

    padded = write_parquet(
        tmp_path, "property_id VARCHAR, model_id VARCHAR", [("  p1 ", " m1 "), ("p1", "m1")],
    )
    assert load_property_model_pairs(padded) == {("p1", "m1")}

    import duckdb
    mixed = tmp_path / "mixed.parquet"
    with duckdb.connect(":memory:") as connection:
        connection.execute("CREATE TABLE fixture (property_id INTEGER, model_id VARCHAR)")
        connection.execute("INSERT INTO fixture VALUES (1, 'm-int')")
        connection.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(mixed)])
    assert load_property_model_pairs(mixed) == {("1", "m-int")}
    text_ids = write_parquet(
        tmp_path, "property_id VARCHAR, model_id VARCHAR", [("001", "m-text"), ("1", "m-one")],
    )
    assert load_property_model_pairs(text_ids) == {("001", "m-text"), ("1", "m-one")}

    broken = write_parquet(
        tmp_path,
        "property_id VARCHAR, model_id VARCHAR",
        [("p1", "m1"), (None, "m2"), ("p2", "m3")],
    )
    assert load_property_model_pairs(broken) is None
    assert load_property_model_pairs(tmp_path / "missing.parquet") is None


def test_live_join_reports_match_conflict_and_unknown(client, mocks, monkeypatch):
    shots = {
        "matched": make_shot("p1", "m1"),
        "conflict": make_shot("p1", "m-other"),
        "missing": make_shot("p9", "m9"),
    }

    def search(**kwargs):
        return [shots[search.which]]

    search.which = "matched"
    monkeypatch.setattr(production, "get_active_index", lambda: SimpleNamespace(is_mock=False))
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", False)
    monkeypatch.setattr(production.vexcel_tools, "USE_MOCKS", False)
    monkeypatch.setattr(production, "search_shots", search)
    monkeypatch.setattr(
        production, "load_property_model_pairs",
        lambda path: {("p1", "m1"), ("p2", "m2")},
    )
    monkeypatch.setattr(production, "plan_logistics", lambda *args, **kwargs: Logistics(
        property_id=args[0], parking_status="unknown"))
    monkeypatch.setattr(production, "get_property", lambda property_id: {
        "property_id": property_id, "availability_status": "unknown",
    })

    expected = {"matched": "matched", "conflict": "conflict", "missing": "unknown"}
    for name, status in expected.items():
        search.which = name
        response = client.post("/api/production/plan", json=plan_request())
        assert response.status_code == 200, response.status_code
        candidate_row = scene_candidates(response.json())[0]
        warning = next(item for item in candidate_row["warnings"] if item["field"] == "property_id/model_id")
        assert warning["status"] == status
        assert warning["source"] == "costar"
        assert candidate_row["eligible"] is (status != "conflict")
        if status == "unknown":
            assert "join confirmed" not in warning["message"]


# ---------------------------------------------------------------------------
# Missing evidence stays unknown
# ---------------------------------------------------------------------------


def test_explicit_unknown_parking_and_availability_are_not_certified(client, mocks, monkeypatch):
    install_sources(
        monkeypatch,
        [make_shot("p1")],
        lambda property_id, trucks, cars: Logistics(
            property_id=property_id,
            truck_spaces=1,
            car_spaces=2,
            parking_status="unknown",
            estimated=False,
        ),
        lambda property_id: {"property_id": property_id, "available": True, "availability_status": None},
    )
    body = plan_request(trucks=20, cars=200, require_available=True)
    response = client.post("/api/production/plan", json=body)
    assert response.status_code == 200, response.status_code
    candidate_row = scene_candidates(response.json())[0]
    assert candidate_row["logistics"]["enough_parking"] is None
    assert candidate_row["logistics"]["truck_spaces"] == 1
    assert candidate_row["eligible"] is False
    assert assignments(response.json()) == []
    statuses = {item["field"]: item["status"] for item in candidate_row["warnings"]}
    assert statuses["parking_capacity"] == "unknown"
    assert statuses["availability"] == "unknown"


def test_omitted_costar_and_vexcel_fields_stay_null(client, mocks, monkeypatch):
    install_sources(
        monkeypatch,
        [make_shot("p1")],
        lambda property_id, trucks, cars: Logistics(property_id=property_id, estimated=False),
        lambda property_id: {"property_id": property_id},
    )
    response = client.post("/api/production/plan", json=plan_request(trucks=5, cars=10))
    assert response.status_code == 200, response.status_code
    candidate_row = scene_candidates(response.json())[0]
    logistics = candidate_row["logistics"]
    assert logistics["enough_parking"] is None
    assert logistics["truck_spaces"] is None
    assert logistics["car_spaces"] is None
    assert logistics["walk_m"] is None
    assert logistics["parking_status"] is None
    assert logistics["walk_status"] is None
    assert logistics["noise_status"] is None
    assert logistics["truck_spaces"] != 0
    assert candidate_row["property"].get("available") is not True
    assert candidate_row["property"].get("availability_status") != "available"
    assert candidate_row["property"].get("year_built") is None
    assert any(item["status"] == "unknown" and item["source"] == "vexcel" for item in candidate_row["warnings"])
    assert any(item["status"] == "unknown" and item["source"] == "costar" for item in candidate_row["warnings"])
    assert candidate_row["eligible"] is True


@pytest.mark.xfail(strict=True, reason="BUG: missing parking_status is treated as known, so enough_parking becomes a hard pass or fail and can drop the property")
def test_missing_parking_status_stays_unknown(client, mocks, monkeypatch):
    install_sources(
        monkeypatch,
        [make_shot("p1")],
        lambda property_id, trucks, cars: Logistics(
            property_id=property_id,
            truck_spaces=4,
            car_spaces=45,
            estimated=True,
        ),
        lambda property_id: {"property_id": property_id, "availability_status": "unknown"},
    )
    response = client.post("/api/production/plan", json=plan_request(trucks=20, cars=200))
    assert response.status_code == 200, response.status_code
    candidate_row = scene_candidates(response.json())[0]
    assert candidate_row["logistics"]["parking_status"] is None
    assert candidate_row["logistics"]["enough_parking"] is None
    assert candidate_row["eligible"] is True
    assert assignments(response.json())
    parking = [item for item in candidate_row["warnings"] if item["field"] == "parking_capacity"]
    assert parking and parking[0]["status"] == "unknown"


# ---------------------------------------------------------------------------
# Solver: rejection, independence, determinism
# ---------------------------------------------------------------------------


def test_forbidden_property_never_returns_and_plans_are_independent_and_deterministic():
    scenes = ["sc_1", "sc_2"]
    rows = [
        candidate("sc_1", "p_both", "sh_b1", 0.60),
        candidate("sc_2", "p_both", "sh_b2", 0.60),
        candidate("sc_1", "p1", "sh_1", 0.90),
        candidate("sc_2", "p2", "sh_2", 0.90),
        candidate("sc_1", "bad", "sh_bad", 0.99),
        candidate("sc_2", "bad", "sh_bad2", 0.99),
    ]
    snapshot = deepcopy(rows)
    first = solve_plans(scenes, rows, max_locations=2, forbidden_property_ids=["bad"])
    second = solve_plans(scenes, list(reversed(rows)), max_locations=2, forbidden_property_ids=["bad"])
    assert rows == snapshot
    assert first == second
    assert "bad" not in json.dumps(first)
    assert len(first["plans"]) >= 2
    left, right = first["plans"][0], first["plans"][1]
    assert left is not right
    assert left["assignments"] is not right["assignments"]
    assert left["property_ids"] is not right["property_ids"]
    assert not any(
        item is other
        for item in left["assignments"]
        for other in right["assignments"]
    )
    saved = deepcopy(right)
    left["property_ids"].append("mutated")
    left["assignments"].append({"scene_id": "extra"})
    left["assignments"][0]["score"] = -1
    left["uncovered_scene_ids"].append("extra")
    assert right == saved


def test_http_replan_drops_an_exact_forbidden_property(client, mocks, monkeypatch):
    install_sources(
        monkeypatch,
        [make_shot("keep", score=0.4), make_shot("drop", score=0.9)],
        lambda property_id, trucks, cars: Logistics(
            property_id=property_id, truck_spaces=10, car_spaces=40,
            parking_status="measured", estimated=False,
        ),
        lambda property_id: {
            "property_id": property_id, "available": True, "availability_status": "available",
        },
    )
    first = client.post("/api/production/plan", json=plan_request(max_locations=1))
    assert first.status_code == 200, first.status_code
    assert any(item["property_id"] == "drop" for item in assignments(first.json()))
    second = client.post("/api/production/plan", json=plan_request(
        max_locations=1, forbidden_property_ids=["drop"]))
    assert second.status_code == 200, second.status_code
    body = second.json()
    assert all(item["property_id"] != "drop" for item in assignments(body))
    assert "drop" not in body["pool_properties"]
    assert all(item["shot"]["property_id"] != "drop" for item in scene_candidates(body))


@pytest.mark.xfail(strict=True, reason="BUG: forbidden property ids are not stripped, so a rejected id with surrounding whitespace is planned again")
def test_replan_drops_property_id_with_surrounding_whitespace(client, mocks, monkeypatch):
    padded = " p1 "
    install_sources(
        monkeypatch,
        [make_shot(padded, score=0.9)],
        lambda property_id, trucks, cars: Logistics(
            property_id=property_id, truck_spaces=10, car_spaces=40,
            parking_status="measured", estimated=False,
        ),
        lambda property_id: {
            "property_id": property_id, "available": True, "availability_status": "available",
        },
    )
    first = client.post("/api/production/plan", json=plan_request())
    assert first.status_code == 200, first.status_code
    assert [item["property_id"] for item in assignments(first.json())] == [padded]
    second = client.post("/api/production/plan", json=plan_request(forbidden_property_ids=[padded]))
    assert second.status_code == 200, second.status_code
    body = second.json()
    assert assignments(body) == []
    assert padded not in body["pool_properties"]
    assert all(item["shot"]["property_id"] != padded for item in scene_candidates(body))


@pytest.mark.xfail(strict=True, reason="BUG: solver whitespace-padded forbidden ids still match and return that property")
def test_solver_strips_forbidden_property_ids():
    result = solve_plans(
        ["sc_1"],
        [candidate("sc_1", "p1", "sh", 0.5)],
        forbidden_property_ids=[" p1 "],
    )
    assert result["plans"][0]["property_ids"] == []
    assert result["plans"][0]["assignments"] == []


@pytest.mark.xfail(strict=True, reason="BUG: forbidden property ids count toward the 24-property cap before they are removed, so a replan raises instead of returning the remaining property")
def test_forbidden_ids_do_not_consume_the_property_cap():
    rows = [candidate("sc_1", f"p{i:02d}", f"s{i:02d}", 0.2) for i in range(24)]
    rows.append(candidate("sc_1", "allowed", "s-ok", 0.9))
    result = solve_plans(
        ["sc_1"],
        rows,
        max_locations=1,
        forbidden_property_ids=[f"p{i:02d}" for i in range(24)],
    )
    assert result["plans"][0]["property_ids"] == ["allowed"]
    assert result["plans"][0]["assignments"][0]["shot_id"] == "s-ok"


@pytest.mark.xfail(strict=True, reason="BUG: a blank property id from retrieval raises inside the solver and the plan route returns a plain-text 500")
@pytest.mark.parametrize("property_id", ["", "   "])
def test_blank_property_id_is_a_client_or_service_error(client, mocks, monkeypatch, property_id):
    install_sources(
        monkeypatch,
        [Shot(
            shot_id="shot-blank", property_id=property_id, model_id="model-blank",
            sweep_id="sweep", heading_deg=0.0, image_path="mocks/img/audit.jpg", score=0.5,
            room_area_m2=40.0, ceiling_m=3.0, depth_m=6.0,
        )],
        lambda *args, **kwargs: None,
    )
    response = client.post("/api/production/plan", json=plan_request())
    assert_no_leak(response.text)
    assert response.status_code != 500
    assert response.status_code in {400, 422, 503}
    assert "json" in response.headers.get("content-type", "")
    assert isinstance(response.json().get("detail"), (str, list))


# ---------------------------------------------------------------------------
# Retrieval score and proposals
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="BUG: mock retrieval coerces a missing shot score to 0.0, so an unknown similarity is ranked as a real zero")
def test_missing_shot_score_is_not_coerced_to_zero(client, mocks, monkeypatch):
    from index.search import ShotRetrievalIndex
    from index import search

    shot = Shot(
        shot_id="unscored",
        property_id="mock-p1",
        model_id="mock-m1",
        sweep_id="sw",
        heading_deg=10,
        image_path="mocks/img/mock-p1-s0.jpg",
        score=None,
        room_area_m2=50,
        ceiling_m=3,
        depth_m=5,
    )
    monkeypatch.setattr(search, "_ACTIVE_INDEX", ShotRetrievalIndex([shot], None, is_mock=True))
    response = client.post("/api/production/plan", json=plan_request())
    assert response.status_code == 200, response.status_code
    scores = [item["shot"]["score"] for item in scene_candidates(response.json())]
    assert 0 not in scores and 0.0 not in scores


def test_brainstorm_rejects_stale_ids_and_does_not_replay(client, mocks, monkeypatch):
    stale = brainstorm_request()
    stale["proposal_id"] = "proposal-old"
    stale["version"] = 1
    stale["shot"]["proposal_version"] = 4
    rejected = client.post("/api/production/brainstorm", json=stale)
    assert_client_error(rejected)

    calls = {"n": 0}

    class Provider:
        def configured(self):
            return True

        def structured(self, instructions, text, output_model, **kwargs):
            calls["n"] += 1
            return {
                "summary": f"Proposal {calls['n']}",
                "creative_note": "A different staging.",
                "shot": brainstorm_request()["shot"],
            }

    monkeypatch.setattr("agent.models.get_provider", lambda **kwargs: Provider())
    first = client.post("/api/production/brainstorm", json=brainstorm_request())
    second = client.post("/api/production/brainstorm", json=brainstorm_request())
    assert first.status_code == 200, first.status_code
    assert second.status_code == 200, second.status_code
    assert first.json()["summary"] == "Proposal 1"
    assert second.json()["summary"] == "Proposal 2"
    assert set(first.json()) == {"summary", "creative_note", "shot"}
    assert "proposal_id" not in first.json() and "version" not in first.json()
    invalid = {
        "summary": "Bad coordinates",
        "creative_note": "Should be rejected.",
        "shot": brainstorm_request()["shot"],
        "proposal_id": "stale",
    }
    invalid["shot"] = deepcopy(invalid["shot"])
    invalid["shot"]["actors"][0]["x0"] = 5

    class Invalid:
        def configured(self):
            return True

        def structured(self, *args, **kwargs):
            return invalid

    monkeypatch.setattr("agent.models.get_provider", lambda **kwargs: Invalid())
    response = client.post("/api/production/brainstorm", json=brainstorm_request())
    assert response.status_code in {422, 502}
    assert_no_leak(response.text, "stale")


@pytest.mark.xfail(strict=True, reason="BUG: a BrainstormProposal instance is returned without a second validation, so mutated coordinates and constructed proposals bypass the schema")
@pytest.mark.parametrize("kind", ["mutated", "constructed"])
def test_brainstorm_revalidates_provider_model_instances(client, mocks, monkeypatch, kind):
    shot = brainstorm_request()["shot"]
    if kind == "mutated":
        proposal = production.BrainstormProposal.model_validate({
            "summary": "Move Ada.",
            "creative_note": "Stronger silhouette.",
            "shot": shot,
        })
        proposal.shot.actors[0].x0 = 7
    else:
        proposal = production.BrainstormProposal.model_construct(
            summary="Bypass",
            creative_note="Unvalidated.",
            shot=production.RehearsalShot.model_construct(
                duration_sec=99,
                dialogue="x" * 900,
                actors=[production.ActorBlock.model_construct(
                    id="a", name="A", pose="fly", x0=5, y0=0, x1=0, y1=0, scale=9,
                )],
            ),
        )

    class Provider:
        def configured(self):
            return True

        def structured(self, *args, **kwargs):
            return proposal

    monkeypatch.setattr("agent.models.get_provider", lambda **kwargs: Provider())
    response = client.post("/api/production/brainstorm", json=brainstorm_request())
    assert_no_leak(response.text)
    assert response.status_code in {422, 502}


# ---------------------------------------------------------------------------
# Offline mock mode and disclosure
# ---------------------------------------------------------------------------


def test_mock_endpoints_make_no_network_or_model_calls(mocks, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network disabled")

    import socket
    import http.client
    import urllib.request
    import openai
    import anthropic

    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", boom)
    monkeypatch.setattr(http.client.HTTPSConnection, "connect", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(openai, "OpenAI", boom)
    monkeypatch.setattr(anthropic, "Anthropic", boom)
    monkeypatch.setenv("TYPECAST_LLM_MODEL", "")
    monkeypatch.setenv("TYPECAST_LLM_PROVIDER", "openai")
    try:
        import requests
    except ImportError:
        requests = None
    else:
        monkeypatch.setattr(requests.sessions.Session, "request", boom)

    from index.preview import app

    with TestClient(app, raise_server_exceptions=False) as mounted:
        for path in ("/director", "/director.js", "/director.css"):
            static = mounted.get(path)
            assert static.status_code == 200, path
            assert_no_leak(static.text)
            assert "audit-sentinel-not-a-secret" not in static.text
        plan = mounted.post("/api/production/plan", json=plan_request())
        assert plan.status_code == 200, plan.status_code
        body = plan.json()
        assert body["mode"] == "mock"
        assert_no_leak(plan.text, "audit-sentinel-not-a-secret")
        allowed_ids = {
            row["property_id"]
            for row in json.loads((ROOT / "mocks" / "property.json").read_text())
        }
        found = set()
        for candidate_row in scene_candidates(body):
            found.add(candidate_row["shot"]["property_id"])
            image_path = candidate_row["shot"]["image_path"]
            assert not os.path.isabs(image_path)
            assert not image_path.startswith("/")
            if candidate_row["property"] is not None:
                found.add(candidate_row["property"]["property_id"])
                assert candidate_row["property"]["address"].endswith("(FAKE)")
        assert found <= allowed_ids
        brain = mounted.post("/api/production/brainstorm", json=brainstorm_request())
        assert brain.status_code == 503, brain.status_code
        assert isinstance(brain.json()["detail"], str)
        assert_no_leak(brain.text, "audit-sentinel-not-a-secret")


def test_eight_scene_plan_stays_on_public_fixtures(client, mocks):
    scenes = [
        {"id": f"s{i}", "heading": f"INT. ROOM {i}", "description": f"Scene {i} office"}
        for i in range(1, 9)
    ]
    response = client.post("/api/production/plan", json=plan_request(scenes=scenes, max_locations=4))
    assert response.status_code == 200, response.status_code
    body = response.json()
    assert body["mode"] == "mock"
    assert [scene["id"] for scene in body["scenes"]] == [f"s{i}" for i in range(1, 9)]
    assert len(body["pool_properties"]) <= 24
    assert_no_leak(response.text, "audit-sentinel-not-a-secret")
