import os
for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "LANGSMITH_API_KEY"):
    os.environ[name] = ""
os.environ.update(TYPECAST_USE_MOCKS="1", TYPECAST_ENABLE_MODEL_PARSE="0", TYPECAST_ENABLE_VISION_RERANK="0", LANGSMITH_TRACING="false", TYPECAST_ENGINE="fixed")
import asyncio, json, threading
import pytest
from fastapi.testclient import TestClient
from agent.app import app, scout_stream
from agent import pipeline, state, runtime

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
    r = c.post("/scout", json={"scene": SCENE}).json()
    assert c.post("/approve", json={"thread_id": r["thread_id"], "pick_rank": 1, "decision": "no"}).json()["sent"] is False


def test_stream_sends_events_then_result(monkeypatch):
    body = c.get("/scout/stream", params={"scene": SCENE}).text
    assert body.count("event: agent") >= 5 and body.strip().split("\n\n")[-1].startswith("event: result")
    assert c.get("/scout/stream").status_code == 400


@pytest.fixture(autouse=True)
def private_state(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "CACHE_ROOT", tmp_path)
    state._memory.clear()
    state._expires.clear()
    yield
    state._memory.clear()
    state._expires.clear()


def test_unknown_expired_and_bad_rank():
    assert c.post("/refine", json={"thread_id": "unknown-thread", "message": "more cars"}).status_code == 404
    assert c.post("/approve", json={"thread_id": "unknown-thread", "pick_rank": 1, "decision": "yes"}).status_code == 404
    assert c.post("/approve", json={"thread_id": "../escape", "pick_rank": 1, "decision": "no"}).status_code == 422
    r = c.post("/scout", json={"scene": SCENE}).json()
    assert c.post("/approve", json={"thread_id": r["thread_id"], "pick_rank": 99, "decision": "yes"}).status_code == 422
    state._expires[r["thread_id"]] = 0
    assert c.post("/refine", json={"thread_id": r["thread_id"], "message": "more cars"}).status_code == 404


def test_stream_matches_regular_response_and_event_timestamps():
    regular = c.post("/scout", json={"scene": SCENE}).json()
    body = c.get("/scout/stream", params={"scene": SCENE}).text
    parts = body.strip().split("\n\n")
    first = json.loads(parts[0].splitlines()[1][6:])
    result = json.loads(parts[-1].splitlines()[1][6:])
    assert parts[0].startswith("event: agent") and parts[-1].startswith("event: result")
    assert result["picks"] == regular["picks"]
    assert first["ts"] < result["events"][-1]["ts"] < result["timings"]["total_ms"] / 1000


def test_event_arrives_while_tool_is_still_blocked(monkeypatch):
    release, completed = threading.Event(), threading.Event()
    original = pipeline.search_costar
    def slow(*args, **kwargs):
        assert release.wait(2)
        result = original(*args, **kwargs)
        completed.set()
        return result
    monkeypatch.setattr(pipeline, "search_costar", slow)
    async def consume():
        response = await scout_stream(scene=SCENE)
        iterator = response.body_iterator
        try:
            first = await asyncio.wait_for(anext(iterator), 1)
            assert first.startswith("event: agent") and not completed.is_set()
        finally:
            release.set()
        remaining = [part async for part in iterator]
        assert remaining[-1].startswith("event: result")
    asyncio.run(consume())


def test_tool_failure_is_a_sanitized_stream_error(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("private-token-provider-stack")
    monkeypatch.setattr(pipeline, "search_costar", fail)
    response = c.get("/scout/stream", params={"scene": SCENE})
    assert response.status_code == 200 and "event: error" in response.text
    assert "private-token" not in response.text
    regular = c.post("/scout", json={"scene": SCENE})
    assert regular.status_code == 502 and "private-token" not in regular.text


def test_approve_writes_a_local_draft(tmp_path):
    r = c.post("/scout", json={"scene": SCENE}).json()
    body = {"thread_id": r["thread_id"], "pick_rank": 1}
    no = c.post("/approve", json={**body, "decision": "no"}).json()
    assert no["status"] == "cancelled" and no["sent"] is False
    assert not (tmp_path / "outbox").exists()
    yes = c.post("/approve", json={**body, "decision": "yes"}).json()
    assert yes["status"] == "draft_saved" and yes["sent"] is False
    assert yes["path"] == f"cache/outbox/{r['thread_id']}-1.md"
    assert "No message has been sent" in (tmp_path / "outbox" / f"{r['thread_id']}-1.md").read_text()


def test_health_reports_adapter_modes_without_secret(monkeypatch):
    import data.vexcel_tools as adapter
    monkeypatch.setattr(adapter, "USE_MOCKS", False)
    monkeypatch.setenv("LANGSMITH_API_KEY", "private-health-key")
    response = c.get("/health")
    health = response.json()
    assert health["mocks"] is False and health["source_modes"]["vexcel"] == "live"
    assert health["langsmith_configured"] is True and "fixed" in health["engines_available"]
    assert "private-health-key" not in response.text


def test_private_cache_paths_are_not_served():
    for path in ("threads/safe-test/requirements.json", "outbox/safe-test-1.md", "join.parquet", "records.json"):
        assert c.get(f"/cache/{path}").status_code == 404


def test_viewer_modules_always_revalidate():
    response = c.get("/app/utils.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert "etag" in response.headers
