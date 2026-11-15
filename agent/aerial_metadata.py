"""Read the small, validated georeferencing subset of a private aerial cache."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

from PIL import Image


class AerialMetadataUnavailable(FileNotFoundError):
    """Missing or invalid cached metadata; callers may return a generic 404."""


def _numbers(value, length):
    if (not isinstance(value, list) or len(value) != length
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError
    return value


def read_aerial_metadata(property_id: str, cache_root: str | Path) -> dict:
    """Return only image georeferencing, never provider records or logistics.

    ``cache_root`` is the application's trusted cache directory. IDs, cache
    symlinks, source-coordinate bindings and the actual PNG are validated before
    returning a subset. Every failure uses the same path-free error contract.
    """
    try:
        if not isinstance(property_id, str) or not re.fullmatch(r"[0-9]{1,12}", property_id):
            raise ValueError
        root = Path(cache_root).resolve()
        directory = root / "vexcel" / property_id
        # Reject symlinked cache directories and files, including aliases within
        # the cache: the allowlist identifies one exact property generation.
        if directory.resolve(strict=True) != directory:
            raise ValueError

        def cache_file(name):
            path = directory / name
            if path.resolve(strict=True) != path or not path.is_file():
                raise ValueError
            return path

        extent = _numbers(json.loads(cache_file("aerial-extent.json").read_text()), 4)
        west, south, east, north = extent
        if west >= east or south >= north:
            raise ValueError
        coordinates = _numbers(json.loads(cache_file("source-coordinates.json").read_text()), 2)
        lat, lon = coordinates
        if not (-85 <= lat <= 85 and -180 <= lon <= 180):
            raise ValueError
        record = json.loads(cache_file("logistics.json").read_text())
        if (type(record.get("schema_version")) is not int or record["schema_version"] != 1
                or record.get("property_id") != property_id
                or record.get("logistics", {}).get("property_id") != property_id
                or _numbers(record.get("coordinates"), 2) != coordinates):
            raise ValueError
        # This cache format is a north-up Mercator extract centred at the bound
        # property coordinate. Reject stale extents from another property.
        radius = 6_378_137.0
        x = radius * math.radians(lon)
        y = radius * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
        if not (math.isclose(x, west / 2 + east / 2, abs_tol=.01, rel_tol=0)
                and math.isclose(y, south / 2 + north / 2, abs_tol=.01, rel_tol=0)):
            raise ValueError
        with Image.open(cache_file("aerial.png")) as image:
            width, height = image.size
            if image.format != "PNG" or not (0 < width * height <= 16_777_216):
                raise ValueError
            image.verify()
        return {"property_id": property_id, "crs": "EPSG:3857", "extent": extent,
                "width": width, "height": height,
                "image_path": f"cache/vexcel/{property_id}/aerial.png",
                "coordinates": coordinates}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RuntimeError,
            Image.DecompressionBombError):
        raise AerialMetadataUnavailable("Aerial metadata unavailable.") from None
