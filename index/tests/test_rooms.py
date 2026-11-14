"""Offline unit tests for index/rooms.py."""

from __future__ import annotations

from index.rooms import enrich_source_manifest, match_sweep_to_room


def _payload(floors: list[dict], rooms: list[dict]) -> dict:
    return {"data": {"model": {"floors": floors, "rooms": rooms}}}


def _floor(fid: str, pts: dict[str, tuple[float, float]], edges: list[tuple[str, str, str]]) -> dict:
    return {
        "id": fid,
        "label": fid,
        "vertices": [{"id": vid, "position": {"x": x, "y": y}} for vid, (x, y) in pts.items()],
        "edges": [{"id": eid, "type": "wall", "thickness": 0.15, "vertices": [{"id": u}, {"id": v}]} for eid, u, v in edges],
    }


def _room(rid: str, fid: str, eids: list[str], *, area=24.0, height=3.0, width=4.0, depth=6.0, classes=None) -> dict:
    return {
        "id": rid,
        "floor": {"id": fid},
        "classifications": classes if classes is not None else [{"label": "living room", "confidence": 0.91}, {"label": "den", "confidence": 0.4}],
        "boundary": {"edges": [{"id": e} for e in eids]},
        "dimensions": {"areaFloor": area, "width": width, "depth": depth, "height": height},
    }


def test_rectangle_and_concave_l_shape_with_unordered_edges() -> None:
    # Unordered edges forming L-shaped concave room + separate rectangle
    pts = {
        "v1": (0.0, 0.0), "v2": (4.0, 0.0), "v3": (4.0, 2.0),
        "v4": (2.0, 2.0), "v5": (2.0, 4.0), "v6": (0.0, 4.0),
        "r1": (10.0, 0.0), "r2": (14.0, 0.0), "r3": (14.0, 3.0), "r4": (10.0, 3.0),
    }
    edges = [
        ("e3", "v3", "v4"), ("e1", "v1", "v2"), ("e5", "v5", "v6"),
        ("e2", "v2", "v3"), ("e6", "v6", "v1"), ("e4", "v4", "v5"),
        ("re1", "r1", "r2"), ("re2", "r2", "r3"), ("re3", "r3", "r4"), ("re4", "r4", "r1"),
    ]
    data = _payload(
        [_floor("f1", pts, edges)],
        [
            _room("room_l", "f1", ["e1", "e2", "e3", "e4", "e5", "e6"], area=12.0, height=2.9),
            _room("room_rect", "f1", ["re1", "re2", "re3", "re4"], area=12.0, height=3.2),
        ],
    )

    # Inside concave pocket (3.0, 3.0) is outside room_l
    out_pocket = match_sweep_to_room(data, {"x": 3.0, "y": 3.0, "z": 0.0})
    assert out_pocket.room_id is None

    # Inside L-arm (1.0, 3.0) matches room_l; depth_m remains None & measure_on_site True
    in_l = match_sweep_to_room(data, {"x": 1.0, "y": 3.0, "z": 0.0})
    assert in_l.room_id == "room_l"
    assert in_l.floor_id == "f1"
    assert in_l.classification == "living room"
    assert in_l.room_area_m2 == 12.0
    assert in_l.ceiling_m == 2.9
    assert in_l.depth_m is None
    assert in_l.measure_on_site is True


def test_boundary_point_is_ambiguous_unknown() -> None:
    pts = {"v1": (0.0, 0.0), "v2": (4.0, 0.0), "v3": (4.0, 4.0), "v4": (0.0, 4.0)}
    edges = [("e1", "v1", "v2"), ("e2", "v2", "v3"), ("e3", "v3", "v4"), ("e4", "v4", "v1")]
    data = _payload([_floor("f1", pts, edges)], [_room("r1", "f1", ["e1", "e2", "e3", "e4"])])

    res = match_sweep_to_room(data, {"x": 2.0, "y": 0.0, "z": 1.0})
    assert res.room_id is None
    assert "sweep_on_room_boundary:r1" in res.warnings


