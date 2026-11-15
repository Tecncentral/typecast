"""Oblique search: find exteriors and urban outdoor places from a description, seen at 45 degrees.

1. Vexcel semantic search over ortho-tile embeddings inside a metro area preset (billable; capped).
2. Nearby hits are merged so each candidate is a distinct place.
3. One Vexcel oblique per place; the other three cardinal views load on request.
4. Terrain from Vexcel: bare-earth elevation along a 200 m cross (relief, steepest slope) and surface
   minus ground at the centre (how tall whatever stands there is).
5. One batched vision call scores every oblique against the request from what is visible.
Results, images and chat versions are cached privately under cache/oblique/<search id>/.

"Reimagine" edits one oblique with an image model from chat messages, each building on the last
version. Every edited image is labelled AI-imagined, not the real place. The image model and quality
come from TYPECAST_OBLIQUE_IMAGE_MODEL / TYPECAST_OBLIQUE_IMAGE_QUALITY: cheap by default for testing.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from pydantic import BaseModel, Field

from data.vexcel_client import ProviderError
from data.vexcel_oblique import DIRECTIONS, ObliqueClient, cross_points, terrain_summary

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "oblique"
LABEL = "AI-imagined, not the real place"
SEARCH_ID = re.compile(r"[0-9a-f]{16}")
MAX_PLACES = 8
MERGE_M = 140.0

# Metro presets inside the Vexcel collections this team can read (LA and Houston).
AREAS = {
    "la-downtown": ("Downtown LA", "Los Angeles", 34.0480, -118.2510, 3000),
    "la-arts-river": ("Arts District & LA River", "Los Angeles", 34.0330, -118.2290, 2500),
    "la-hollywood-griffith": ("Hollywood & Griffith Park", "Los Angeles", 34.1200, -118.3050, 4000),
    "la-westside-coast": ("Santa Monica & Venice", "Los Angeles", 34.0050, -118.4800, 3500),
    "la-port": ("San Pedro & the port", "Los Angeles", 33.7450, -118.2700, 4000),
    "hou-downtown": ("Downtown Houston", "Houston", 29.7580, -95.3650, 3000),
    "hou-bayou": ("Buffalo Bayou", "Houston", 29.7620, -95.3900, 3000),
    "hou-ship-channel": ("Ship Channel industrial", "Houston", 29.7350, -95.2600, 4000),
}


class PlaceScore(BaseModel):
    index: int
    score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=240)


class PlaceScores(BaseModel):
    results: list[PlaceScore]


def image_model() -> tuple[str, str]:
    """(model, quality or provider) of the configured image editor (agent/image_edit.py)."""
    from agent.image_edit import describe
    return describe()


def _distance_m(a: dict, b: dict) -> float:
    dy = (a["lat"] - b["lat"]) * 111_320.0
    dx = (a["lon"] - b["lon"]) * 111_320.0 * math.cos(math.radians(a["lat"]))
    return math.hypot(dx, dy)


def merge_places(tiles: list[dict], limit: int = MAX_PLACES) -> list[dict]:
    """Best tile of each cluster within MERGE_M metres, best first."""
    places: list[dict] = []
    for tile in sorted(tiles, key=lambda t: -t["score"]):
        if all(_distance_m(tile, place) > MERGE_M for place in places):
            places.append(dict(tile))
        if len(places) >= limit:
            break
    return places


def _search_id(query: str, area: str) -> str:
    return hashlib.sha256(f"{area}\n{' '.join(query.lower().split())}".encode()).hexdigest()[:16]


def _save_jpeg(content: bytes, path: Path) -> tuple[int, int]:
    with Image.open(io.BytesIO(content)) as image:
        image = image.convert("RGB")
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, "JPEG", quality=90)
        return image.size


def _data_url(path: Path, size: int = 768) -> str:
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((size, size))
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _first_oblique(client: ObliqueClient, place: dict, folder: Path, index: int) -> dict | None:
    for direction in DIRECTIONS:
        path = folder / f"{index}-{direction}.jpg"
        if path.is_file():
            return {"direction": direction, "path": path}
        try:
            _save_jpeg(client.oblique(place["lat"], place["lon"], direction), path)
            return {"direction": direction, "path": path}
        except (ProviderError, OSError, ValueError):
            continue
    return None


def _terrain(client: ObliqueClient, place: dict) -> dict:
    try:
        cross = cross_points(place["lat"], place["lon"])
        ground = client.elevations(cross, "dtm")
        summary = terrain_summary(ground)
        surface = client.elevations([(place["lat"], place["lon"])], "dsm")[0]
        summary["above_ground_m"] = round(surface - summary["ground_m"], 1)
        return {**summary, "status": "estimated"}
    except (ProviderError, ValueError, KeyError):
        return {"status": "unknown"}


def _score(query: str, places: list[dict]) -> None:
    from agent.models import get_provider
    provider = get_provider(vision=True)
    usable = [p for p in places if p.get("image")]
    if not usable or not provider.configured():
        return
    instructions = ("You are a film and photo location scout reviewing 45-degree aerial oblique photographs. "
                    "For each numbered image, score 0 to 1 how well the visible place matches the request, "
                    "judging only what is visible (surfaces, structures, vegetation, water, open space, access). "
                    "Give one short sentence naming the visible evidence; say what is unclear instead of guessing.")
    text = f"Request: {query}\n" + "\n".join(f"Image {i}: candidate {p['index']}" for i, p in enumerate(usable))
    try:
        result = provider.structured(instructions, text, PlaceScores,
                                     image_urls=[_data_url(ROOT / p["image"]["path"]) for p in usable])
    except Exception:  # noqa: BLE001 - the Vexcel order stands when the vision model is unavailable
        return
    for item in result.results:
        if 0 <= item.index < len(usable):
            usable[item.index]["match"] = {"score": round(item.score, 2), "reason": item.reason.strip(),
                                           "model": provider.model}


def search(query: str, area: str, *, client: ObliqueClient | None = None) -> dict:
    query = " ".join(str(query).split())[:300]
    if not query:
        raise ValueError("Describe the place to find.")
    if area not in AREAS:
        raise ValueError("Unknown area.")
    search_id = _search_id(query, area)
    folder = CACHE / search_id
    saved = folder / "search.json"
    if saved.is_file():
        return json.loads(saved.read_text(encoding="utf-8"))
    label, city, lat, lon, radius = AREAS[area]
    started = time.monotonic()
    client = client or ObliqueClient()
    places = merge_places(client.search_tiles(query, lat, lon, radius, k=16))

    def enrich(item):
        index, place = item
        worker = ObliqueClient()  # one HTTP session per thread
        found = _first_oblique(worker, place, folder, index)
        return {"index": index, "lat": round(place["lat"], 6), "lon": round(place["lon"], 6),
                "vexcel_score": round(place["score"], 3), "collection": place.get("collection"),
                "image": ({"direction": found["direction"], "path": str(found["path"].relative_to(ROOT))}
                          if found else None),
                "terrain": _terrain(worker, place)}

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(enrich, enumerate(places)))
    _score(query, results)
    results.sort(key=lambda r: (-(r.get("match") or {}).get("score", -1), -r["vexcel_score"]))
    for rank, result in enumerate(results, 1):
        result["rank"] = rank
    record = {"search_id": search_id, "query": query, "area": area, "area_label": label, "city": city,
              "center": [lat, lon], "radius_m": radius, "results": results,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "seconds": round(time.monotonic() - started, 1),
              "notes": ["Vexcel semantic search runs on top-down tiles; obliques show the same place at 45 degrees.",
                        "Terrain is Vexcel bare-earth and surface elevation, estimated; it does not establish "
                        "access, permission or clearance.",
                        "Coverage is the Vexcel metro collections for Los Angeles and Houston."]}
    folder.mkdir(parents=True, exist_ok=True)
    saved.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def _load(search_id: str) -> dict:
    if not SEARCH_ID.fullmatch(search_id or ""):
        raise KeyError(search_id)
    path = CACHE / search_id / "search.json"
    if not path.is_file():
        raise KeyError(search_id)
    return json.loads(path.read_text(encoding="utf-8"))


def view(search_id: str, index: int, direction: str) -> dict:
    """One cardinal oblique of a found place, fetched once and cached."""
    record = _load(search_id)
    place = next((r for r in record["results"] if r["index"] == index), None)
    if place is None or direction not in DIRECTIONS:
        raise KeyError(index)
    path = CACHE / search_id / f"{index}-{direction}.jpg"
    if not path.is_file():
        try:
            _save_jpeg(ObliqueClient().oblique(place["lat"], place["lon"], direction), path)
        except ProviderError as error:
            return {"direction": direction, "path": None, "reason": str(error)}
    return {"direction": direction, "path": str(path.relative_to(ROOT))}


def _chat_file(search_id: str, index: int, direction: str) -> Path:
    return CACHE / search_id / f"{index}-{direction}-chat.json"


def chat(search_id: str, index: int, direction: str) -> dict:
    path = _chat_file(search_id, index, direction)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"label": LABEL, "versions": []}


def reimagine(search_id: str, index: int, direction: str, message: str, *, client=None) -> dict:
    """Edit the latest version of one oblique from a chat message; returns the whole chat."""
    message = " ".join(str(message).split())[:600]
    if not message:
        raise ValueError("Say what to change.")
    base = view(search_id, index, direction)
    if not base.get("path"):
        raise KeyError(direction)
    record = _load(search_id)
    history = chat(search_id, index, direction)
    source = ROOT / (history["versions"][-1]["path"] if history["versions"] else base["path"])
    with Image.open(source) as image:
        image = image.convert("RGB").resize((1536, 1024), Image.LANCZOS)
        buf = io.BytesIO()
        image.save(buf, "PNG")
    from agent.building import CACHE as STRUCTURE_CACHE, prompt_facts
    import hashlib as _hashlib
    place = next((r for r in record["results"] if r["index"] == index), {})
    structure = STRUCTURE_CACHE / (_hashlib.sha256(f"{place.get('lat', 0):.6f},{place.get('lon', 0):.6f}".encode())
                                   .hexdigest()[:20] + ".json")
    facts = prompt_facts(json.loads(structure.read_text(encoding="utf-8"))) if structure.is_file() else ""
    prompt = (f"This is a real 45-degree aerial oblique photograph of a place in {record['city']}. {facts} "
              f"Change it as requested, photorealistic, keeping the same camera angle, lighting and every part "
              f"of the place the request does not mention. Request: {message}. No text, captions or logos.")
    from agent.image_edit import ImageEditError, edit_image
    try:
        content, model, quality = edit_image(buf.getvalue(), prompt, "1536x1024", client=client)
    except ImageEditError as error:
        raise ProviderError(str(error)) from None
    number = len(history["versions"]) + 1
    path = CACHE / search_id / f"{index}-{direction}-v{number}.jpg"
    with Image.open(io.BytesIO(content)) as edited:
        edited.convert("RGB").resize((1024, 683), Image.LANCZOS).save(path, "JPEG", quality=90)
    history["versions"].append({"path": str(path.relative_to(ROOT)), "message": message, "model": model,
                                "quality": quality, "created_at": datetime.now(timezone.utc).isoformat()})
    history["label"] = LABEL
    _chat_file(search_id, index, direction).write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history
