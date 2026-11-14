"""(a) Query ordering on the real retrieval path with an injected fake encoder."""
import numpy as np
import pytest

from index.tests._audit_helpers import make_index, shot

ROWS = [
    (shot("a-brick", "p1"), [1.0, 0.0, 0.0]),
    (shot("b-glass", "p2"), [0.0, 1.0, 0.0]),
    (shot("c-wood", "p3"), [0.0, 0.0, 1.0]),
    (shot("d-mixed", "p4"), [0.7, 0.7, 0.0]),
    (shot("e-tie", "p5"), [1.0, 0.0, 0.0]),   # identical vector to a-brick
]


def _ids(results):
    return [s.shot_id for s in results]


def test_different_queries_give_different_top_results():
    idx = make_index(ROWS)
    brick = _ids(idx.search_shots(query_text="brick warehouse"))
    glass = _ids(idx.search_shots(query_text="glass office lobby"))
    wood = _ids(idx.search_shots(query_text="wood apartment kitchen"))
    assert brick[0] in {"a-brick", "e-tie"} and glass[0] == "b-glass" and wood[0] == "c-wood"
    assert len({tuple(brick), tuple(glass), tuple(wood)}) == 3


def test_ordering_is_deterministic_and_scores_descend():
    idx = make_index(ROWS)
    first = idx.search_shots(query_text="brick warehouse")
    for _ in range(5):
        assert _ids(idx.search_shots(query_text="brick warehouse")) == _ids(first)
    scores = [s.score for s in first]
    assert scores == sorted(scores, reverse=True)
    assert all(-1.0001 <= s <= 1.0001 for s in scores)


def test_exact_ties_break_by_shot_id_regardless_of_insertion_order():
    forward = make_index(ROWS)
    backward = make_index(list(reversed(ROWS)))
    q = "brick"
    assert _ids(forward.search_shots(query_text=q))[:2] == ["a-brick", "e-tie"]
    assert _ids(backward.search_shots(query_text=q))[:2] == ["a-brick", "e-tie"]


def test_property_filter_applies_before_top_k():
    idx = make_index(ROWS)
    got = idx.search_shots(query_text="brick", property_ids=["p3"], k=1)
    assert _ids(got) == ["c-wood"]
    assert idx.search_shots(query_text="brick", property_ids=[]) == []
    assert idx.search_shots(query_text="brick", property_ids=["no-such-property"]) == []


@pytest.mark.parametrize("k", [0, -1, -100])
def test_non_positive_k_returns_nothing_not_partial(k):
    assert make_index(ROWS).search_shots(query_text="brick", k=k) == []


@pytest.mark.parametrize("kwargs", [
    {}, {"query_text": "brick", "query_shot_id": "a-brick"}, {"query_text": "   "},
    {"query_text": "brick", "k": True}, {"query_text": "brick", "min_depth_m": float("nan")},
    {"query_text": "brick", "min_ceiling_m": -1.0},
], ids=["no-query", "both-queries", "blank-text", "bool-k", "nan-min", "negative-min"])
def test_invalid_requests_raise_value_error(kwargs):
    with pytest.raises(ValueError):
        make_index(ROWS).search_shots(**kwargs)


def test_results_are_copies_not_index_rows():
    idx = make_index(ROWS)
    got = idx.search_shots(query_text="brick")[0]
    got.property_id = "tampered"
    assert idx.get_shot(got.shot_id).property_id != "tampered"


def test_query_dimension_mismatch_is_clear_error():
    from index.search import IndexUnavailableError, ShotRetrievalIndex
    idx = ShotRetrievalIndex([r[0] for r in ROWS], np.array([r[1] for r in ROWS], dtype=np.float32),
                             text_encoder=lambda _t: np.ones(512, dtype=np.float32))
    with pytest.raises(IndexUnavailableError, match="dim"):
        idx.search_shots(query_text="brick")
