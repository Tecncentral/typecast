from fastapi.testclient import TestClient
from agent.app import app
from agent import pipeline

SCENE = "INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling. Parking for 3 trucks and 30 crew cars."
c = TestClient(app)


def test_scout_three_picks_cite_all_layers():
    r = c.post("/scout", json={"scene": SCENE}).json()
    assert len(r["picks"]) == 3 and [p["rank"] for p in r["picks"]] == [1, 2, 3]
    for p in r["picks"]:
        assert all(w in p["reason"] for w in ("CoStar", "Matterport", "Vexcel"))
        assert p["skeptic_notes"]
    assert {e["type"] for e in r["events"]} >= {"plan", "skeptic", "final"}


def test_refine_reuses_thread_and_changes_notes():
    r = c.post("/scout", json={"scene": SCENE}).json()
    r2 = c.post("/refine", json={"thread_id": r["thread_id"], "message": "need parking for 50 trucks"}).json()
    assert r2["thread_id"] == r["thread_id"]
    assert any("Parking short" in n for p in r2["picks"] for n in p["skeptic_notes"])


def test_lookalike_excludes_source_building():
    r = c.post("/scout", json={"example_shot_id": "mock-p1-s0"}).json()
    assert r["picks"] and all(p["property"]["property_id"] != "mock-p1" for p in r["picks"])


def test_bad_request_and_approve_needs_yes():
    assert c.post("/scout", json={}).status_code == 400
    assert c.post("/approve", json={"thread_id": "x", "pick_rank": 1, "decision": "no"}).json()["sent"] is False


def test_stream_sends_events_then_result(monkeypatch):
    monkeypatch.setenv("TYPECAST_EVENT_DELAY", "0")
    body = c.get("/scout/stream", params={"scene": SCENE}).text
    assert body.count("event: agent") >= 5 and body.strip().split("\n\n")[-1].startswith("event: result")
    assert c.get("/scout/stream").status_code == 400
