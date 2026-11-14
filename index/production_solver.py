"""Exact combinatorial production-feasibility planner over retrieval candidates."""

from __future__ import annotations

from itertools import combinations
import math
from typing import Any, Mapping, Sequence

MAX_SCENES = 8
MAX_PROPERTIES = 24
MIN_LOCATIONS = 1
MAX_LOCATIONS = 4


def _require_nonempty_str(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_int_in_range(value: Any, *, name: str, low: int, high: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not (low <= value <= high):
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _require_cosine_score(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Candidate score must be a finite numeric cosine value")
    score = float(value)
    if not math.isfinite(score) or not (-1.0 <= score <= 1.0):
        raise ValueError("Candidate score must be finite within [-1.0, 1.0]")
    return score


def _plan_sort_key(plan: Mapping[str, Any]) -> tuple[int, float, int, tuple[str, ...]]:
    covered = len(plan["assignments"])
    mean_sim = plan["mean_similarity"]
    rounded_mean = -float(mean_sim) if mean_sim is not None else float("inf")
    return (
        -covered,
        rounded_mean,
        int(plan["locations"]),
        tuple(plan["property_ids"]),
    )


def solve_plans(
    scene_ids: list[str],
    candidates: list[dict],
    max_locations: int = 3,
    forbidden_property_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Enumerate exact property subsets up to max_locations and rank Pareto-optimal plans."""
    if not isinstance(scene_ids, Sequence) or isinstance(scene_ids, (str, bytes)):
        raise ValueError("scene_ids must be a sequence of non-empty strings")
    if not (1 <= len(scene_ids) <= MAX_SCENES):
        raise ValueError(f"scene_ids must contain 1..{MAX_SCENES} scenes")

    ordered_scenes: list[str] = []
    seen_scenes: set[str] = set()
    for raw_sid in scene_ids:
        sid = _require_nonempty_str(raw_sid, name="scene_id")
        if sid in seen_scenes:
            raise ValueError(f"Duplicate scene_id: '{sid}'")
        seen_scenes.add(sid)
        ordered_scenes.append(sid)

    budget_cap = _require_int_in_range(
        max_locations, name="max_locations", low=MIN_LOCATIONS, high=MAX_LOCATIONS
    )

    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise ValueError("candidates must be a sequence of candidate dicts")

    forbidden: set[str] = set()
    if forbidden_property_ids is not None:
        if not isinstance(forbidden_property_ids, Sequence) or isinstance(
            forbidden_property_ids, (str, bytes)
        ):
            raise ValueError("forbidden_property_ids must be a sequence of strings or None")
        for raw_pid in forbidden_property_ids:
            forbidden.add(_require_nonempty_str(raw_pid, name="forbidden_property_id"))

    # Collapse repeated (scene_id, property_id) rows to best cosine score, tie-broken by shot_id ascending.
    best_pair_cand: dict[tuple[str, str], dict[str, Any]] = {}
    all_props: set[str] = set()
    for idx, item in enumerate(candidates):
        if not isinstance(item, Mapping):
            raise ValueError(f"candidates[{idx}] must be a mapping")
        sid = _require_nonempty_str(item.get("scene_id"), name=f"candidates[{idx}].scene_id")
        if sid not in seen_scenes:
            raise ValueError(f"Unknown scene_id '{sid}' in candidates[{idx}]")
        pid = _require_nonempty_str(item.get("property_id"), name=f"candidates[{idx}].property_id")
        shot_id = _require_nonempty_str(item.get("shot_id"), name=f"candidates[{idx}].shot_id")
        score = _require_cosine_score(item.get("score"))

        all_props.add(pid)
        if len(all_props) > MAX_PROPERTIES:
            raise ValueError(f"Candidate pool exceeds max {MAX_PROPERTIES} unique properties")

        if pid in forbidden:
            continue

        normalized = {
            "scene_id": sid,
            "property_id": pid,
            "shot_id": shot_id,
            "score": score,
        }
        pair_key = (sid, pid)
        prev = best_pair_cand.get(pair_key)
        if prev is None:
            best_pair_cand[pair_key] = normalized
        else:
            cand_rank = (-score, shot_id)
            prev_rank = (-prev["score"], prev["shot_id"])
            if cand_rank < prev_rank:
                best_pair_cand[pair_key] = normalized

    eligible_props = sorted({pid for (_, pid) in best_pair_cand})
    if not eligible_props:
        empty_plan = {
            "property_ids": [],
            "assignments": [],
            "uncovered_scene_ids": list(ordered_scenes),
            "locations": 0,
            "company_moves": 0,
            "mean_similarity": None,
        }
        return {
            "plans": [empty_plan],
            "evaluated_subsets": 0,
            "optimal_within_pool": True,
        }

    # Index candidates by property_id -> scene_id for fast subset evaluation.
    by_prop: dict[str, dict[str, dict[str, Any]]] = {pid: {} for pid in eligible_props}
    for (sid, pid), cand in best_pair_cand.items():
        by_prop[pid][sid] = cand

    max_k = min(budget_cap, len(eligible_props))
    evaluated_subsets = 0
    best_by_budget: list[dict[str, Any]] = []

    best_so_far = None
    for k in range(1, max_k + 1):
        best_for_k: dict[str, Any] | None = None
        for subset in combinations(eligible_props, k):
            evaluated_subsets += 1
            assignments: list[dict[str, Any]] = []
            uncovered: list[str] = []
            score_sum = 0.0

            for sid in ordered_scenes:
                chosen: dict[str, Any] | None = None
                chosen_key: tuple[float, str, str] | None = None
                for pid in subset:
                    cand = by_prop[pid].get(sid)
                    if cand is None:
                        continue
                    key = (-cand["score"], cand["shot_id"], pid)
                    if chosen_key is None or key < chosen_key:
                        chosen_key = key
                        chosen = cand
                if chosen is None:
                    uncovered.append(sid)
                else:
                    assignments.append(dict(chosen))
                    score_sum += chosen["score"]

            mean_sim = (score_sum / len(assignments)) if assignments else None
            used = sorted({a['property_id'] for a in assignments})
            plan = {
                "property_ids": used,
                "assignments": assignments,
                "uncovered_scene_ids": uncovered,
                "locations": len(used),
                "company_moves": max(0, len(used) - 1),
                "mean_similarity": mean_sim,
            }
            if best_for_k is None or _plan_sort_key(plan) < _plan_sort_key(best_for_k):
                best_for_k = plan

        if best_for_k is not None:
            if best_so_far is None or _plan_sort_key(best_for_k) < _plan_sort_key(best_so_far):
                best_so_far = best_for_k
            best_by_budget.append(best_so_far)

    # Deduplicate identical property sets across budgets, then order globally by Pareto priority.
    deduped: dict[tuple[str, ...], dict[str, Any]] = {}
    for plan in best_by_budget:
        pkey = tuple(plan["property_ids"])
        prev = deduped.get(pkey)
        if prev is None or _plan_sort_key(plan) < _plan_sort_key(prev):
            deduped[pkey] = plan

    final_plans = sorted(deduped.values(), key=_plan_sort_key)
    return {
        "plans": final_plans,
        "evaluated_subsets": evaluated_subsets,
        "optimal_within_pool": True,
    }
