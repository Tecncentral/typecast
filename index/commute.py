"""Bounded one-origin road routing. No traffic, straight-line substitutes or persisted homes."""
from __future__ import annotations

import math
import os
import threading
import time
from datetime import datetime, timezone
from collections import OrderedDict

import httpx

_CACHE: OrderedDict = OrderedDict()
_LOCK = threading.Lock()
_LAST_CALL = 0.0


def coordinates(value):
    if not isinstance(value, dict):
        return None
    lat, lon = value.get("lat"), value.get("lon")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (lat, lon)):
        return None
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def route_commutes(origin, properties, *, mock=False):
    """Return exact property-keyed estimates; unavailable/unreachable stays unknown.

    One table request for <=24 destinations; five-minute in-memory cache reused
    across slider changes. Public demo service is replaceable for deployment.
    """
    global _LAST_CALL
    result = {pid: {"status": "unknown", "minutes": None, "miles": None,
                    "source": "OSRM / OpenStreetMap", "traffic": False}
              for pid in properties}
    targets = [(pid, coordinates(p)) for pid, p in properties.items()]
    targets = [(pid, point) for pid, point in targets if point is not None][:24]
    if not targets or mock:
        for row in result.values():
            row["note"] = "Routing not called for mock fixtures" if mock else "Property coordinates unavailable"
        return result
    start = coordinates(origin)
    if start is None:
        return result
    key = (start, tuple(targets))
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < 300:
            return {pid: dict(row) for pid, row in cached[1].items()}
        # Bound demo-service rate across concurrent plan requests in this process.
        pause = max(0, 1.05 - (time.monotonic() - _LAST_CALL))
        if pause:
            time.sleep(pause)
        _LAST_CALL = time.monotonic()
        points = [start] + [point for _, point in targets]
        coords = ";".join(f"{lon},{lat}" for lat, lon in points)
        base = os.environ.get("TYPECAST_OSRM_URL", "https://router.project-osrm.org").rstrip("/")
        try:
            response = httpx.get(f"{base}/table/v1/driving/{coords}",
                                 params={"sources": "0", "annotations": "duration,distance"},
                                 headers={"User-Agent": "Typecast-HackPrinceton/1.0 (https://github.com/Tecncentral/typecast)"},
                                 timeout=12, follow_redirects=False)
            response.raise_for_status()
            data = response.json()
            if data.get("code") != "Ok":
                raise ValueError("Router did not return a table")
            durations, distances = data["durations"][0], data["distances"][0]
            destinations = data.get("destinations", [])
            sources = data.get("sources", [])
            for i, (pid, _) in enumerate(targets, 1):
                sec, meters = durations[i], distances[i]
                # A road snapped far from a home or property cannot establish its commute.
                snaps = [sources[0].get("distance"), destinations[i].get("distance")]
                valid = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                            and math.isfinite(v) and v >= 0 for v in (sec, meters, *snaps))
                if not valid or any(v > 1000 for v in snaps):
                    continue
                result[pid].update(status="estimated", minutes=sec / 60, miles=meters / 1609.344,
                                   checked_at=datetime.now(timezone.utc).isoformat(),
                                   note="One-way driving estimate; no live traffic, departure-time or parking delay")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            for row in result.values():
                row["note"] = "Road routing unavailable; no distance-to-time fallback used"
        _CACHE[key] = (time.monotonic(), result)
        while len(_CACHE) > 64:
            _CACHE.popitem(last=False)
    return {pid: dict(row) for pid, row in result.items()}
