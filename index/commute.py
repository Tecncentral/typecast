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


def _blank():
    return {"status": "unknown", "minutes": None, "miles": None,
            "source": "OSRM / OpenStreetMap", "traffic": False}


def route_commutes(origin, properties, *, mock=False):
    """Return exact property-keyed estimates; unavailable/unreachable stays unknown.

    One table request for <=24 destinations; a five-minute cache stores only a
    complete table. Provider failures are not cached. The public demo service
    is replaceable for deployment.
    """
    global _LAST_CALL
    if not isinstance(properties, dict):
        return {}
    result = {pid: _blank() for pid in properties}
    located = []
    for pid, prop in properties.items():
        point = coordinates(prop)
        if point is None:
            result[pid]["note"] = "Property coordinates unavailable"
        else:
            located.append((pid, point))
    targets = located[:24]
    for pid, _point in located[24:]:
        result[pid]["note"] = "Property was outside the 24-destination routing limit"
    if mock:
        for row in result.values():
            row["note"] = "Routing not called for mock fixtures"
        return {pid: dict(row) for pid, row in result.items()}
    if not targets:
        return {pid: dict(row) for pid, row in result.items()}
    start = coordinates(origin)
    if start is None:
        return {pid: dict(row) for pid, row in result.items()}

    def published():
        return {pid: dict(row) for pid, row in result.items()}

    key = (start, tuple(targets))
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < 300:
            _CACHE.move_to_end(key)
            for pid, row in cached[1].items():
                if pid in result:
                    result[pid] = dict(row)
            return published()
        # Bound demo-service rate across concurrent plan requests in this process.
        pause = max(0.0, 1.05 - (time.monotonic() - _LAST_CALL))
        if pause:
            time.sleep(pause)
        _LAST_CALL = time.monotonic()
        points = [start, *(point for _pid, point in targets)]
        coords = ";".join(f"{lon},{lat}" for lat, lon in points)
        base = os.environ.get("TYPECAST_OSRM_URL", "https://router.project-osrm.org").rstrip("/")
        try:
            response = httpx.get(f"{base}/table/v1/driving/{coords}",
                                 params={"sources": "0", "annotations": "duration,distance"},
                                 headers={"User-Agent": "route-table-client/1.0"},
                                 timeout=12, follow_redirects=False)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("code") != "Ok":
                raise ValueError("Router did not return a table")
            durations, distances = data["durations"][0], data["distances"][0]
            destinations = data.get("destinations")
            sources = data.get("sources")
            expected = len(points)
            aligned = (isinstance(durations, list) and isinstance(distances, list)
                       and len(durations) == expected and len(distances) == expected
                       and isinstance(destinations, list) and len(destinations) == expected
                       and isinstance(sources, list) and bool(sources) and isinstance(sources[0], dict))
            if not aligned:
                raise ValueError("Router table is misaligned")
            for i, (pid, _) in enumerate(targets, 1):
                dest = destinations[i]
                if not isinstance(dest, dict):
                    continue
                sec, meters = durations[i], distances[i]
                # A road snapped far from a home or property cannot establish its commute.
                snaps = [sources[0].get("distance"), dest.get("distance")]
                valid = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                            and math.isfinite(v) and v >= 0 for v in (sec, meters, *snaps))
                if not valid or any(v > 1000 for v in snaps):
                    continue
                result[pid].update(status="estimated", minutes=sec / 60, miles=meters / 1609.344,
                                   checked_at=datetime.now(timezone.utc).isoformat(),
                                   note="One-way driving estimate; no live traffic, departure-time or parking delay")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            for row in result.values():
                row.update(status="unknown", minutes=None, miles=None,
                           note="Road routing unavailable; no distance-to-time fallback used")
                row.pop("checked_at", None)
            return published()
        _CACHE[key] = (time.monotonic(), {pid: dict(result[pid]) for pid, _point in targets})
        while len(_CACHE) > 64:
            _CACHE.popitem(last=False)
        return published()