def test_overlapping_rooms_and_self_intersecting_or_bad_edges_rejected() -> None:
    pts = {
        "a1": (0.0, 0.0), "a2": (4.0, 0.0), "a3": (4.0, 4.0), "a4": (0.0, 4.0),
        "b1": (2.0, 2.0), "b2": (6.0, 2.0), "b3": (6.0, 6.0), "b4": (2.0, 6.0),
        "x1": (10.0, 0.0), "x2": (14.0, 4.0), "x3": (10.0, 4.0), "x4": (14.0, 0.0),
    }
    edges = [
        ("ea1", "a1", "a2"), ("ea2", "a2", "a3"), ("ea3", "a3", "a4"), ("ea4", "a4", "a1"),
        ("eb1", "b1", "b2"), ("eb2", "b2", "b3"), ("eb3", "b3", "b4"), ("eb4", "b4", "b1"),
        # Bowtie self-intersection
        ("ex1", "x1", "x2"), ("ex2", "x2", "x3"), ("ex3", "x3", "x4"), ("ex4", "x4", "x1"),
    ]
    data = _payload(
        [_floor("f1", pts, edges)],
        [
            _room("r_a", "f1", ["ea1", "ea2", "ea3", "ea4"]),
            _room("r_b", "f1", ["eb1", "eb2", "eb3", "eb4"]),
            _room("r_bowtie", "f1", ["ex1", "ex2", "ex3", "ex4"]),
            _room("r_open", "f1", ["ea1", "ea2", "ea3"]),
        ],
    )

    overlap = match_sweep_to_room(data, {"x": 3.0, "y": 3.0, "z": 0.0})
    assert overlap.room_id is None
    assert any(w.startswith("ambiguous_overlapping_rooms:") for w in overlap.warnings)
    assert "invalid_room_boundary:r_bowtie" in overlap.warnings
    assert "invalid_room_boundary:r_open" in overlap.warnings


def test_multiple_floors_require_explicit_pano_floor_id() -> None:
    pts = {"v1": (0.0, 0.0), "v2": (5.0, 0.0), "v3": (5.0, 5.0), "v4": (0.0, 5.0)}
    edges1 = [("e1", "v1", "v2"), ("e2", "v2", "v3"), ("e3", "v3", "v4"), ("e4", "v4", "v1")]
    edges2 = [("f2e1", "v1", "v2"), ("f2e2", "v2", "v3"), ("f2e3", "v3", "v4"), ("f2e4", "v4", "v1")]
    data = _payload(
        [_floor("floor_1", pts, edges1), _floor("floor_2", pts, edges2)],
        [_room("r_down", "floor_1", ["e1", "e2", "e3", "e4"]), _room("r_up", "floor_2", ["f2e1", "f2e2", "f2e3", "f2e4"])],
    )

    ambiguous = match_sweep_to_room(data, {"x": 2.0, "y": 2.0, "z": 3.5})
    assert ambiguous.room_id is None
    assert "ambiguous_multiple_floors_without_pano_floor_id" in ambiguous.warnings

    explicit = match_sweep_to_room(data, {"x": 2.0, "y": 2.0, "z": 3.5}, pano_floor_id="floor_2")
    assert explicit.room_id == "r_up"
    assert explicit.floor_id == "floor_2"


def test_null_dimensions_and_manifest_enrichment_adapter() -> None:
    pts = {"v1": (0.0, 0.0), "v2": (4.0, 0.0), "v3": (4.0, 4.0), "v4": (0.0, 4.0)}
    edges = [("e1", "v1", "v2"), ("e2", "v2", "v3"), ("e3", "v3", "v4"), ("e4", "v4", "v1")]
    data = _payload([_floor("f1", pts, edges)], [_room("r_null", "f1", ["e1", "e2", "e3", "e4"], area=None, height=0.0, classes=[])])

    manifest = {
        "records": [{
            "shot_id": "m1__s1__f1",
            "model_id": "m1",
            "sweep_id": "s1",
            "property_id": "p1",
            "heading_deg": 0.0,
            "room_area_m2": None,
            "ceiling_m": None,
            "depth_m": None,
            "measure_on_site": True,
            "provenance": {"position_m": {"x": 1.0, "y": 1.0, "z": 0.0}, "fetched_at": "2026-11-14T00:00:00+00:00"},
        }]
    }
    enriched = enrich_source_manifest(manifest, {"m1": data})
    rec = enriched["records"][0]
    assert rec["room_id"] == "r_null"
    assert rec["classification"] is None
    assert rec["room_area_m2"] is None
    assert rec["ceiling_m"] is None
    assert rec["depth_m"] is None
    assert rec["measure_on_site"] is True
    assert rec["heading_deg"] == 0.0
    assert rec["provenance"]["fetched_at"] == "2026-11-14T00:00:00+00:00"
