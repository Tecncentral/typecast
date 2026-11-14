"""Pure-function diversity re-ranking and grounded visual query brief composition."""

from __future__ import annotations

import math
from typing import Mapping, Sequence
import numpy as np

from contracts.schemas import Shot

MAX_QUERY_BRIEF_CHARS = 500


def _validate_unit_vector(raw: object, *, shot_id: str, expected_dim: int | None) -> np.ndarray:
    arr = np.asarray(raw, dtype=np.float32)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError(f"Invalid vector shape for shot '{shot_id}': {arr.shape}")
    if expected_dim is not None and arr.size != expected_dim:
        raise ValueError(f"Vector dimension mismatch for shot '{shot_id}': {arr.size} != {expected_dim}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"Non-finite vector values for shot '{shot_id}'")
    norm = float(np.linalg.norm(arr))
    if norm <= 0.0 or not math.isfinite(norm):
        raise ValueError(f"Zero-norm vector for shot '{shot_id}'")
    return (arr / norm).astype(np.float32)


def _base_score(shot: Shot) -> float:
    if shot.score is None:
        raise ValueError(f"Candidate shot '{shot.shot_id}' is missing cosine score")
    val = float(shot.score)
    if not math.isfinite(val):
        raise ValueError(f"Candidate shot '{shot.shot_id}' has non-finite score")
    return val


def diverse_results(
    shots: Sequence[Shot],
    vectors_by_id: Mapping[str, object] | None,
    k: int = 12,
    relevance_weight: float = 0.8,
    max_per_property: int = 2,
    max_per_sweep: int = 1,
) -> list[Shot]:
    """Greedily re-rank eligible shots via MMR under hard property and sweep caps."""
    if not isinstance(k, int) or isinstance(k, bool) or k < 0:
        raise ValueError("k must be a non-negative integer")
    if isinstance(relevance_weight, bool) or not math.isfinite(float(relevance_weight)) or not 0.0 <= float(relevance_weight) <= 1.0:
        raise ValueError("relevance_weight must be a finite float in [0.0, 1.0]")
    if not isinstance(max_per_property, int) or isinstance(max_per_property, bool) or max_per_property < 1:
        raise ValueError("max_per_property must be an integer >= 1")
    if not isinstance(max_per_sweep, int) or isinstance(max_per_sweep, bool) or max_per_sweep < 1:
        raise ValueError("max_per_sweep must be an integer >= 1")

    candidates = list(shots)
    seen_ids: set[str] = set()
    for shot in candidates:
        if shot.shot_id in seen_ids:
            raise ValueError(f"Duplicate shot_id in candidates: '{shot.shot_id}'")
        seen_ids.add(shot.shot_id)
        _base_score(shot)

    if k == 0 or not candidates:
        return []

    use_vectors = vectors_by_id is not None and len(vectors_by_id) > 0
    norm_vecs: dict[str, np.ndarray] = {}
    if use_vectors:
        expected_dim: int | None = None
        for shot in candidates:
            if shot.shot_id not in vectors_by_id:
                raise ValueError(f"Missing embedding vector for candidate shot '{shot.shot_id}'")
            vec = _validate_unit_vector(vectors_by_id[shot.shot_id], shot_id=shot.shot_id, expected_dim=expected_dim)
            expected_dim = vec.size
            norm_vecs[shot.shot_id] = vec

    lam = float(relevance_weight)
    remaining = list(range(len(candidates)))
    selected: list[Shot] = []
    selected_vecs: list[np.ndarray] = []
    prop_counts: dict[str, int] = {}
    sweep_counts: dict[tuple[str, str], int] = {}

    while remaining and len(selected) < k:
        eligible = [
            idx
            for idx in remaining
            if prop_counts.get(candidates[idx].property_id, 0) < max_per_property
            and sweep_counts.get((candidates[idx].model_id, candidates[idx].sweep_id), 0) < max_per_sweep
        ]
        if not eligible:
            break

        best_idx = eligible[0]
        best_key: tuple[float, str] | None = None
        for idx in eligible:
            cand = candidates[idx]
            rel = _base_score(cand)
            if use_vectors and selected_vecs:
                cvec = norm_vecs[cand.shot_id]
                max_sim = max(float(np.dot(cvec, svec)) for svec in selected_vecs)
                mmr = lam * rel - (1.0 - lam) * max_sim
            else:
                mmr = rel
            key = (-round(mmr, 7), cand.shot_id)
            if best_key is None or key < best_key:
                best_key = key
                best_idx = idx

        chosen = candidates[best_idx]
        remaining.remove(best_idx)
        selected.append(chosen)
        if use_vectors:
            selected_vecs.append(norm_vecs[chosen.shot_id])
        prop_counts[chosen.property_id] = prop_counts.get(chosen.property_id, 0) + 1
        sweep_key = (chosen.model_id, chosen.sweep_id)
        sweep_counts[sweep_key] = sweep_counts.get(sweep_key, 0) + 1

    return selected


def query_brief(
    scene: str,
    mood: str = "",
    lighting: str = "",
    materials: str = "",
) -> str:
    """Compose a concise grounded visual search brief from caller-supplied fields."""
    if not isinstance(scene, str) or not " ".join(scene.split()):
        raise ValueError("scene must be a non-empty string")
    for name, val in (("mood", mood), ("lighting", lighting), ("materials", materials)):
        if not isinstance(val, str):
            raise ValueError(f"{name} must be a string")

    parts: list[str] = [" ".join(scene.split())]
    for label, raw in (("mood", mood), ("lighting", lighting), ("materials", materials)):
        cleaned = " ".join(raw.split())
        if cleaned:
            parts.append(f"{label}: {cleaned}")

    brief = "; ".join(parts)
    if len(brief) <= MAX_QUERY_BRIEF_CHARS:
        return brief
    clipped = brief[: MAX_QUERY_BRIEF_CHARS - 3].rstrip(" ;,:")
    return f"{clipped}..."
