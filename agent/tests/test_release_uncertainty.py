"""Release regressions: source uncertainty survives joining, ranking and evidence."""
import pytest

from agent import pipeline
from agent.interfaces import Requirements, RunContext
from contracts.schemas import Logistics, Property, Shot
from index.geometry import check_fit


def candidate(monkeypatch, *, status="available", available=True, estimated=False,
              depth=20, ceiling=3):
    prop = Property(property_id="p", address="Test building", city="Los Angeles",
                    lat=0, lon=0, type="Office", available=available,
                    availability_status=status)
    shot = Shot(shot_id="s", property_id="p", model_id="m", sweep_id="sw",
                heading_deg=0, image_path="mocks/s.jpg", depth_m=depth,
                ceiling_m=ceiling, room_area_m2=100, measure_on_site=estimated,
                score=0.99)
    logi = Logistics(property_id="p", truck_spaces=10, car_spaces=100, walk_m=10)
    # Deliberately optimistic about provenance: the pipeline must enforce the
    # Shot's estimated marker even when an adapter evaluates it as measured.
    monkeypatch.setattr(pipeline, "check_shot", lambda sid, focal, width:
                        check_fit(depth, ceiling, focal, width, measure_on_site=False))
    req = Requirements(scene="Office", min_ceiling_m=2.7)
    ctx = RunContext(thread_id="release-uncertainty")
    candidates = pipeline._evaluate(ctx, req, [shot], {"p": prop}, logistics={"p": logi})
    picks, viable = pipeline._select(req, candidates, [])
    return candidates, picks, viable


@pytest.mark.parametrize("available", [False, True])
@pytest.mark.parametrize("status", [None, "unknown", "available", "not_available"])
def test_availability_status_governs_rank_reason_and_evidence(monkeypatch, status, available):
    candidates, picks, viable = candidate(monkeypatch, status=status, available=available)
    assert len(picks) == 1
    pick = picks[0]
    evidence = next(e for e in pick.evidence if e.claim.startswith("Availability:"))
    assert "occupied" not in pick.reason
    if status in (None, "unknown"):
        assert viable == 0 and candidates[0].blockers == 1
        assert pick.reason.startswith("Blocked alternative;")
        assert any("Availability is unknown" in note for note in pick.skeptic_notes)
        assert evidence.status == "unknown" and "Availability: unknown" in evidence.claim
    elif status == "not_available":
        assert viable == 0
        assert "not listed as available" in pick.reason
        assert evidence.status == "measured"
    else:
        assert viable == 1 and candidates[0].blockers == 0
        assert not pick.reason.startswith("Blocked alternative;")
        assert not any("Availability" in note for note in pick.skeptic_notes)
        assert evidence.status == "measured" and "Availability: available" in evidence.claim


@pytest.mark.parametrize("depth,ceiling", [(2, 3), (20, 1), (20, 3)])
def test_estimates_remain_unknown_and_are_not_rejected_as_measured_failures(monkeypatch, depth, ceiling):
    candidates, picks, viable = candidate(monkeypatch, estimated=True, depth=depth, ceiling=ceiling)
    assert len(picks) == 1 and not candidates[0].failed
    assert viable == 0
    pick = picks[0]
    assert pick.shot_fit.status == "unknown" and not pick.shot_fit.fits
    assert "fit unverified" in pick.shot_fit.note
    assert "shot fit unknown" in pick.reason
    assert any("Shot fit unknown" in note for note in pick.skeptic_notes)
    fit_evidence = next(e for e in pick.evidence if e.claim.startswith("Shot fit:"))
    assert fit_evidence.status == "unknown"
    dimension_evidence = [e for e in pick.evidence if e.claim.startswith(("Room area:", "Ceiling:", "Room depth:"))]
    assert all(e.status == "estimated" for e in dimension_evidence)


@pytest.mark.parametrize("depth,ceiling", [(2, 3), (20, 1)])
def test_known_measured_failures_still_exclude_views(monkeypatch, depth, ceiling):
    candidates, picks, viable = candidate(monkeypatch, depth=depth, ceiling=ceiling)
    assert candidates[0].failed
    assert picks == [] and viable == 0
