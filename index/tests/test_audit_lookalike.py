"""(d) LookAlike (query_shot_id) never returns the source building."""
import pytest

from index.search import ShotNotFoundError
from index.tests._audit_helpers import make_index, shot

ROWS = [
    (shot("src", "p1", model_id="m1"), [1.0, 0.0, 0.0]),
    (shot("src-same-sweep", "p1", model_id="m1", sweep_id="sw-src", heading_deg=90), [1.0, 0.0, 0.0]),
    (shot("same-model-other-property", "p9", model_id="m1"), [1.0, 0.0, 0.0]),
    (shot("same-property-other-model", "p1", model_id="m7"), [1.0, 0.0, 0.0]),
    (shot("near", "p2", model_id="m2"), [0.9, 0.1, 0.0]),
    (shot("far", "p3", model_id="m3"), [0.0, 0.0, 1.0]),
]


def test_lookalike_excludes_source_model_and_property():
    got = [s.shot_id for s in make_index(ROWS).search_shots(query_shot_id="src")]
    assert got == ["near", "far"]


def test_property_filter_cannot_reintroduce_source_building():
    idx = make_index(ROWS)
    assert idx.search_shots(query_shot_id="src", property_ids=["p1", "p9"]) == []


def test_lookalike_reason_names_the_example():
    first = make_index(ROWS).search_shots(query_shot_id="src")[0]
    assert "src" in (first.reason or "")


def test_unknown_example_shot_is_keyerror_subclass():
    with pytest.raises(ShotNotFoundError) as info:
        make_index(ROWS).search_shots(query_shot_id="missing")
    assert isinstance(info.value, KeyError)


def test_mock_mode_lookalike_also_excludes_source(monkeypatch):
    from index import search
    search.configure_index(None)
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "1")
    try:
        source = search.get_shot("mock-p1-s0")
        got = search.search_shots(query_shot_id="mock-p1-s0")
        assert got and all(s.property_id != source.property_id and s.model_id != source.model_id
                           for s in got)
    finally:
        search.configure_index(None)
