"""Explicit, single-frame image edits. Never replace source evidence or 3D geometry."""
from __future__ import annotations
import base64
import io
import os
import threading
import uuid
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageDraw

from index.search import ROOT, get_active_index, get_shot, IndexUnavailableError, ShotNotFoundError

LABEL = "AI-IMAGINED SCENE - NOT THE REAL ROOM - FIT UNVERIFIED"
_GATE = threading.Lock()


def render_scene(shot_id: str, instruction: str):
    if os.environ.get("TYPECAST_ALLOW_VISION_UPLOAD", "").lower() not in {"1", "true", "yes"}:
        raise HTTPException(503, "Image customization requires the existing TYPECAST_ALLOW_VISION_UPLOAD opt-in and a configured image provider")
    try:
        active = get_active_index()
    except IndexUnavailableError:
        raise HTTPException(503, "Real retrieval index unavailable") from None
    if getattr(active, "is_mock", True):
        raise HTTPException(409, "Image customization needs a real indexed frame; mock fixtures are not sent")
    try:
        shot = get_shot(shot_id)
        source = (ROOT / shot.image_path.lstrip("/")).resolve()
        source.relative_to((ROOT / "cache" / "views").resolve())
        if not source.is_file():
            raise ValueError("Missing indexed image")
    except (ValueError, KeyError, FileNotFoundError, ShotNotFoundError):
        raise HTTPException(404, "Indexed source frame unavailable") from None
    if not _GATE.acquire(blocking=False):
        raise HTTPException(429, "Another image is being generated; wait before requesting another")
    try:
        from strike.core import OpenAIClient, StrikeError, EDIT_MODEL
        try:
            client = OpenAIClient()
        except StrikeError:
            raise HTTPException(503, "Configured image provider unavailable") from None
        with Image.open(source) as original:
            image = original.convert("RGB")
            image.thumbnail((1536, 1536))
            buf = io.BytesIO()
            image.save(buf, "PNG")
        prompt = ("Create a film director's imagined scene customization of this exact source room. "
                  "Preserve the camera position, walls, doors, windows and architecture as much as possible. "
                  "Furniture, props, character stand-ins, lighting, wardrobe, era and mood may change as requested. "
                  "This is concept art, never evidence of physical fit. No captions, logos or watermarks. "
                  "Director request: " + instruction)
        try:
            body = client._post("/images/edits", files={"image": ("source.png", buf.getvalue(), "image/png")},
                                data={"model":os.environ.get("TYPECAST_DRESS_MODEL", EDIT_MODEL),
                                      "prompt":prompt, "size":"1024x1024", "quality":"medium", "n":"1"}, timeout=300)
            raw = base64.b64decode(body["data"][0]["b64_json"], validate=True)
            with Image.open(io.BytesIO(raw)) as generated:
                rendered = generated.convert("RGB")
            if max(rendered.size) > 4096:
                raise ValueError("Image too large")
        except (StrikeError, ValueError, KeyError, IndexError, TypeError, OSError):
            raise HTTPException(502, "Image provider did not return a usable preview; original retained") from None
        draw = ImageDraw.Draw(rendered)
        draw.rectangle((0,0,rendered.width,34),fill="#101212")
        draw.text((10,10), LABEL, fill="#ffffff")
        output = ROOT / "cache" / "customizations"
        if output.is_symlink():
            raise HTTPException(503, "Preview cache unavailable")
        output.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        rendered.save(output / f"{token}.png")
        return {"image_url":f"/api/production/customization/{token}.png", "source_shot_id":shot_id,
                "label":LABEL, "kind":"imagined-single-frame", "geometry_verified":False}
    finally:
        _GATE.release()


def image_path(token: str) -> Path:
    if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
        raise HTTPException(404, "Preview not found")
    path = ROOT / "cache" / "customizations" / f"{token}.png"
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise HTTPException(404, "Preview not found")
    return path
