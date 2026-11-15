"""Vexcel 3D Cities: the textured city mesh around a point, served through this server.

https://api.vexcelgroup.com/v2/api-docs/3d. A collection's tileset is OGC 3D Tiles 1.1 (Cesium
packaging): nested tilesets (`./tileset?zoom=..&tile-x=..&tile-y=..&childAOI=..`) down to glTF tiles
(`./tile?...`, Draco meshes, Basis textures, Earth-centred coordinates). The browser never sees the key:
it asks this server for a place, which walks the hierarchy to the most detailed tiles near the point,
and then fetches each tile through a proxy that accepts only these documented parameters. Every
tileset and tile is cached privately under cache/vexcel3d/, so a place costs provider calls once.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from data.vexcel_client import VEXCEL_BASE, ProviderError, VexcelClient

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "vexcel3d"
AOI = re.compile(r"[a-z0-9][a-z0-9-]{0,99}")
TARGET_ZOOM = 19  # ~75 m tiles in LA: detailed facades without hundreds of requests
MAX_TILES = 36


def tile_params(zoom, x, y, child_aoi) -> dict:
    zoom, x, y = int(zoom), int(x), int(y)
    if not (0 <= zoom <= 23 and 0 <= x < 2 ** zoom and 0 <= y < 2 ** zoom) or not AOI.fullmatch(str(child_aoi)):
        raise ValueError("Invalid 3D tile reference")
    return {"zoom": zoom, "tile-x": x, "tile-y": y, "childAOI": str(child_aoi)}


class City3D(VexcelClient):
    def _fetch(self, endpoint: str, params: dict, suffix: str) -> bytes:
        if endpoint not in ("3d/collections", "3d/tileset", "3d/tile"):
            raise ValueError("Unsupported Vexcel endpoint")
        key = hashlib.sha256(json.dumps([endpoint, sorted(params.items())]).encode()).hexdigest()[:24]
        path = CACHE / f"{endpoint.split('/')[1]}-{key}{suffix}"
        if path.is_file():
            return path.read_bytes()
        content = self._request("GET", VEXCEL_BASE + endpoint, params={**params, "api_key": self.api_key})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return content

    def collection(self, lat: float, lon: float) -> str | None:
        data = json.loads(self._fetch("3d/collections", {"wkt": f"POINT({lon:.4f} {lat:.4f})"}, ".json"))
        for feature in data.get("features", []):
            name = (feature.get("properties") or {}).get("collection")
            if name and AOI.fullmatch(name):
                return name
        return None

    def tileset(self, params: dict) -> dict:
        return json.loads(self._fetch("3d/tileset", params, ".json"))

    def tile(self, params: dict) -> bytes:
        content = self._fetch("3d/tile", tile_params(params["zoom"], params["tile-x"], params["tile-y"],
                                                     params["childAOI"]), ".glb")
        if content[:4] != b"glTF":
            raise ProviderError("Vexcel 3D tile is not a glTF binary")
        return content

    def place(self, lat: float, lon: float, radius_m: float = 140.0) -> dict:
        """Tiles at TARGET_ZOOM (or the deepest available) whose regions meet the box around the point."""
        collection = self.collection(lat, lon)
        if not collection:
            return {"collection": None, "tiles": []}
        dlat = radius_m / 111_320.0
        dlon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
        box = (math.radians(lon - dlon), math.radians(lat - dlat), math.radians(lon + dlon), math.radians(lat + dlat))
        root = self.tileset({"collection": collection, "layer": "3d-cities"})
        found: dict[int, list[dict]] = {}
        asset = root.get("asset", {}).get("extras", {})

        def meets(node):
            region = (node.get("boundingVolume") or {}).get("region")
            return (region is not None and region[0] <= box[2] and region[2] >= box[0]
                    and region[1] <= box[3] and region[3] >= box[1])

        def walk(node, depth=0):
            if depth > 40:
                return
            for child in node.get("children") or []:
                if not meets(child):
                    continue
                uri = (child.get("content") or {}).get("uri", "")
                parts = urlsplit(uri)
                query = dict(parse_qsl(parts.query))
                kind = parts.path.lstrip("./")
                if kind == "tile" and {"zoom", "tile-x", "tile-y", "childAOI"} <= set(query):
                    zoom = int(query["zoom"])
                    if zoom <= TARGET_ZOOM:
                        found.setdefault(zoom, []).append(tile_params(zoom, query["tile-x"], query["tile-y"],
                                                                      query["childAOI"]))
                elif kind == "tileset" and "zoom" in query and int(query["zoom"]) <= TARGET_ZOOM:
                    walk(self.tileset({k: query[k] for k in ("zoom", "tile-x", "tile-y", "childAOI") if k in query}
                                      | {"layer": "3d-cities"})["root"], depth + 1)
                walk(child, depth + 1)

        walk(root["root"])
        zoom = max(found) if found else None
        tiles = []
        for params in found.get(zoom, []):
            if params not in tiles:
                tiles.append(params)
        return {"collection": collection, "zoom": zoom, "tiles": tiles[:MAX_TILES],
                "capture": [asset.get("minCaptureDate"), asset.get("maxCaptureDate")],
                "copyright": "© Vexcel Imaging US Inc. · 3D Cities"}
