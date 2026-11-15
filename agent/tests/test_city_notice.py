"""Search-scope notices report the existing city choice without changing it."""
import json

from fastapi.testclient import TestClient
import pytest

from agent.eval.harness import mock_app
from agent import pipeline, runtime, state


@pytest.mark.parametrize("engine", ["fixed", "deep"])
@pytest.mark.parametrize("scene,city,notice", [
    ("INT. OFFICE, DAY. Windows and neutral walls.", "Los Angeles", True),
    ("INT. HOUSTON OFFICE, DAY. Windows.", "Houston", False),
    ("INT. LOS ANGELES OFFICE, DAY. Windows.", "Los Angeles", False),
])
def test_scope_notice_and_city_filter_for_both_engines(monkeypatch, engine, scene, city, notice):
    with mock_app() as app:
        monkeypatch.setenv("TYPECAST_ENGINE", engine)
        searched = []
        original = pipeline.market_properties

        def market(ctx, selected_city):
            searched.append(selected_city)
            return original(ctx, selected_city)

        def fake_deep(ctx, req):
            result = pipeline.scout(ctx, req)
            ctx.engine = "deep"
            result.engine = "deep"
            return result

        monkeypatch.setattr(pipeline, "market_properties", market)
        monkeypatch.setattr(runtime.deep, "run_deep", fake_deep)
        with TestClient(app) as client:
            response = client.post("/scout", json={"scene": scene})
        assert response.status_code == 200
        body = response.json()
        assert searched == [city]
        assert state.load(body["thread_id"], "requirements").city == city
        assert body["notes"] == ([runtime.DEFAULT_CITY_NOTE] if notice else [])
        notices = [event for event in body["events"] if event["type"] == "notice"]
        assert len(notices) == int(notice)
        if notice:
            assert notices[0]["text"] == runtime.DEFAULT_CITY_NOTE


def test_streamed_notice_and_refinement_keep_original_scope(monkeypatch):
    with mock_app() as app, TestClient(app) as client:
        text = client.get("/scout/stream", params={"scene": "INT. OFFICE, DAY."}).text
        blocks = text.strip().split("\n\n")
        body = json.loads(blocks[-1].split("data: ", 1)[1])
        assert body["notes"] == [runtime.DEFAULT_CITY_NOTE]
        assert any(json.loads(block.split("data: ", 1)[1])["type"] == "notice"
                   for block in blocks[:-1] if block.startswith("event: agent\n"))
        monkeypatch.setattr(pipeline, "search_shots", lambda **kw: pytest.fail("Refine searched again"))
        refined = client.post("/refine", json={"thread_id": body["thread_id"], "message": "Need 5 trucks"})
        assert refined.status_code == 200
        assert refined.json()["notes"] == body["notes"]


def test_example_query_and_its_refinement_do_not_claim_city_default():
    with mock_app() as app, TestClient(app) as client:
        body = client.post("/scout", json={"example_shot_id": "mock-p1-s0"}).json()
        assert body["notes"] == []
        result = client.post("/refine", json={"thread_id": body["thread_id"], "message": "Need 5 trucks"})
        assert result.status_code == 200 and result.json()["notes"] == []
