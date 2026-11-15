"""Focused offline unit tests for index/cinematic.py."""

from __future__ import annotations

import numpy as np
import pytest

from contracts.schemas import Shot
from index.cinematic import MAX_QUERY_BRIEF_CHARS, diverse_results, query_brief


def _shot(
    shot_id: str,
    *,
    property_id: str = "prop_1",
    model_id: str = "model_1",
    sweep_id: str = "sweep_1",
    score: float | None = 0.8,
) -> Shot:
    return Shot(
        shot_id=shot_id,
        model_id=model_id,
        sweep_id=sweep_id,
        heading_deg=0.0,
        image_path=f"images/{shot_id}.jpg",
        property_id=property_id,
        score=score,
    )


def test_mmr_tradeoff_promotes_diverse_view_over_near_duplicate() -> None:
    s1 = _shot("s1", property_id="p1", sweep_id="sw1", score=0.90)
    s2 = _shot("s2", property_id="p2", sweep_id="sw2", score=0.88)  # near-duplicate vector to s1
    s3 = _shot("s3", property_id="p3", sweep_id="sw3", score=0.82)  # orthogonal diverse vector
    vecs = {
        "s1": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "s2": np.array([0.99, 0.14106736, 0.0], dtype=np.float32),
        "s3": np.array([0.0, 1.0, 0.0], dtype=np.float32),
    }

    # With relevance_weight=0.5, diversity penalty pushes s3 ahead of near-duplicate s2
    diverse = diverse_results([s1, s2, s3], vecs, k=2, relevance_weight=0.5)
    assert [s.shot_id for s in diverse] == ["s1", "s3"]

    # With relevance_weight=1.0, pure cosine relevance keeps s2 second
    pure_rel = diverse_results([s1, s2, s3], vecs, k=2, relevance_weight=1.0)
    assert [s.shot_id for s in pure_rel] == ["s1", "s2"]


def test_hard_property_and_sweep_caps_may_return_fewer_than_k() -> None:
    shots = [
        _shot("a1", property_id="p1", model_id="m1", sweep_id="sw1", score=0.95),
        _shot("a2", property_id="p1", model_id="m1", sweep_id="sw1", score=0.94),  # blocked by max_per_sweep=1
        _shot("a3", property_id="p1", model_id="m1", sweep_id="sw2", score=0.93),
        _shot("a4", property_id="p1", model_id="m1", sweep_id="sw3", score=0.92),  # blocked by max_per_property=2
        _shot("b1", property_id="p2", model_id="m2", sweep_id="sw1", score=0.70),
    ]
    vecs = {
        "a1": np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32),
        "a2": np.array([0.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32),
        "a3": np.array([0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float32),
        "a4": np.array([0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float32),
        "b1": np.array([0.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32),
    }

    res = diverse_results(shots, vecs, k=5, max_per_property=2, max_per_sweep=1)
    assert [s.shot_id for s in res] == ["a1", "a3", "b1"]


def test_deterministic_tiebreak_no_mutation_and_mock_none_vectors() -> None:
    s_b = _shot("shot_b", property_id="p1", sweep_id="sw1", score=0.85)
    s_a = _shot("shot_a", property_id="p2", sweep_id="sw2", score=0.85)
    s_c = _shot("shot_c", property_id="p1", sweep_id="sw1", score=0.84)
    original = [s_b, s_a, s_c]
    snapshot = [(s.shot_id, s.score) for s in original]

    res = diverse_results(original, None, k=3, max_per_property=2, max_per_sweep=1)
    assert [s.shot_id for s in res] == ["shot_a", "shot_b"]
    assert [(s.shot_id, s.score) for s in original] == snapshot


def test_invalid_params_and_invalid_vectors_raise_value_error() -> None:
    s1 = _shot("s1", property_id="p1", sweep_id="sw1", score=0.9)
    s2 = _shot("s2", property_id="p2", sweep_id="sw2", score=0.8)
    good = np.array([1.0, 0.0], dtype=np.float32)

    with pytest.raises(ValueError):
        diverse_results([s1, s2], {"s1": good, "s2": np.array([0.0, 0.0], dtype=np.float32)})
    with pytest.raises(ValueError):
        diverse_results([s1, s2], {"s1": good, "s2": np.array([np.nan, 1.0], dtype=np.float32)})
    with pytest.raises(ValueError):
        diverse_results([s1, s2], {"s1": good})  # missing s2
    with pytest.raises(ValueError):
        diverse_results([s1, s2], {"s1": good, "s2": np.array([1.0, 0.0, 0.0], dtype=np.float32)})
    with pytest.raises(ValueError):
        diverse_results([s1], {"s1": good}, relevance_weight=1.5)
    with pytest.raises(ValueError):
        diverse_results([s1], {"s1": good}, max_per_property=0)
    with pytest.raises(ValueError):
        diverse_results([_shot("no_score", score=None)], None)


def test_query_brief_grounded_and_bounded() -> None:
    brief = query_brief(
        "  open industrial   loft  ",
        mood="quiet morning",
        lighting="diffused north window light",
        materials="brushed concrete, raw oak",
    )
    assert brief == (
        "open industrial loft; mood: quiet morning; "
        "lighting: diffused north window light; materials: brushed concrete, raw oak"
    )
    long_brief = query_brief("gallery hall " * 60, mood="calm")
    assert len(long_brief) <= MAX_QUERY_BRIEF_CHARS
    assert long_brief.endswith("...")
    with pytest.raises(ValueError):
        query_brief("   ")
