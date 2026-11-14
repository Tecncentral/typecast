"""Documented Vexcel v2/OSM requests with bounded payloads and private caches.

Official schemas read 2026-11-14:
https://api.vexcelgroup.com/v2/api-docs/{ortho,property,embedding}
https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL
Semantic search returns tile footprints, NOT parking lot boundaries.
"""
from __future__ import annotations

import io
import json
import math
import os
from pathlib import Path
import tempfile

from PIL import Image
import requests

VEXCEL_BASE = "https://api.vexcelgroup.com/v2/"
# Listed public instance in the OSM API docs. The German public instance
# returned 406 during verification; do not hammer or silently rotate servers.
OVERPASS_URL = "https://overpass.private.coffee/api/interpreter"
MAX_BYTES = 20 * 1024 * 1024


class ProviderError(RuntimeError):
    """Sanitized errors deliberately exclude URL, provider body and credentials."""


def atomic_json(path: Path, value):
    atomic_bytes(path, json.dumps(value, indent=2, allow_nan=False).encode())


def atomic_bytes(path: Path, value: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".tmp-", delete=False) as output:
        temporary = Path(output.name)
        output.write(value)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def mercator_extent(lat: float, lon: float, width_m: float = 400):
    radius = 6_378_137.0
    x = radius * math.radians(lon)
    y = radius * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    half = width_m / (2 * math.cos(math.radians(lat)))
    return [x - half, y - half, x + half, y + half]


def overpass_query(lat: float, lon: float) -> str:
    if not (-85 <= lat <= 85 and -180 <= lon <= 180):
        raise ValueError("Invalid property coordinates")
    return f'''[out:json][timeout:30];(
      nwr(around:200,{lat},{lon})[amenity=parking];
      way(around:200,{lat},{lon})[building];
      node(around:200,{lat},{lon})[entrance];
      way(around:250,{lat},{lon})[highway~"^(footway|pedestrian|path|steps|living_street)$"];
      way(around:210,{lat},{lon})[highway~"^motorway(_link)?$"];
      way(around:310,{lat},{lon})[railway~"^(rail|light_rail|narrow_gauge|tram)$"];
      nwr(around:3050,{lat},{lon})[aeroway~"^(aerodrome|runway)$"];
    );out body geom;'''


class VexcelClient:
    def __init__(self, api_key: str | None = None, session=None):
        self.api_key = api_key or os.getenv("VEXCEL_API_KEY")
        if not self.api_key:
            raise ProviderError("Vexcel key missing; set VEXCEL_API_KEY privately")
        self.session = session or requests.Session()

    def _get(self, endpoint: str, parameters: dict) -> bytes:
        # Only fixed documented endpoints can receive the key. Redirects are
        # disabled so credentials cannot leak into an unexpected destination.
        if endpoint not in {"property/extract", "ortho/extract", "embedding/extract"}:
            raise ValueError("Unsupported Vexcel endpoint")
        return self._request("GET", VEXCEL_BASE + endpoint,
                             params={**parameters, "api_key": self.api_key})

    def _request(self, method: str, url: str, **kwargs) -> bytes:
        try:
            response = self.session.request(method, url, timeout=(10, 55),
                                            allow_redirects=False, stream=True,
                                            headers={"User-Agent": "Typecast-HackPrinceton/1.0"}, **kwargs)
            with response:
                if response.status_code != 200:
                    raise ProviderError(f"{'Vexcel' if url.startswith(VEXCEL_BASE) else 'OSM'} HTTP {response.status_code}")
                content = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    content.extend(chunk)
                    if len(content) > MAX_BYTES:
                        raise ProviderError("Provider response exceeds private cache size limit")
                return bytes(content)
        except requests.RequestException as error:
            # Never propagate requests' exception text: it includes credential
            # bearing query URLs on network failures.
            raise ProviderError(f"Provider network failure ({type(error).__name__})") from None

    def property(self, lat: float, lon: float):
        data = self._get("property/extract", {"wkt": f"POINT({lon} {lat})", "srid": "4326",
            "unit-system": "metric", "include": "hardscapes,structures,metadata", "latest": "true",
            "total-records": 1, "page-size": 1})
        return decode_json(data, "features")

    def aerial(self, lat: float, lon: float):
        extent = mercator_extent(lat, lon)
        west, south, east, north = extent
        wkt = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
        content = self._get("ortho/extract", {"layer": "urban,urban-r,urban-g,wide-area", "wkt": wkt,
            "srid": "3857", "destination-dimensions": "1024,1024,fit", "crop": "bounding_box",
            "image-format": "png", "attribution": "true", "include": "estimate-date"})
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format != "PNG" or image.size != (1024, 1024):
                    raise ProviderError("Unexpected Vexcel aerial format or dimensions")
                image.verify()
        except (OSError, ValueError):
            raise ProviderError("Vexcel aerial is not a valid image") from None
        return content, extent

    def semantic_search(self, lat: float, lon: float):
        content = self._get("embedding/extract", {"search-text": "surface parking lot",
            "wkt": f"POINT({lon} {lat})", "buffer-meter": 150, "source.product-type": "final-ortho",
            "total-records": 5, "page-size": 5, "include": "geometry,score,collection,product-type"})
        return decode_json(content, "features")

    def parking_detection(self, lat: float, lon: float):
        # Request actual segmentation masks. The returned GeoJSON geometry and
        # bbox alone describe bounding boxes, not the segmented parking outline.
        wkt = f"POINT({lon} {lat})"
        body = {"wkt": wkt, "srid": 4326, "buffer-meter": 150,
                "images": [{"endpoint": "ortho/extract", "request": {
                    "layer": "urban,urban-r,urban-g,wide-area", "wkt": wkt,
                    "srid": 4326, "bbox-dimensions": "400,400",
                    "destination-dimensions": "1024,1024,fit"}}],
                "model-input": {"elements": [{"label": "parking lot", "model": "sam3",
                    "detection-threshold": 0.5}],
                    "include": ["geometry", "pixel-mask", "pixel-bbox", "bbox", "confidence"]}}
        content = self._request("POST", VEXCEL_BASE + "elements/detect",
                                params={"api_key": self.api_key}, json=body)
        return decode_json(content, "features")

    def osm(self, lat: float, lon: float):
        # No authentication header or Vexcel key is passed to OSM.
        data = decode_json(self._request("POST", OVERPASS_URL, data={"data": overpass_query(lat, lon)}), "elements")
        if data.get("remark"):
            raise ProviderError("OSM query returned partial results")
        return data


def decode_json(content: bytes, expected_key: str):
    try:
        value = json.loads(content)
        if not isinstance(value, dict) or not isinstance(value.get(expected_key), list):
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise ProviderError("Unexpected provider JSON response") from None
