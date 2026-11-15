import pytest

from agent import pipeline
from agent.interfaces import Requirements, RunContext
from data import costar_tools, vexcel_tools
from index import search

SCENE = "INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling. Parking for 3 trucks and 30 crew cars."


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for name in ("TYPECAST_ENABLE_MODEL_PARSE", "TYPECAST_ENABLE_VISION_RERANK", "TYPECAST_ALLOW_VISION_UPLOAD"):
        monkeypatch.setenv(name, "0")
    for name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        monkeypatch.setenv(name, "false")
    for name in ("LLM_API_KEY", "VISION_API_KEY", "FALLBACK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(name, "")
    for module in (costar_tools, vexcel_tools, search):
        monkeypatch.setattr(module, "USE_MOCKS", True)
    monkeypatch.setattr(pipeline.working_memory, "save", lambda *args: None)


def test_parse():
    req = pipeline.parse_scene(SCENE)
    assert req.trucks == 3 and req.cars == 30 and req.year_max == 1992
    assert {"trucks", "cars", "year_max"} <= req.explicit_fields


def test_scout_preserves_legacy_scene_entrypoint_and_evidence():
    response = pipeline.scout(scene=SCENE, thread_id="legacy-scout")
    assert response.thread_id == "legacy-scout" and response.engine == "fixed"
    assert response.picks
    for pick in response.picks:
        assert {e.source for e in pick.evidence} == {"costar", "matterport", "vexcel"}
        assert all(layer in pick.reason for layer in ("CoStar", "Matterport", "Vexcel"))
        assert pick.skeptic_notes
    assert "search_shots" in response.timings and "rerank_shots" in response.timings


def test_refine_five_trucks_demotes_short_parking_without_new_search(monkeypatch):
    ctx = RunContext(thread_id="refine-five")
    initial = pipeline.scout(ctx, Requirements(scene="Office space"))
    original_rank = [pick.property.property_id for pick in initial.picks]

    def unexpected_search(*args, **kwargs):
        pytest.fail("refine must only re-rank cached candidates")

    monkeypatch.setattr(pipeline, "search_costar", unexpected_search)
    monkeypatch.setattr(pipeline, "search_shots", unexpected_search)
    response = pipeline.refine(ctx, pipeline._threads[ctx.thread_id], "need parking for 5 trucks")
    assert pipeline._threads[ctx.thread_id]["requirements"].trucks == 5
    assert response.picks[0].property.property_id == "mock-p3"
    assert original_rank != [pick.property.property_id for pick in response.picks]
    assert any("Parking short" in note for pick in response.picks for note in pick.skeptic_notes)
    assert all(pick.reason.startswith("Blocked alternative;") for pick in response.picks[1:])


def test_no_trucks_is_an_explicit_zero_and_preserves_other_constraints():
    ctx = RunContext(thread_id="zero-trucks")
    req = Requirements(scene="Office", trucks=5, cars=20, year_max=1992, min_area_m2=90,
                       focal_mm=35, frame_width_m=4, explicit_fields={"trucks", "cars", "year_max"})
    pipeline.scout(ctx, req)
    pipeline.refine(ctx, pipeline._threads[ctx.thread_id], "no trucks")
    updated = pipeline._threads[ctx.thread_id]["requirements"]
    assert updated.trucks == 0
    assert (updated.cars, updated.year_max, updated.min_area_m2) == (20, 1992, 90)
    assert (updated.focal_mm, updated.frame_width_m, updated.city) == (35, 4, req.city)


def test_parser_entrypoint_delegates_to_parser_module(monkeypatch):
    expected = Requirements(scene="scene", trucks=0, explicit_fields={"trucks"})
    monkeypatch.setattr(pipeline.parse, "parse_scene", lambda scene: expected)
    assert pipeline.parse_scene("scene") is expected
