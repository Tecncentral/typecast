"""(c) Dimension policy.

Design intent (Owner 1, Nov 14):
* DIRECT invalid physical inputs to geometry (check_fit called with 0, negative,
  NaN, inf or bool) are programming errors and must raise ValueError.
* MALFORMED PROVIDER/CATALOG dimensions (Matterport rooms payload, import
  manifest rows, index catalog rows with 0, missing, NaN, negative, strings)
  must NORMALIZE to None/unknown before reaching geometry, never crash.
"""
import json
import math

import numpy as np
import pytest

from index.tests._audit_helpers import fake_text_encoder, jpeg_bytes, make_index, shot, write_generation

def _fit(**dims):
    return make_index([(shot("s", "p1", **dims), [1.0, 0.0, 0.0])]).check_shot("s")


def _assert_unknown(fit):
    assert fit.fits is False and fit.status == "unknown"


# ---- unknown geometry from a valid provider -------------------------------------

def test_importer_style_all_unknown_geometry_is_unknown():
    fit = _fit(depth_m=None, ceiling_m=None, room_area_m2=None, measure_on_site=True)
    _assert_unknown(fit)
    assert fit.have_depth_m is None and "measure on site" in fit.note.lower()


def test_unknown_ceiling_with_ample_depth_is_never_verified():
    _assert_unknown(_fit(depth_m=30.0, ceiling_m=None))


def test_room_enriched_estimate_is_unknown_not_fits():
    # Matches index/rooms.py output: area and ceiling estimated, depth None, measure_on_site.
    _assert_unknown(_fit(depth_m=None, ceiling_m=2.9, room_area_m2=41.0, measure_on_site=True))
    _assert_unknown(_fit(depth_m=30.0, ceiling_m=3.5, measure_on_site=True))


def test_measured_short_room_does_not_fit():
    fit = _fit(depth_m=5.0, ceiling_m=3.0)
    assert fit.fits is False and fit.status == "tight"


# ---- DIRECT invalid physical inputs: reject ---------------------------------------
# Covered by the owner's index/tests/test_geometry_evidence.py::test_reject_invalid_physical_inputs
# (True, False, 0, -1, nan, inf x 4 fields) since 9a6fea1; the audit duplicates were removed.

# ---- MALFORMED PROVIDER/CATALOG dimensions: normalize -----------------------------

PROVIDER_BAD = [0, -2.5, "nan", "3.1m", "", True, None, [], {"v": 3}]
PROVIDER_IDS = ["zero", "negative", "nan-string", "unit-string", "empty", "bool", "missing", "list", "object"]


@pytest.mark.parametrize("bad", PROVIDER_BAD, ids=PROVIDER_IDS)
def test_rooms_payload_dimensions_normalize_to_none(bad):
    from index.rooms import parse_rooms_model
    payload = {"data": {"model": {
        "floors": [{"id": "f1", "vertices": [
            {"id": "a", "position": {"x": 0, "y": 0}}, {"id": "b", "position": {"x": 4, "y": 0}},
            {"id": "c", "position": {"x": 4, "y": 4}}, {"id": "d", "position": {"x": 0, "y": 4}}],
            "edges": [{"id": e, "vertices": [{"id": u}, {"id": v}]}
                      for e, u, v in [("e1", "a", "b"), ("e2", "b", "c"), ("e3", "c", "d"), ("e4", "d", "a")]]}],
        "rooms": [{"id": "r1", "floor": {"id": "f1"}, "classifications": [],
                   "boundary": {"edges": [{"id": "e1"}, {"id": "e2"}, {"id": "e3"}, {"id": "e4"}]},
                   "dimensions": {"areaFloor": bad, "height": bad}}]}}}
    _floors, rooms, _warnings = parse_rooms_model(payload)
    assert len(rooms) == 1
    assert rooms[0].room_area_m2 is None and rooms[0].ceiling_m is None


BUILD_BAD = [0, -2.5, float("nan"), float("inf"), "abc", "", True, [], {"v": 3}]
BUILD_IDS = ["zero", "negative", "nan", "inf", "string", "empty", "bool", "list", "object"]


@pytest.mark.parametrize("bad", BUILD_BAD, ids=BUILD_IDS)
def test_build_manifest_dimensions_normalize_to_unknown(tmp_path, monkeypatch, bad):
    """Regression (fixed in 9a6fea1, index/build.py _dimension)."""
    from index import build
    monkeypatch.setattr(build, "ROOT", tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "f.jpg").write_bytes(jpeg_bytes())
    rec = dict(property_id="p1", model_id="m1", sweep_id="s1", image_path="cache/f.jpg",
               format="perspective", heading_deg=0.0, room_area_m2=bad, ceiling_m=bad,
               depth_m=bad, measure_on_site=False)
    (cache / "src.json").write_text(json.dumps({"records": [rec]}))
    shots = build.prepare("cache/src.json")
    assert shots[0].ceiling_m is None and shots[0].depth_m is None and shots[0].room_area_m2 is None
    # A discarded provider value must force on-site measurement even if the row said otherwise.
    assert shots[0].measure_on_site is True
    idx = make_index([(shots[0], [1.0, 0.0, 0.0])])
    _assert_unknown(idx.check_shot(shots[0].shot_id))


