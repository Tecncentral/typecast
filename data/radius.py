"""Offline radius filter: which properties lie within max_km of a base point.

Straight-line (great-circle) distance on a sphere, not drive time. No network and no kit access; it
only reads the dicts it is given. For road time from a base, see index/commute.py.
"""

from __future__ import annotations

import math

LABEL = "straight-line distance, not drive time"
EARTH_RADIUS_KM = 6371.0088


def _coordinates(lat, lon) -> tuple[float, float] | None:
    for value in (lat, lon):
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
        ):
            return None
    return (float(lat), float(lon)) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((phi2 - phi1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def within_radius(base: dict, max_km: float, rows) -> dict:
    """Rows within max_km of base, nearest first.

    base is {"lat", "lon"}; each row is a dict with property_id, lat and lon. A row whose
    coordinates are missing or invalid is not guessed at: it is left out of the results and counted
    in excluded_missing_coordinates. Distance ties are ordered by property_id.
    """
    start = (
        _coordinates(base.get("lat"), base.get("lon"))
        if isinstance(base, dict)
        else None
    )
    if start is None:
        raise ValueError("base needs a valid lat and lon")
    if (
        isinstance(max_km, bool)
        or not isinstance(max_km, int | float)
        or not math.isfinite(max_km)
        or max_km < 0
    ):
        raise ValueError("max_km must be a finite number of at least zero")
    found, excluded = [], 0
    for row in rows:
        if not isinstance(row, dict) or row.get("property_id") in (None, ""):
            raise ValueError("every row needs a property_id")
        point = _coordinates(row.get("lat"), row.get("lon"))
        if point is None:
            excluded += 1
            continue
        distance = haversine_km(*start, *point)
        if distance <= max_km:
            found.append((distance, str(row["property_id"])))
    found.sort()
    return {
        "label": LABEL,
        "base": {"lat": start[0], "lon": start[1]},
        "max_km": max_km,
        "results": [
            {"property_id": pid, "distance_km": round(distance, 3)}
            for distance, pid in found
        ],
        "excluded_missing_coordinates": excluded,
    }
