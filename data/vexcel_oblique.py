"""Vexcel oblique imagery, semantic tile search and terrain for outdoor and exterior search.

Documented services (https://api.vexcelgroup.com/v2/api-docs/{oriented,embedding,dtm,dsm}):
  embedding/extract  text search over ortho-tile embeddings (oblique embeddings are not indexed for the
                     LA and Houston collections today: the API answers "No embeddings found")
  oriented/extract   one 45-degree oblique (north, east, south or west) or nadir image around a point
  dtm/elevation      bare-earth elevation at each vertex of a point or line, metres
  dsm/elevation      surface elevation (buildings and trees included) at each vertex

Only these fixed endpoints receive the key. Requests go through VexcelClient._request: redirects are
disabled and errors never carry provider bodies or credential-bearing URLs. Coverage is the metro
collections; outside them the API answers 403, reported as outside coverage.
"""
from __future__ import annotations

import json
import math
import re
import time

from data.vexcel_budget import caps, check_and_record
from data.vexcel_client import VEXCEL_BASE, ProviderError, VexcelClient

ENDPOINTS = {"embedding/extract", "oriented/extract", "dtm/elevation", "dsm/elevation"}
MAX_RETRIES = 5
DIRECTIONS = ("north", "east", "south", "west")
_Z = re.compile(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")


class ObliqueClient(VexcelClient):
    def _call(self, endpoint: str, parameters: dict, count: int = 1) -> bytes:
        if endpoint not in ENDPOINTS:
            raise ValueError("Unsupported Vexcel endpoint")
        check_and_record(endpoint, count)
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self._request("GET", VEXCEL_BASE + endpoint, params={**parameters, "api_key": self.api_key})
            except ProviderError as error:
                if "HTTP 429" not in str(error):
                    raise
                if attempt == MAX_RETRIES:
                    raise ProviderError("Vexcel HTTP 429: rate limited, retries exhausted") from None
                time.sleep(2**attempt)

    def search_tiles(self, text: str, lat: float, lon: float, radius_m: float, k: int = 16) -> list[dict]:
        """Ortho tiles whose embedding matches the text, best first; [] when nothing matches."""
        k = min(k, caps("embedding")["per_search"])
        try:
            raw = self._call("embedding/extract", {
                "search-text": text[:300], "wkt": f"POINT({lon} {lat})", "buffer-meter": int(radius_m),
                "source.product-type": "final-ortho", "total-records": k, "page-size": k,
                "include": "score,geometry,quadkey,collection"}, count=k)
        except ProviderError as error:
            if "404" in str(error):
                return []
            raise
        tiles = []
        for feature in json.loads(raw).get("features", []):
            ring = _outer_ring(feature.get("geometry") or {})
            if not ring:
                continue
            props = feature.get("properties") or {}
            tiles.append({"lat": sum(p[1] for p in ring) / len(ring), "lon": sum(p[0] for p in ring) / len(ring),
                          "score": float(props.get("score") or 0.0), "quadkey": props.get("quadkey"),
                          "collection": props.get("collection"), "ring": ring})
        return sorted(tiles, key=lambda t: -t["score"])

    def oblique(self, lat: float, lon: float, direction: str, size_m: int = 120,
                width: int = 1024, height: int = 768) -> bytes:
        """The newest Vexcel oblique of that cardinal product type (oblique-north etc.) around the point."""
        if direction not in DIRECTIONS:
            raise ValueError("direction must be north, east, south or west")
        return self._call("oriented/extract", {
            "layer": "urban,urban-r,urban-g,wide-area", "wkt": f"POINT({lon} {lat})",
            "product-type": f"oblique-{direction}", "bbox-dimensions": f"{size_m},{size_m}",
            "destination-dimensions": f"{width},{height},fill", "image-format": "png",
            "order-by": "collection-last-capture-date-desc,image-center-distance-asc",
            "attribution": "true"})

    def elevations(self, points: list[tuple[float, float]], model: str = "dtm") -> list[float]:
        """Elevation in metres at each (lat, lon), from the bare-earth (dtm) or surface (dsm) model."""
        if model not in ("dtm", "dsm") or not points:
            raise ValueError("model must be dtm or dsm, with at least one point")
        wkt = (f"POINT({points[0][1]} {points[0][0]})" if len(points) == 1 else
               "LINESTRING(" + ", ".join(f"{lon} {lat}" for lat, lon in points) + ")")
        data = json.loads(self._call(f"{model}/elevation", {"wkt": wkt, "unit-system": "metric"}))
        values = [float(z) for _, _, z in _Z.findall(str(data.get("wkt", "")))]
        if len(values) != len(points):
            raise ProviderError("Vexcel elevation returned an unexpected number of vertices")
        return values


def _outer_ring(geometry: dict) -> list:
    coords = geometry.get("coordinates")
    try:
        if geometry.get("type") == "Polygon":
            return coords[0]
        if geometry.get("type") == "MultiPolygon":
            return coords[0][0]
    except (TypeError, IndexError):
        return []
    return []


def cross_points(lat: float, lon: float, half_m: float = 100.0, steps: int = 4) -> list[tuple[float, float]]:
    """A west-east then south-north cross of points through the centre (2*steps+1 each)."""
    dlat = half_m / 111_320.0
    dlon = half_m / (111_320.0 * math.cos(math.radians(lat)))
    we = [(lat, lon + dlon * i / steps) for i in range(-steps, steps + 1)]
    sn = [(lat + dlat * i / steps, lon) for i in range(-steps, steps + 1)]
    return we + sn


def terrain_summary(ground: list[float], half_m: float = 100.0, steps: int = 4) -> dict:
    """Relief and steepest slope along the cross, from bare-earth elevations."""
    n = 2 * steps + 1
    spacing = half_m / steps
    slopes = []
    for line in (ground[:n], ground[n:2 * n]):
        slopes += [abs(b - a) / spacing for a, b in zip(line, line[1:])]
    return {"ground_m": round(ground[steps], 1), "relief_m": round(max(ground) - min(ground), 1),
            "max_slope_deg": round(math.degrees(math.atan(max(slopes))), 1) if slopes else None}