def test_build_keeps_valid_numeric_strings_and_numbers(tmp_path, monkeypatch):
    from index import build
    monkeypatch.setattr(build, "ROOT", tmp_path)
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache/f.jpg").write_bytes(jpeg_bytes())
    rec = dict(property_id="p1", model_id="m1", sweep_id="s1", image_path="cache/f.jpg",
               format="perspective", heading_deg=0.0, room_area_m2="41.5", ceiling_m=3.2,
               depth_m=12, measure_on_site=False)
    (tmp_path / "cache/src.json").write_text(json.dumps({"records": [rec]}))
    s = build.prepare("cache/src.json")[0]
    assert (s.room_area_m2, s.ceiling_m, s.depth_m, s.measure_on_site) == (41.5, 3.2, 12.0, False)


CATALOG_BAD = {"zero-depth": {"depth_m": 0.0}, "zero-ceiling": {"ceiling_m": 0.0},
               "nan-depth": {"depth_m": math.nan}, "inf-ceiling": {"ceiling_m": math.inf},
               "negative-depth": {"depth_m": -2.0}, "zero-area": {"room_area_m2": 0.0}}


def _load_catalog(tmp_path, shots_text):
    from index.search import ShotRetrievalIndex
    gen = write_generation(tmp_path / "gen", [shot("s", "p1")],
                           np.array([[1.0, 0.0, 0.0]], dtype=np.float32), shots_text=shots_text)
    return ShotRetrievalIndex.from_cache_dir(gen, text_encoder=fake_text_encoder)


@pytest.mark.parametrize("dims", list(CATALOG_BAD.values()), ids=list(CATALOG_BAD))
def test_catalog_row_dimensions_degrade_to_unknown(tmp_path, dims):
    """Regression (fixed in 9a6fea1, index/search.py _load_shots_file): an on-disk
    shots.json row with 0/negative/NaN/inf is normalized to None at load."""
    row = shot("s", "p1", depth_m=12.0, ceiling_m=3.5, room_area_m2=40.0, measure_on_site=False).model_dump()
    row.update(dims)
    idx = _load_catalog(tmp_path, json.dumps([row]))
    loaded = idx.get_shot("s")
    for field in dims:
        assert getattr(loaded, field) is None
    assert loaded.measure_on_site is True
    _assert_unknown(idx.check_shot("s"))


NON_NUMERIC = [True, False, "3.1m", "unknown", "", [], {"v": 3}]


@pytest.mark.parametrize("field", ["depth_m", "room_area_m2"])
@pytest.mark.parametrize("bad", NON_NUMERIC, ids=["true", "false", "unit-string", "word", "empty", "list", "object"])
def test_catalog_row_non_numeric_dimension_degrades_to_unknown(tmp_path, field, bad):
    """Regression (fixed in 9faab10, normalization before schema validation). The owner's
    test_retrieval.py covers ceiling_m; this covers depth/area and the measure_on_site flag.
    A bool must never be read as 1 m, and one bad value must not abort the whole index."""
    row = shot("s", "p1", depth_m=12.0, ceiling_m=3.5, room_area_m2=40.0, measure_on_site=False).model_dump()
    row[field] = bad
    other = shot("t", "p2").model_dump()
    gen = write_generation(tmp_path / "gen", [shot("s", "p1"), shot("t", "p2")],
                           np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32),
                           shots_text=json.dumps([row, other]))
    from index.search import ShotRetrievalIndex
    idx = ShotRetrievalIndex.from_cache_dir(gen, text_encoder=fake_text_encoder)
    loaded = idx.get_shot("s")
    assert getattr(loaded, field) is None and loaded.measure_on_site is True
    assert loaded.ceiling_m == 3.5  # only the malformed field is discarded
    _assert_unknown(idx.check_shot("s"))
    assert len(idx.shots) == 2


def test_catalog_row_numeric_string_is_kept(tmp_path):
    row = shot("s", "p1", depth_m=12.0, ceiling_m=3.5, measure_on_site=False).model_dump()
    row["ceiling_m"] = "3.25"
    idx = _load_catalog(tmp_path, json.dumps([row]))
    assert idx.get_shot("s").ceiling_m == 3.25 and idx.get_shot("s").measure_on_site is False


def test_explicit_geometry_minimums_exclude_unknown_rows_but_default_search_keeps_them():
    idx = make_index([
        (shot("known", "p1", depth_m=12.0), [1.0, 0.0, 0.0]),
        (shot("unknown", "p2", depth_m=None, ceiling_m=None, room_area_m2=None,
              measure_on_site=True), [1.0, 0.0, 0.0]),
    ])
    assert [s.shot_id for s in idx.search_shots(query_text="brick", min_depth_m=9)] == ["known"]
    assert {s.shot_id for s in idx.search_shots(query_text="brick")} == {"known", "unknown"}
