"""Owner 2. Crew parking and noise from Vexcel aerial imagery.

TYPECAST_USE_MOCKS=1 returns mocks/logistics.json. Otherwise a property is fetched
from Vexcel once and cached under cache/vexcel/.

Everything derived from imagery is an estimate. An aerial cannot show parking
permission, truck clearance, garage or street parking, or sound level.
"""

import base64
import io
import json
import math
import os
import pathlib
import time

from contracts.schemas import Logistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
USE_MOCKS = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"
M2_PER_CAR = 30.0
CARS_PER_TRUCK = 4

_CACHE = ROOT / "cache" / "vexcel"
_JOIN = ROOT / "cache" / "join.parquet"
_API = "https://api.vexcelgroup.com/v2"
_LAYERS = "urban,urban-r,wide-area,urban-g"
_M_PER_DEG = 111_320

_PARKING_BUFFER_M = 30  # lots on or beside the parcel
_NO_PARCEL_HALF_M = 40  # window used when Vexcel has no parcel at the point
_NOISE_HALF_M = 150
# Calibrated on 3 known freeway and rail tiles against 12 ordinary properties:
# rail never fired on the ordinary ones; "freeway" also fires on wide streets, up to 4 times.
_MIN_FREEWAY_DETECTIONS = 6
_MIN_RAIL_DETECTIONS = 3


class VexcelUnavailable(FileNotFoundError):
    """Key is geofenced away from this location, or Vexcel has no imagery for it.

    A FileNotFoundError so the agent pipeline skips the candidate instead of crashing.
    """


