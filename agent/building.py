"""The building at a place, from Vexcel Structure data (through Vexcel's MCP server).

One call per place, cached under cache/structure/: footprint and area, height, roof shape and material
(with Vexcel's confidence), what stands on the roof, detected roof defects, ground elevation and the
imagery behind it. The nearest structure to the point is "the building"; others nearby are counted.
These are imagery-derived estimates: they say nothing about load capacity, zoning, permits or
ownership, and many fields are empty for many buildings (shown as unknown, never guessed).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "structure"
_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")
ROOF_OBJECTS = (("ac-unit", "AC unit"), ("roof-vent", "vent"), ("skylight", "skylight"), ("chimney", "chimney"),
                ("satellite-dish", "satellite dish"), ("solar-panel-photovoltaic", "solar panel"),
                ("solar-panel-thermal", "solar thermal panel"))
DEFECTS = (("missing-material", "missing roof material"), ("tarp", "tarp"), ("debris", "debris"),
           ("patch", "patched areas"), ("structural-damage", "structural damage"), ("rust", "rust"),
           ("discoloration.types.water-pooling", "water pooling"), ("discoloration.types.algae-staining", "algae staining"),
           ("discoloration.types.vegetation-on-roof", "vegetation on the roof"))


def _num(value):
    return round(float(value), 2) if isinstance(value, (int, float)) and math.isfinite(value) else None


def footprint_ring(wkt: str, limit: int = 400) -> list[list[float]]:
    """Outer ring of the first polygon as [lon, lat] pairs, thinned to at most `limit` points."""
    if not isinstance(wkt, str) or "((" not in wkt:
        return []
    first = wkt.split("((", 1)[1].split(")", 1)[0]
    ring = [[float(x), float(y)] for x, y in _PAIR.findall(first)]
    step = max(1, math.ceil(len(ring) / limit))
    return ring[::step] if len(ring) >= 3 else []


def placement(feature: dict, lat: float, lon: float) -> tuple[bool, float]:
    """(footprint contains the point, metres from the point to the footprint edge), measured here.

    Vexcel's structure-distance field did not match real distances in testing (about 1 for buildings
    15-46 m away), so the building is chosen by geometry instead.
    """
    ring = footprint_ring((feature.get("properties") or {}).get("footprint.wkt", ""), limit=10_000)
    if len(ring) < 3:
        return False, float("inf")
    kx = 111_320.0 * math.cos(math.radians(lat))
    pts = [((x - lon) * kx, (y - lat) * 110_574.0) for x, y in ring]
    inside = False
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > 0) != (y2 > 0) and 0 < (x2 - x1) * (0 - y1) / (y2 - y1) + x1:
            inside = not inside
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, -(x1 * dx + y1 * dy) / (dx * dx + dy * dy or 1.0)))
        best = min(best, math.hypot(x1 + t * dx, y1 + t * dy))
    return inside, 0.0 if inside else best


def summarize(feature: dict, others: int, distance_m: float | None = None) -> dict:
    p = feature.get("properties", {})
    objects = []
    for key, label in ROOF_OBJECTS:
        count = p.get(f"roof-objects.{key}.count")
        if isinstance(count, int) and count > 0:
            objects.append({"label": label, "count": count, "score": _num(p.get(f"roof-objects.{key}.score"))})
    defects = []
    for key, label in DEFECTS:
        if p.get(f"roof-defects.{key}.detected") is True:
            defects.append({"label": label, "percent": _num(p.get(f"roof-defects.{key}.percent")),
                            "score": _num(p.get(f"roof-defects.{key}.score"))})
    date = p.get("metadata.ortho-date-estimate")
    return {
        "type": p.get("building-type.class"), "type_score": _num(p.get("building-type.score")),
        "footprint_m2": _num(p.get("footprint.area")), "footprint": footprint_ring(p.get("footprint.wkt", "")),
        "height_m": _num(p.get("roof-characteristics.height")),
        "stories": p.get("roof-characteristics.number-of-stories-below-eave"),
        "roof_shape": p.get("roof-characteristics.shape.value"), "roof_shape_score": _num(p.get("roof-characteristics.shape.score")),
        "roof_material": p.get("roof-characteristics.material.class"),
        "roof_material_score": _num(p.get("roof-characteristics.material.score")),
        "roof_tree_cover_pct": _num(p.get("roof-characteristics.tree-cover.percent")),
        "solar": p.get("roof-objects.solar.value"),
        "roof_objects": objects, "roof_defects": defects,
        "ground_elevation_m": _num(p.get("ground-elevation.value")),
        "imagery": {"collection": p.get("metadata.collection"), "gsd_m": _num(p.get("metadata.gsd")),
                    "date": (datetime.fromtimestamp(date / 1000, tz=timezone.utc).date().isoformat()
                             if isinstance(date, (int, float)) else None)},
        "distance_m": _num(distance_m), "others_nearby": others,
        "source": "Vexcel Structure via Vexcel MCP (structure_metadata_extract), imagery-derived estimates",
    }


def building(lat: float, lon: float, *, mcp=None) -> dict:
    """The structure nearest the point, summarized; {"found": False} when Vexcel has none there."""
    key = hashlib.sha256(f"{lat:.6f},{lon:.6f}".encode()).hexdigest()[:20]
    path = CACHE / f"{key}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    from agent.vexcel_assistant import AssistantError, VexcelMCP
    mcp = mcp or VexcelMCP()
    mcp.connect()
    result = mcp._rpc("tools/call", {"name": "structure_metadata_extract", "arguments": {
        "wkt": f"POINT({lon} {lat})", "buffer-meter": 25, "total-records": 5,
        "include": ["structures", "metadata", "calculated"]}}) or {}
    text = "".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
    # Only a readable feature collection is an answer. A tool error (or anything else) is a failure to
    # report and retry later, never cached as "no building here".
    try:
        features = None if result.get("isError") else json.loads(text).get("features")
    except (ValueError, AttributeError):
        features = None
    if not isinstance(features, list):
        raise AssistantError("Vexcel did not return structure data for this place. Try again in a moment.")
    placed = [(placement(f, lat, lon), f) for f in features]
    placed = [((inside, d), f) for (inside, d), f in placed if d != float("inf")]
    if not placed:
        record = {"found": False, "reason": "Vexcel has no structure record within 25 m of this place."}
    else:
        (inside, distance), nearest = min(placed, key=lambda item: (not item[0][0], item[0][1]))
        record = {"found": True, "contains_point": inside, **summarize(nearest, len(placed) - 1, distance)}
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def prompt_facts(record: dict) -> str:
    """A short factual line for image prompts, so edits respect the real building."""
    if not record or not record.get("found"):
        return ""
    parts = []
    if record.get("type"):
        parts.append(f"a {record['type']} building")
    if record.get("footprint_m2"):
        parts.append(f"footprint about {round(record['footprint_m2']):,} m²")
    if record.get("height_m"):
        parts.append(f"about {round(record['height_m'])} m tall")
    if record.get("roof_shape"):
        parts.append(f"{record['roof_shape']} {record.get('roof_material') or ''} roof".replace("  ", " "))
    if record.get("roof_objects"):
        parts.append("on the roof: " + ", ".join(f"{o['count']} {o['label']}{'s' if o['count'] > 1 else ''}"
                                                  for o in record["roof_objects"]))
    return "The building at the centre is " + "; ".join(parts) + "." if parts else ""
