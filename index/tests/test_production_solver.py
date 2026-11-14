"""Offline unit tests for index/production_solver.py."""

from __future__ import annotations

import copy
from math import comb
import pytest

from index.production_solver import solve_plans


def _cand(scene_id: str, property_id: str, shot_id: str, score: float) -> dict:
    return {
        "scene_id": scene_id,
        "property_id": property_id,
        "shot_id": shot_id,
        "score": score,
    }


def test_shared_two_locations_beat_greedy_three_locations_and_preserve_inputs() -> None:
    scenes = ["sc_1", "sc_2", "sc_3"]
    # Greedy per-scene top picks are p1 (0.95), p2 (0.94), p3 (0.93) -> 3 locations.
    # Shared properties p_ab (covers sc_1, sc_2) + p_bc (covers sc_2, sc_3) cover all 3 in 2 locations.
    candidates = [
        _cand("sc_1", "p1", "sh_p1_1", 0.95),
        _cand("sc_2", "p2", "sh_p2_2", 0.94),
        _cand("sc_3", "p3", "sh_p3_3", 0.93),
        _cand("sc_1", "p_ab", "sh_ab_1", 0.85),
        _cand("sc_2", "p_ab", "sh_ab_2", 0.82),
        _cand("sc_2", "p_bc", "sh_bc_2", 0.86),
        _cand("sc_3", "p_bc", "sh_bc_3", 0.84),
    ]
    snapshot = copy.deepcopy(candidates)

    out = solve_plans(scenes, candidates, max_locations=3)
    assert candidates == snapshot
    assert out["optimal_within_pool"] is True
    assert out["evaluated_subsets"] == comb(5, 1) + comb(5, 2) + comb(5, 3)

    # Best 3-location plan uses greedy top-1 per scene; best 2-location plan uses [p1, p_bc].
    by_locs = {p["locations"]: p for p in out["plans"]}
    assert by_locs[3]["property_ids"] == ["p1", "p2", "p3"]
    assert by_locs[3]["company_moves"] == 2
    assert by_locs[3]["uncovered_scene_ids"] == []

    assert by_locs[2]["property_ids"] == ["p1", "p_bc"]
    assert by_locs[2]["company_moves"] == 1
    assert by_locs[2]["uncovered_scene_ids"] == []
    assert [a["shot_id"] for a in by_locs[2]["assignments"]] == ["sh_p1_1", "sh_bc_2", "sh_bc_3"]
    assert by_locs[2]["mean_similarity"] == pytest.approx((0.95 + 0.86 + 0.84) / 3.0)


def test_forbidden_location_replans_and_partial_coverage_reports_uncovered() -> None:
    scenes = ["sc_1", "sc_2", "sc_3"]
    candidates = [
        _cand("sc_1", "p_hub", "sh_hub_1", 0.90),
        _cand("sc_2", "p_hub", "sh_hub_2", 0.88),
        _cand("sc_1", "p_alt", "sh_alt_1", 0.75),
    ]

    out = solve_plans(scenes, candidates, max_locations=2, forbidden_property_ids=["p_hub"])
    assert len(out["plans"]) == 1
    plan = out["plans"][0]
    assert plan["property_ids"] == ["p_alt"]
    assert plan["locations"] == 1
    assert plan["company_moves"] == 0
    assert [a["scene_id"] for a in plan["assignments"]] == ["sc_1"]
    assert plan["uncovered_scene_ids"] == ["sc_2", "sc_3"]
    assert plan["mean_similarity"] == pytest.approx(0.75)


def test_deterministic_ties_and_candidate_order_invariance() -> None:
    scenes = ["sc_1", "sc_2"]
    cands_a = [
        _cand("sc_1", "prop_b", "shot_2", 0.80),
        _cand("sc_1", "prop_b", "shot_1", 0.80),  # duplicate (scene, prop) tie -> shot_1 wins
        _cand("sc_2", "prop_b", "shot_3", 0.80),
        _cand("sc_1", "prop_a", "shot_9", 0.80),
        _cand("sc_2", "prop_a", "shot_8", 0.80),
    ]
    cands_b = list(reversed(cands_a))

    res_a = solve_plans(scenes, cands_a, max_locations=2)
    res_b = solve_plans(scenes, cands_b, max_locations=2)
    assert res_a == res_b
    # prop_a beats prop_b on sorted property_ids tie-break; deduplicated across k=1,2 since k=2 cannot beat k=1.
    assert len(res_a["plans"]) == 1
    assert res_a["plans"][0]["property_ids"] == ["prop_a"]
    assert [a["shot_id"] for a in res_a["plans"][0]["assignments"]] == ["shot_9", "shot_8"]


def test_empty_candidates_and_subset_count_bound() -> None:
    empty_out = solve_plans(["sc_1", "sc_2"], [], max_locations=3)
    assert empty_out == {
        "plans": [
            {
                "property_ids": [],
                "assignments": [],
                "uncovered_scene_ids": ["sc_1", "sc_2"],
                "locations": 0,
                "company_moves": 0,
                "mean_similarity": None,
            }
        ],
        "evaluated_subsets": 0,
        "optimal_within_pool": True,
    }

    # Max 24 properties and max_locations=4 -> at most sum_{k=1..4} C(24, k) = 12,950 subsets.
    cands = [_cand("sc_1", f"p_{i:02d}", f"sh_{i:02d}", 0.5) for i in range(24)]
    bounded = solve_plans(["sc_1"], cands, max_locations=4)
    assert bounded["evaluated_subsets"] == sum(comb(24, k) for k in range(1, 5))


def test_validation_rejects_invalid_inputs_and_booleans() -> None:
    valid_cands = [_cand("sc_1", "p1", "sh1", 0.7)]

    with pytest.raises(ValueError):
        solve_plans([], valid_cands)
    with pytest.raises(ValueError):
        solve_plans(["sc_1", "sc_1"], valid_cands)
    with pytest.raises(ValueError):
        solve_plans([f"s_{i}" for i in range(9)], valid_cands)
    with pytest.raises(ValueError):
        solve_plans(["sc_1"], valid_cands, max_locations=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        solve_plans(["sc_1"], valid_cands, max_locations=5)
    with pytest.raises(ValueError):
        solve_plans(["sc_1"], [_cand("unknown_sc", "p1", "sh1", 0.5)])
    with pytest.raises(ValueError):
        solve_plans(["sc_1"], [_cand("sc_1", "p1", "sh1", True)])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        solve_plans(["sc_1"], [_cand("sc_1", "p1", "sh1", 1.2)])
    with pytest.raises(ValueError):
        solve_plans(["sc_1"], [_cand("sc_1", "p1", "", 0.5)])
