import pytest

from agent import pipeline
from agent.interfaces import Requirements, RunContext
from contracts.schemas import Event, Logistics, Property, Shot
from index.geometry import check_fit


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for name in ("TYPECAST_ENABLE_MODEL_PARSE", "TYPECAST_ENABLE_VISION_RERANK", "TYPECAST_ALLOW_VISION_UPLOAD"):
        monkeypatch.setenv(name, "0")
    for name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        monkeypatch.setenv(name, "false")
    for name in ("LLM_API_KEY", "VISION_API_KEY", "FALLBACK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(name, "")
    monkeypatch.setattr(pipeline.working_memory, "save", lambda *args: None)


def dataset(monkeypatch, rows):
    properties, shots, logistics = {}, [], {}
    counts = {"costar": 0, "shots": 0}
    for index, row in enumerate(rows):
        pid = row.get("pid", f"p{index}")
        properties[pid] = Property(property_id=pid, address=f"{pid} Test St", city="Los Angeles", lat=0, lon=0,
                                   type="Office", year_built=row.get("year", 1980),
                                   available=row.get("available", True), model_id=f"m-{pid}")
        shots.append(Shot(shot_id=f"s{index}", model_id=f"m-{pid}", sweep_id=f"sw{index}", heading_deg=0,
                          image_path="mocks/image.jpg", property_id=pid, depth_m=row.get("depth", 20),
                          ceiling_m=row.get("ceiling", 3), room_area_m2=row.get("area", 100),
                          measure_on_site=row.get("estimated", False), score=row.get("score", 1 - index * .1)))
        logistics[pid] = Logistics(property_id=pid, truck_spaces=row.get("trucks", 10), car_spaces=100,
                                   walk_m=row.get("walk", 30), estimated=row.get("aerial_estimated", True))
    by_shot = {shot.shot_id: shot for shot in shots}

    def costar(**kwargs):
        counts["costar"] += 1
        return list(properties.values())

    def views(**kwargs):
        counts["shots"] += 1
        return [shot for shot in shots if shot.property_id in kwargs.get("property_ids", properties)]

    def fit(shot_id, focal_mm, frame_width_m):
        shot = by_shot[shot_id]
        return check_fit(shot.depth_m, shot.ceiling_m, focal_mm, frame_width_m, shot.measure_on_site)

    monkeypatch.setattr(pipeline, "search_costar", costar)
    monkeypatch.setattr(pipeline, "search_shots", views)
    monkeypatch.setattr(pipeline, "get_property", properties.__getitem__)
    monkeypatch.setattr(pipeline, "get_shot", by_shot.__getitem__)
    monkeypatch.setattr(pipeline, "check_shot", fit)
    monkeypatch.setattr(pipeline, "plan_logistics", lambda pid, *args: logistics[pid])
    monkeypatch.setattr(pipeline.rerank, "rerank_shots", lambda ctx, req, shots, k=20: shots)
    return counts, shots


@pytest.mark.parametrize("missing", [{"depth": None}, {"ceiling": None}, {"depth": None, "ceiling": None}])
def test_unknown_geometry_never_crashes_or_claims_fit(monkeypatch, missing):
    dataset(monkeypatch, [missing])
    result = pipeline.scout(RunContext(thread_id="unknown-geometry"), Requirements(scene="Office"))
    assert len(result.picks) == 1
    pick = result.picks[0]
    assert pick.shot_fit.status == "unknown" and pick.shot_fit.fits is False
    assert "measure on site" in pick.shot_fit.note and "None" not in pick.reason
    assert pick.reason.startswith("Blocked alternative;")
    assert any(e.source == "matterport" and e.status == "unknown" for e in pick.evidence)
    assert any("Shot fit unknown" in note for note in pick.skeptic_notes)


def test_precomputed_logistics_is_used_without_source_requests(monkeypatch):
    _, shots = dataset(monkeypatch, [{"pid": "p-cache"}])
    cached = Logistics(property_id="p-cache", truck_spaces=0, car_spaces=0,
                       walk_m=500, estimated=True)
    monkeypatch.setattr(pipeline, "plan_logistics", lambda *args: pytest.fail("Duplicate logistics request"))
    candidates = pipeline._evaluate(RunContext("cached-logistics"), Requirements(trucks=3), shots,
                                    logistics={"p-cache": cached})
    assert len(candidates) == 1 and candidates[0].logi is cached
    assert candidates[0].blockers > 0


def test_missing_precomputed_logistics_is_an_error_without_hidden_fetch(monkeypatch):
    _, shots = dataset(monkeypatch, [{}])
    events = []
    monkeypatch.setattr(pipeline, "plan_logistics", lambda *args: pytest.fail("Hidden logistics request"))
    candidates = pipeline._evaluate(RunContext("missing-logistics", emit=events.append), Requirements(),
                                    shots, logistics={})
    assert candidates == []
    assert any(event.type == "error" for event in events)


def test_estimated_geometry_is_at_most_tight(monkeypatch):
    dataset(monkeypatch, [{"estimated": True}])
    result = pipeline.scout(RunContext(thread_id="estimated-geometry"), Requirements(scene="Office"))
    pick = result.picks[0]
    assert pick.shot_fit.status == "tight" and pick.shot_fit.fits is False
    assert "measure on site" in pick.shot_fit.note
    assert all(e.status == "estimated" for e in pick.evidence if e.source == "matterport")


def test_rounded_display_depth_does_not_admit_a_measured_failure(monkeypatch):
    from index.geometry import needed_depth_m
    exact = needed_depth_m(24, 6)
    dataset(monkeypatch, [{"depth": round(exact, 2)}])
    result = pipeline.scout(RunContext(thread_id="exact-depth"), Requirements(scene="Office"))
    assert result.picks == []
    assert any("rejected shot fit" in event.text for event in result.events)


def test_all_measured_shot_failures_return_fewer_picks_after_honest_relaxation(monkeypatch):
    dataset(monkeypatch, [{"depth": 1}, {"depth": 2}, {"depth": 3}])
    result = pipeline.scout(RunContext(thread_id="failed-fits"),
                            Requirements(scene="1980s office", year_max=1992, min_area_m2=150))
    assert result.picks == []
    assert result.gave_up == ["parking distance", "era", "minimum size"]
    relaxed = [e.text for e in result.events if e.type == "relaxed"]
    assert len(relaxed) == 3
    assert "parking distance" in relaxed[0] and "era" in relaxed[1] and "minimum room size" in relaxed[2]
    assert sum("rejected shot fit" in e.text for e in result.events) == 3
    assert "0 picks" in result.events[-1].text


def test_relaxation_uses_parking_distance_then_era_then_size(monkeypatch):
    dataset(monkeypatch, [{"walk": 220}, {"year": 2010}, {"area": 40}])
    result = pipeline.scout(RunContext(thread_id="relax-in-order"),
                            Requirements(scene="1980s office", year_max=1992, min_area_m2=80))
    assert len(result.picks) == 3
    assert result.gave_up == ["parking distance", "era", "minimum size"]
    assert "parking distance relaxed" in result.picks[0].reason
    assert any("220 m" in note and "relaxed" in note for note in result.picks[0].skeptic_notes)


def test_occupied_unknown_fit_and_parking_short_are_blocking_not_small_score_penalties(monkeypatch):
    dataset(monkeypatch, [{"available": False, "score": 1_000_000},
                          {"depth": None, "score": 1_000_000},
                          {"trucks": 0, "score": 1_000_000}, {"score": .01}])
    result = pipeline.scout(RunContext(thread_id="blocker-ranks"), Requirements(scene="Office", trucks=5))
    assert result.picks[0].property.property_id == "p3"
    assert not result.picks[0].reason.startswith("Blocked alternative;")
    assert all(p.reason.startswith("Blocked alternative;") for p in result.picks[1:])
    assert any("Parking short" in e.text for e in result.events)
    assert any("occupied" in e.text for e in result.events)
    assert any("Shot fit unknown" in e.text for e in result.events)
    assert "explicitly blocked alternatives" in result.events[-1].text


def test_each_evidence_layer_has_field_level_uncertainty(monkeypatch):
    dataset(monkeypatch, [{"year": None, "area": None, "walk": None}])
    result = pipeline.scout(RunContext(thread_id="evidence-status"), Requirements(scene="Office"))
    pick = result.picks[0]
    assert {e.source for e in pick.evidence} == {"costar", "matterport", "vexcel"}
    assert len(pick.evidence) == 11
    assert all(e.status in {"measured", "estimated", "unknown"} for e in pick.evidence)
    for field in ("Year built", "Room area", "Parking walk"):
        assert next(e for e in pick.evidence if e.claim.startswith(field)).status == "unknown"
    assert all(layer in pick.reason for layer in ("CoStar", "Matterport", "Vexcel"))


def test_selects_fitting_view_instead_of_discarding_property(monkeypatch):
    dataset(monkeypatch, [{"pid": "p0", "depth": 2, "score": .99},
                          {"pid": "p0", "depth": 20, "score": .5}])
    result = pipeline.scout(RunContext(thread_id="alternate-view"), Requirements(scene="Office"))
    assert result.picks[0].shots[0].shot_id == "s1" and result.picks[0].shot_fit.fits
    assert any("s0: rejected shot fit" in e.text for e in result.events)


def test_refine_cached_json_has_zero_search_calls_and_keeps_unmentioned_fields(monkeypatch):
    counts, _ = dataset(monkeypatch, [{"trucks": 1}, {"trucks": 6}])
    ctx = RunContext(thread_id="cached-json")
    pipeline.scout(ctx, Requirements(scene="Office", cars=20, year_max=1992))
    cached = pipeline._threads[ctx.thread_id]
    restored = {"requirements": cached["requirements"].model_dump(mode="json"),
                "candidates": [shot.model_dump(mode="json") for shot in cached["candidates"]]}
    assert counts == {"costar": 1, "shots": 1}
    result = pipeline.refine(ctx, restored, "need parking for 5 trucks")
    assert counts == {"costar": 1, "shots": 1}
    assert restored["requirements"].trucks == 5
    assert restored["requirements"].cars == 20 and restored["requirements"].year_max == 1992
    assert result.picks[0].property.property_id == "p1"
    assert any("Parking short" in note for pick in result.picks for note in pick.skeptic_notes)
    pipeline.refine(ctx, restored, "no trucks")
    assert restored["requirements"].trucks == 0
    assert counts == {"costar": 1, "shots": 1}


def test_events_are_emitted_in_order_during_tools_and_rerank(monkeypatch):
    dataset(monkeypatch, [{}])
    observed = []
    original_search = pipeline.search_shots

    def search_while_running(**kwargs):
        assert observed[0].type == "plan"
        assert any(e.agent == "search_costar" and e.type == "tool" for e in observed)
        assert not any(e.type == "final" for e in observed)
        return original_search(**kwargs)

    def rerank_while_running(ctx, req, shots, k):
        assert k == 20
        assert any(e.agent == "search_shots" and e.type == "tool" for e in observed)
        ctx.event(Event(type="fallback", agent="rerank", text="Vision skipped in test."))
        assert observed[-1].text == "Vision skipped in test."
        return shots

    monkeypatch.setattr(pipeline, "search_shots", search_while_running)
    monkeypatch.setattr(pipeline.rerank, "rerank_shots", rerank_while_running)
    result = pipeline.scout(RunContext(thread_id="live-events", emit=observed.append), Requirements(scene="Office"))
    assert observed == result.events and observed[-1].type == "final"
    assert all(e.engine == "fixed" for e in observed)
    assert [e.ts for e in observed] == sorted(e.ts for e in observed)
    assert any(e.agent == "rerank" and e.type == "fallback" for e in result.events)
    assert all(result.timings[name] >= 0 for name in ("search_costar", "search_shots", "check_shot", "plan_logistics", "rerank_shots"))


def test_parser_fallback_note_is_emitted_even_if_backup_model_succeeded(monkeypatch):
    dataset(monkeypatch, [{}])
    monkeypatch.setattr(pipeline, "parse_scene", lambda scene, **kwargs: Requirements(
        scene=scene, parsed_with_model=True, parse_note="Primary provider failed; backup parser succeeded."))
    result = pipeline.scout(scene="Office", thread_id="backup-parser")
    assert any(e.type == "fallback" and "backup parser succeeded" in e.text for e in result.events)


def test_minimum_area_chooses_large_enough_alternate_view(monkeypatch):
    dataset(monkeypatch, [{"pid": "p0", "area": 30, "score": .99},
                          {"pid": "p0", "area": 120, "score": .5}])
    result = pipeline.scout(RunContext(thread_id="alternate-area"), Requirements(scene="Office", min_area_m2=100))
    assert result.picks[0].shots[0].shot_id == "s1"
    assert "minimum size" in result.gave_up  # Still fewer than three viable properties.


def test_rerank_top_twenty_preserves_other_cached_views(monkeypatch):
    _, shots = dataset(monkeypatch, [{} for _ in range(25)])
    calls = []

    def rerank(ctx, req, candidates, k):
        calls.append(k)
        return list(reversed(candidates[:k]))

    monkeypatch.setattr(pipeline.rerank, "rerank_shots", rerank)
    ctx = RunContext(thread_id="rerank-cap")
    pipeline.scout(ctx, Requirements(scene="Office"))
    cached = pipeline._threads[ctx.thread_id]["candidates"]
    assert calls == [20]
    assert {shot.shot_id for shot in cached} == {shot.shot_id for shot in shots}
    assert len(cached) == 25


def test_live_unknown_availability_capacity_and_noise_are_visible(monkeypatch):
    dataset(monkeypatch, [{"pid": "live-unknown", "available": False, "trucks": None}])
    prop = pipeline.get_property("live-unknown").model_copy(update={
        "availability_status": "unknown", "availability_reason": "Listing status missing.",
        "parking_flags": {"hasNoParkingAvailable": False}})
    monkeypatch.setattr(pipeline, "get_property", lambda pid: prop)
    monkeypatch.setattr(pipeline, "search_costar", lambda **kwargs: [prop])
    logi = Logistics(property_id=prop.property_id, parking_status="unknown", noise_status="unknown")
    monkeypatch.setattr(pipeline, "plan_logistics", lambda *args: logi)
    result = pipeline.scout(RunContext(thread_id="live-unknown"), Requirements(scene="Office", trucks=3, cars=30))
    pick = result.picks[0]
    assert "occupied" not in pick.reason and "None" not in pick.reason
    assert "unknown truck and unknown car spaces" in pick.reason
    assert any("Parking capacity unknown" in note for note in pick.skeptic_notes)
    assert any("Availability is unknown" in note for note in pick.skeptic_notes)
    assert any(e.status == "unknown" and "Availability" in e.claim for e in pick.evidence)
    assert any(e.status == "unknown" and "Noise" in e.claim for e in pick.evidence)
    assert any(e.source == "costar" and e.status == "measured" and "parking flag" in e.claim for e in pick.evidence)


def test_zero_parking_requirement_does_not_require_known_capacity(monkeypatch):
    dataset(monkeypatch, [{"pid": "no-parking-required"}])
    logi = Logistics(property_id="no-parking-required", parking_status="unknown")
    monkeypatch.setattr(pipeline, "plan_logistics", lambda *args: logi)
    result = pipeline.scout(RunContext(thread_id="no-parking-required"),
                            Requirements(scene="Office", trucks=0, cars=0))
    assert not any("Parking capacity unknown" in n or "Parking short" in n for n in result.picks[0].skeptic_notes)


def test_live_market_pool_excludes_unindexed_properties_before_logistics(monkeypatch):
    from index import store
    _, shots = dataset(monkeypatch, [{"pid": "indexed"}, {"pid": "not-indexed"}])
    monkeypatch.setattr(store, "load_index", lambda: ([shots[0]], None, "synthetic"))
    pool = pipeline.market_properties(RunContext(thread_id="live-market", source_mode="live"), "Los Angeles")
    assert [p.property_id for p in pool] == ["indexed"]
