"""Pure-stdlib Matterport floor/room boundary reconstruction and sweep-to-room mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

ROOMS_GRAPHQL_QUERY = (
    "query Rooms($id:ID!){model(id:$id){"
    "floors{id label vertices{id position{x y}} edges{id type thickness vertices{id}}} "
    "rooms{id floor{id} classifications{label confidence} boundary{edges{id}} "
    "dimensions(units:metric){areaFloor width depth height}} "
    "panoLocations{id anchor{id floor{id} room{id}} rotation{x y z w}}}}"
)

_EPS = 1e-9
Point2D = tuple[float, float]


@dataclass(frozen=True)
class RoomPolygon:
    room_id: str
    floor_id: str | None
    ring: tuple[Point2D, ...]
    classification: str | None
    classification_confidence: float | None
    room_area_m2: float | None
    ceiling_m: float | None


@dataclass(frozen=True)
class SweepRoomMatch:
    room_id: str | None
    floor_id: str | None
    classification: str | None
    room_area_m2: float | None
    ceiling_m: float | None
    depth_m: None = None
    measure_on_site: bool = True
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "floor_id": self.floor_id,
            "classification": self.classification,
            "room_area_m2": self.room_area_m2,
            "ceiling_m": self.ceiling_m,
            "depth_m": None,
            "measure_on_site": True,
            "warnings": list(self.warnings),
        }


def _positive_finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if math.isfinite(num) and num > 0.0 else None


def _finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if math.isfinite(num) else None


def _orient(a: Point2D, b: Point2D, c: Point2D) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point2D, b: Point2D, p: Point2D) -> bool:
    if abs(_orient(a, b, p)) > _EPS:
        return False
    return (
        min(a[0], b[0]) - _EPS <= p[0] <= max(a[0], b[0]) + _EPS
        and min(a[1], b[1]) - _EPS <= p[1] <= max(a[1], b[1]) + _EPS
    )


def _segments_intersect(a1: Point2D, a2: Point2D, b1: Point2D, b2: Point2D) -> bool:
    o1 = _orient(a1, a2, b1)
    o2 = _orient(a1, a2, b2)
    o3 = _orient(b1, b2, a1)
    o4 = _orient(b1, b2, a2)
    if (o1 > _EPS and o2 < -_EPS or o1 < -_EPS and o2 > _EPS) and (
        o3 > _EPS and o4 < -_EPS or o3 < -_EPS and o4 > _EPS
    ):
        return True
    return (
        _on_segment(a1, a2, b1)
        or _on_segment(a1, a2, b2)
        or _on_segment(b1, b2, a1)
        or _on_segment(b1, b2, a2)
    )


def _reconstruct_closed_ring(
    edge_ids: Sequence[str],
    edges_by_id: Mapping[str, tuple[str, str]],
    vertices_by_id: Mapping[str, Point2D],
) -> tuple[Point2D, ...] | None:
    if len(edge_ids) < 3 or len(set(edge_ids)) != len(edge_ids):
        return None
    adj: dict[str, list[str]] = {}
    for eid in edge_ids:
        pair = edges_by_id.get(eid)
        if pair is None or pair[0] == pair[1]:
            return None
        u, v = pair
        if u not in vertices_by_id or v not in vertices_by_id:
            return None
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)

    if len(adj) != len(edge_ids) or any(len(nbrs) != 2 for nbrs in adj.values()):
        return None

    start = next(iter(adj))
    ordered_vids = [start]
    prev: str | None = None
    curr = start
    while True:
        n0, n1 = adj[curr]
        nxt = n1 if n0 == prev else n0
        if nxt == start:
            break
        if nxt in ordered_vids:
            return None
        ordered_vids.append(nxt)
        prev, curr = curr, nxt

    if len(ordered_vids) != len(edge_ids):
        return None

    ring = tuple(vertices_by_id[vid] for vid in ordered_vids)
    n = len(ring)
    area2 = 0.0
    for i in range(n):
        p1, p2 = ring[i], ring[(i + 1) % n]
        if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) <= _EPS:
            return None
        area2 += p1[0] * p2[1] - p2[0] * p1[1]
    if abs(area2) <= _EPS:
        return None

    for i in range(n):
        a1, a2 = ring[i], ring[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            if _segments_intersect(a1, a2, ring[j], ring[(j + 1) % n]):
                return None
    return ring


def _point_in_ring(pt: Point2D, ring: Sequence[Point2D]) -> str:
    """Return 'inside', 'boundary', or 'outside' via ray casting with exact edge checks."""
    n = len(ring)
    for i in range(n):
        if _on_segment(ring[i], ring[(i + 1) % n], pt):
            return "boundary"
    inside = False
    px, py = pt
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            x_cross = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if abs(px - x_cross) <= _EPS:
                return "boundary"
            if px < x_cross:
                inside = not inside
    return "inside" if inside else "outside"


def _top_classification(items: Any) -> tuple[str | None, float | None]:
    if not isinstance(items, list):
        return None, None
    best_label: str | None = None
    best_conf: float = -1.0
    for item in items:
        if not isinstance(item, Mapping):
            continue
        label = item.get("label")
        conf = _finite_float(item.get("confidence"))
        if isinstance(label, str) and label.strip() and conf is not None and 0 <= conf <= 1:
            if conf > best_conf or (conf == best_conf and (best_label is None or label.strip() < best_label)):
                best_label = label.strip()
                best_conf = conf
    return (best_label, best_conf) if best_label is not None else (None, None)


def parse_rooms_model(
    payload: Mapping[str, Any],
) -> tuple[list[str], list[RoomPolygon], list[str]]:
    """Parse official Rooms GraphQL response into (floor_ids, valid_rooms, warnings)."""
    root = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
    model = root.get("model") if isinstance(root, Mapping) else None
    if not isinstance(model, Mapping):
        return [], [], ["rooms_payload_missing_model"]

    warnings: list[str] = []
    floor_ids: list[str] = []
    vertices_by_id: dict[str, Point2D] = {}
    edges_by_id: dict[str, tuple[str, str]] = {}

    for floor in model.get("floors") or []:
        if not isinstance(floor, Mapping):
            continue
        fid = floor.get("id")
        if isinstance(fid, str) and fid.strip():
            floor_ids.append(fid.strip())
        for v in floor.get("vertices") or []:
            if not isinstance(v, Mapping) or not isinstance(v.get("id"), str):
                continue
            pos = v.get("position")
            if isinstance(pos, Mapping):
                vx, vy = _finite_float(pos.get("x")), _finite_float(pos.get("y"))
                if vx is not None and vy is not None:
                    vertices_by_id[v["id"]] = (vx, vy)
        for e in floor.get("edges") or []:
            if not isinstance(e, Mapping) or not isinstance(e.get("id"), str):
                continue
            verts = e.get("vertices")
            if isinstance(verts, list) and len(verts) == 2 and all(
                isinstance(x, Mapping) and isinstance(x.get("id"), str) for x in verts
            ):
                edges_by_id[e["id"]] = (verts[0]["id"], verts[1]["id"])
            else:
                warnings.append(f"malformed_floor_edge:{e['id']}")

    rooms: list[RoomPolygon] = []
    for room in model.get("rooms") or []:
        if not isinstance(room, Mapping) or not isinstance(room.get("id"), str) or not room["id"].strip():
            warnings.append("malformed_room_missing_id")
            continue
        rid = room["id"].strip()
        floor_obj = room.get("floor")
        floor_id = floor_obj["id"].strip() if isinstance(floor_obj, Mapping) and isinstance(floor_obj.get("id"), str) and floor_obj["id"].strip() else None

        boundary = room.get("boundary")
        raw_edges = boundary.get("edges") if isinstance(boundary, Mapping) else None
        edge_ids = [
            e["id"] for e in (raw_edges or []) if isinstance(e, Mapping) and isinstance(e.get("id"), str)
        ]
        if not isinstance(raw_edges, list) or len(edge_ids) != len(raw_edges):
            warnings.append(f"invalid_room_boundary:{rid}")
            continue
        ring = _reconstruct_closed_ring(edge_ids, edges_by_id, vertices_by_id)
        if ring is None:
            warnings.append(f"invalid_room_boundary:{rid}")
            continue

        dims = room.get("dimensions") if isinstance(room.get("dimensions"), Mapping) else {}
        label, conf = _top_classification(room.get("classifications"))
        rooms.append(
            RoomPolygon(
                room_id=rid,
                floor_id=floor_id,
                ring=ring,
                classification=label,
                classification_confidence=conf,
                room_area_m2=_positive_finite(dims.get("areaFloor")),
                ceiling_m=_positive_finite(dims.get("height")),
            )
        )
    return floor_ids, rooms, warnings


def match_sweep_to_room(
    payload: Mapping[str, Any],
    position: Mapping[str, Any] | None,
    *,
    pano_floor_id: str | None = None,
) -> SweepRoomMatch:
    """Map a sweep xyz position to a unique containing room when floor identity is reliable."""
    floor_ids, rooms, base_warnings = parse_rooms_model(payload)
    warnings = list(base_warnings)

    if not isinstance(position, Mapping):
        return SweepRoomMatch(None, pano_floor_id, None, None, None, warnings=tuple(warnings + ["missing_sweep_position"]))
    px, py = _finite_float(position.get("x")), _finite_float(position.get("y"))
    _ = _finite_float(position.get("z"))
    if px is None or py is None:
        return SweepRoomMatch(None, pano_floor_id, None, None, None, warnings=tuple(warnings + ["invalid_sweep_position"]))

    unique_floors = set(floor_ids) | {r.floor_id for r in rooms if r.floor_id is not None}
    if len(unique_floors) > 1 and not pano_floor_id:
        warnings.append("ambiguous_multiple_floors_without_pano_floor_id")
        return SweepRoomMatch(None, None, None, None, None, warnings=tuple(warnings))

    resolved_floor = pano_floor_id if pano_floor_id else (next(iter(unique_floors)) if len(unique_floors) == 1 else None)
    if resolved_floor is None or resolved_floor not in unique_floors:
        return SweepRoomMatch(None, None, None, None, None,
                              warnings=tuple(warnings + ['unresolved_floor_identity']))
    candidate_rooms = [r for r in rooms if resolved_floor is None or r.floor_id == resolved_floor]

    inside_matches: list[RoomPolygon] = []
    for room in candidate_rooms:
        status = _point_in_ring((px, py), room.ring)
        if status == "boundary":
            warnings.append(f"sweep_on_room_boundary:{room.room_id}")
            return SweepRoomMatch(None, resolved_floor, None, None, None, warnings=tuple(warnings))
        if status == "inside":
            inside_matches.append(room)

    if len(inside_matches) == 0:
        warnings.append("no_containing_room")
        return SweepRoomMatch(None, resolved_floor, None, None, None, warnings=tuple(warnings))
    if len(inside_matches) > 1:
        warnings.append("ambiguous_overlapping_rooms:" + ",".join(sorted(r.room_id for r in inside_matches)))
        return SweepRoomMatch(None, resolved_floor, None, None, None, warnings=tuple(warnings))

    hit = inside_matches[0]
    warnings.append("unverified_metric_estimate_measure_on_site")
    return SweepRoomMatch(
        room_id=hit.room_id,
        floor_id=hit.floor_id or resolved_floor,
        classification=hit.classification,
        room_area_m2=hit.room_area_m2,
        ceiling_m=hit.ceiling_m,
        depth_m=None,
        measure_on_site=True,
        warnings=tuple(warnings),
    )


def enrich_source_manifest(
    manifest: Mapping[str, Any],
    rooms_by_model_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Pure adapter enriching source_manifest records with room estimates while preserving uncertainty."""
    enriched_records: list[dict[str, Any]] = []
    for rec in manifest.get("records") or []:
        if not isinstance(rec, Mapping):
            continue
        out = dict(rec)
        prov = dict(rec.get("provenance") or {}) if isinstance(rec.get("provenance"), Mapping) else {}
        model_id = rec.get("model_id")
        rooms_payload = rooms_by_model_id.get(model_id) if isinstance(model_id, str) else None
        if rooms_payload is None:
            out.update({"room_id": None, "floor_id": None, "classification": None, "room_area_m2": None, "ceiling_m": None, "depth_m": None, "measure_on_site": True})
            prov["room_match_warnings"] = ["missing_rooms_payload_for_model"]
        else:
            # These links were verified through the live official GraphQL schema.
            model = (rooms_payload.get('data') or {}).get('model') or {}
            pano = next((p for p in model.get('panoLocations', [])
                         if p.get('id') == rec.get('sweep_id')), {})
            anchor = pano.get('anchor') or {}
            anchor_floor = (anchor.get('floor') or {}).get('id')
            anchor_room = (anchor.get('room') or {}).get('id')
            if anchor_floor:
                prov['floor_id'] = anchor_floor
            if anchor.get('id'):
                prov['anchor_id'] = anchor['id']
            if pano.get('rotation'):
                prov['source_rotation_quaternion'] = dict(pano['rotation'])
            pano_floor = prov.get("floor_id") if isinstance(prov.get("floor_id"), str) else None
            match = match_sweep_to_room(rooms_payload, prov.get("position_m"), pano_floor_id=pano_floor)
            assigned = [r for r in model.get('rooms', []) if r.get('id') == anchor_room
                        and (r.get('floor') or {}).get('id') == anchor_floor]
            if anchor_floor and len(assigned) == 1:
                room = assigned[0]
                dims = room.get('dimensions') or {}
                label, _ = _top_classification(room.get('classifications'))
                match = SweepRoomMatch(anchor_room, anchor_floor, label,
                    _positive_finite(dims.get('areaFloor')), _positive_finite(dims.get('height')),
                    warnings=('provider_anchor_room_assignment', 'unverified_metric_estimate_measure_on_site'))
            out.update({
                "room_id": match.room_id,
                "floor_id": match.floor_id,
                "classification": match.classification,
                "room_area_m2": match.room_area_m2,
                "ceiling_m": match.ceiling_m,
                "depth_m": None,
                "measure_on_site": True,
            })
            prov["room_match_warnings"] = list(match.warnings)
        out["provenance"] = prov
        enriched_records.append(out)

    result = dict(manifest)
    result["records"] = enriched_records
    return result