def spaces_from_area(area_m2: float) -> int:
    return int(area_m2 // M2_PER_CAR)


def _key() -> str:
    key = os.getenv("VEXCEL_API_KEY")
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "VEXCEL_API_KEY":
                key = value.strip().strip('"')
    if not key:
        raise OSError("VEXCEL_API_KEY is not set")
    return key


def _coords(property_id: str) -> tuple[float, float]:
    if not _JOIN.exists():
        raise FileNotFoundError(f"{_JOIN} not found; run python data/join.py")
    import duckdb

    row = (
        duckdb.connect()
        .execute(
            f"SELECT lat, lon FROM read_parquet('{_JOIN.as_posix()}') WHERE property_id = ?",
            [property_id],
        )
        .fetchone()
    )
    if row is None:
        raise KeyError(property_id)
    return row[0], row[1]


def _request(method: str, path: str, key: str, *, missing_ok: bool = False, **kwargs):
    import requests

    for attempt in range(4):
        response = requests.request(
            method, f"{_API}/{path}", headers={"X-API-KEY": key}, timeout=300, **kwargs
        )
        if response.status_code != 429:
            break
        time.sleep(2**attempt)
    if response.status_code == 403:
        raise VexcelUnavailable(f"Vexcel /{path}: key not permitted here (geofencing)")
    if response.status_code == 404:
        if missing_ok:
            return None
        raise VexcelUnavailable(f"Vexcel /{path}: no imagery or data at this location")
    if not response.ok:
        raise RuntimeError(f"Vexcel /{path} failed: HTTP {response.status_code}")
    return response


def _square_wkt(lat: float, lon: float, half_m: float) -> str:
    dlat = half_m / _M_PER_DEG
    dlon = half_m / (_M_PER_DEG * math.cos(math.radians(lat)))
    w, e, s, n = lon - dlon, lon + dlon, lat - dlat, lat + dlat
    return f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"


def _parcel_wkt(lat: float, lon: float, key: str) -> str | None:
    from shapely import wkt
    from shapely.geometry import shape

    response = _request(
        "GET",
        "property/extract",
        key,
        missing_ok=True,
        params={
            "wkt": f"POINT({lon} {lat})",
            "srid": 4326,
            "layer": _LAYERS,
            "latest": "true",
            "include": "footprint-wkt",
        },
    )
    if response is None:
        return None
    geometry = response.json()["features"][0]["geometry"]
    return wkt.loads(geometry).wkt if isinstance(geometry, str) else shape(geometry).wkt


def _detect(
    area_wkt: str, labels: list[str], key: str, buffer_m: float = 0, masks: bool = False
) -> list[dict]:
    body = {
        "wkt": area_wkt,
        "srid": 4326,
        "buffer-meter": buffer_m,
        "images": [
            {
                "endpoint": "ortho/extract",
                "request": {
                    "layer": _LAYERS,
                    "srid": 4326,
                    "wkt": area_wkt,
                    "crop": "bounding_box",
                },
            }
        ],
        "model-input": {
            "elements": [
                {"label": x, "model": "sam3", "detection-threshold": 0.4}
                for x in labels
            ],
            "include": ["bbox", "confidence"]
            + (["pixel-mask", "pixel-bbox"] if masks else []),
        },
    }
    features = _request("POST", "elements/detect", key, json=body).json()["features"]
    return [
        {"label": f["properties"]["label"], **d}
        for f in features
        for d in f["properties"]["detections"]
    ]


def _mask_area_m2(detection: dict, lat: float) -> float:
    from PIL import Image
    from shapely import wkt

    min_lon, min_lat, max_lon, max_lat = wkt.loads(detection["bbox"]).bounds
    box_m2 = (
        (max_lon - min_lon)
        * _M_PER_DEG
        * math.cos(math.radians(lat))
        * (max_lat - min_lat)
        * _M_PER_DEG
    )
    mask = Image.open(io.BytesIO(base64.b64decode(detection["pixel-mask"]))).convert(
        "L"
    )
    white = mask.point(lambda p: 255 if p > 128 else 0).histogram()[255]
    return box_m2 * white / (mask.width * mask.height)


def _save_aerial(
    property_id: str, lat: float, lon: float, lot: dict | None, key: str
) -> str:
    drawing = []
    if lot is not None:
        from shapely import wkt

        min_lon, min_lat, max_lon, max_lat = wkt.loads(lot["bbox"]).bounds
        ring = [
            (min_lon, min_lat),
            (max_lon, min_lat),
            (max_lon, max_lat),
            (min_lon, max_lat),
        ]
        outline = ", ".join(f"{x} {y}" for x, y in ring + ring[:1])
        drawing = [
            {
                "wkt": f"POLYGON(({outline}))",
                "outline-color": "rgb(0,229,255)",
                "outline-width": 3,
            }
        ]
    response = _request(
        "POST",
        "ortho/extract",
        key,
        json={
            "wkt": _square_wkt(lat, lon, _NOISE_HALF_M),
            "srid": 4326,
            "layer": _LAYERS,
            "crop": "bounding_box",
            "image-format": "jpeg",
            "destination-dimensions": "1600,1600",
            "drawing": drawing,
        },
    )
    path = _CACHE / f"aerial_{property_id}.jpg"
    path.write_bytes(response.content)
    return path.relative_to(ROOT).as_posix()


def _walk_m(lot: dict, lat: float, lon: float) -> float:
    from shapely import wkt

    centre = wkt.loads(lot["bbox"]).centroid
    dx = (centre.x - lon) * _M_PER_DEG * math.cos(math.radians(lat))
    dy = (centre.y - lat) * _M_PER_DEG
    return round(math.hypot(dx, dy))


def plan_logistics(property_id: str, trucks: int = 3, cars: int = 30) -> Logistics:
    if USE_MOCKS:
        for entry in json.loads((ROOT / "mocks/logistics.json").read_text()):
            if entry["property_id"] == property_id:
                return Logistics(**entry)
        raise KeyError(property_id)

    cached = _CACHE / f"logistics_{property_id}.json"
    if cached.exists():
        return Logistics(**json.loads(cached.read_text()))

    lat, lon = _coords(property_id)
    key = _key()

    parcel = _parcel_wkt(lat, lon, key) or _square_wkt(lat, lon, _NO_PARCEL_HALF_M)
    lots = _detect(parcel, ["parking lot"], key, _PARKING_BUFFER_M, masks=True)
    areas = [_mask_area_m2(d, lat) for d in lots]
    total_cars = spaces_from_area(sum(areas))
    largest = lots[areas.index(max(areas))] if lots else None

    noise = {"freeway": 0, "railroad tracks": 0}
    for d in _detect(_square_wkt(lat, lon, _NOISE_HALF_M), list(noise), key):
        noise[d["label"]] += 1
    flags = []
    if noise["freeway"] >= _MIN_FREEWAY_DETECTIONS:
        flags.append(f"possible freeway within {_NOISE_HALF_M} m (imagery estimate)")
    if noise["railroad tracks"] >= _MIN_RAIL_DETECTIONS:
        flags.append(f"possible rail line within {_NOISE_HALF_M} m (imagery estimate)")
    if largest is None:
        flags.append(
            "no surface parking detected in imagery; garage and street parking unknown"
        )

    _CACHE.mkdir(parents=True, exist_ok=True)
    result = Logistics(
        property_id=property_id,
        truck_spaces=total_cars // CARS_PER_TRUCK,
        car_spaces=total_cars,
        parking_polygon=_polygon(largest),
        walk_m=_walk_m(largest, lat, lon) if largest else None,
        noise_flags=flags,
        aerial_image_path=_save_aerial(property_id, lat, lon, largest, key),
        estimated=True,
    )
    cached.write_text(result.model_dump_json())
    return result


def _polygon(lot: dict | None) -> list[list[float]]:
    if lot is None:
        return []
    from shapely import wkt

    min_lon, min_lat, max_lon, max_lat = wkt.loads(lot["bbox"]).bounds
    ring = [
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, max_lon),
        (max_lat, min_lon),
    ]
    return [[lat, lon] for lat, lon in ring + ring[:1]]


def aerial_image(property_id: str) -> str | None:
    return plan_logistics(property_id).aerial_image_path


def enough_parking(l: Logistics, trucks: int, cars: int) -> bool:
    return l.truck_spaces >= trucks and l.car_spaces >= cars
