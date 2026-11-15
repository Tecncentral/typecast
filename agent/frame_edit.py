"""Edit a framed view of a scanned room from chat messages, each building on the last version.

The viewer sends the view once (the frame you see, real or AI-dressed), then only messages. Each
message is one image edit of the latest version, keeping the room's geometry, camera and light.
Every result is labelled AI-imagined set dressing, not the real room. Scan images go to the image
model only when TYPECAST_ALLOW_VISION_UPLOAD=1, the per-laptop switch for the sponsor's permission
(DECISIONS.md); the model and quality come from TYPECAST_OBLIQUE_IMAGE_MODEL/QUALITY (cheap by default).
Everything is cached privately under cache/frame-edits/<edit id>/.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "frame-edits"
LABEL = "AI-imagined set dressing, not the real room"
EDIT_ID = re.compile(r"[0-9a-f]{16}")
SHOT_ID = re.compile(r"[A-Za-z0-9._-]{1,440}")
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class EditUnavailable(RuntimeError):
    """The edit cannot run on this machine (upload permission or configuration)."""


def _folder(edit_id: str) -> Path:
    if not EDIT_ID.fullmatch(edit_id or ""):
        raise KeyError(edit_id)
    return CACHE / edit_id


def _decode(data_url: str) -> Image.Image:
    match = re.fullmatch(r"data:image/(jpeg|png);base64,([A-Za-z0-9+/=]+)", data_url or "")
    if not match:
        raise ValueError("Send the view as a JPEG or PNG data URL.")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("The view image is not valid base64.") from None
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("The view image is too large.")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (OSError, Image.DecompressionBombError):
        raise ValueError("The view image could not be read.") from None
    if not (64 <= image.width <= 4096 and 64 <= image.height <= 4096):
        raise ValueError("The view image has an unexpected size.")
    return image.convert("RGB")


def _size_for(width: int, height: int) -> str:
    ratio = width / height
    return "1536x1024" if ratio >= 1.25 else "1024x1536" if ratio <= 0.8 else "1024x1024"


def _letterbox(width: int, height: int, size: str) -> tuple[tuple[int, int], tuple[int, int, int, int]]:
    """The model's canvas and where the view sits on it, scaled without distortion (a 2.39:1 frame
    gets black bars on a 3:2 canvas instead of being stretched)."""
    tw, th = (int(v) for v in size.split("x"))
    scale = min(tw / width, th / height)
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    x, y = (tw - w) // 2, (th - h) // 2
    return (tw, th), (x, y, x + w, y + h)


def chat(edit_id: str) -> dict:
    path = _folder(edit_id) / "chat.json"
    if not path.is_file():
        raise KeyError(edit_id)
    return json.loads(path.read_text(encoding="utf-8"))


def edit(message: str, *, edit_id: str | None = None, shot_id: str | None = None, address: str = "",
         image: str | None = None, client=None) -> dict:
    message = " ".join(str(message).split())[:600]
    if not message:
        raise ValueError("Say what to change.")
    if os.getenv("TYPECAST_ALLOW_VISION_UPLOAD", "").strip() != "1":
        raise EditUnavailable("Scan images are not sent to the image model on this machine. "
                              "TYPECAST_ALLOW_VISION_UPLOAD=1 enables the sponsor-permitted uploads.")
    if edit_id:
        history = chat(edit_id)
        folder = _folder(edit_id)
    else:
        if not SHOT_ID.fullmatch(shot_id or ""):
            raise ValueError("Unknown scan view.")
        base = _decode(image)
        edit_id = secrets.token_hex(8)
        folder = _folder(edit_id)
        folder.mkdir(parents=True, exist_ok=True)
        base.save(folder / "base.jpg", "JPEG", quality=92)
        history = {"edit_id": edit_id, "shot_id": shot_id, "address": str(address)[:120], "label": LABEL,
                   "base": str((folder / "base.jpg").relative_to(ROOT)), "size": [base.width, base.height],
                   "versions": []}
    source = ROOT / (history["versions"][-1]["path"] if history["versions"] else history["base"])
    width, height = history["size"]
    size = _size_for(width, height)
    canvas_size, box = _letterbox(width, height, size)
    letterboxed = box != (0, 0, *canvas_size)
    with Image.open(source) as current:
        canvas = Image.new("RGB", canvas_size, (0, 0, 0))
        canvas.paste(current.convert("RGB").resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS), box[:2])
        buf = io.BytesIO()
        canvas.save(buf, "PNG")
    prompt = ("This is a photograph of a real, scanned room, framed by a film director. Change it as requested, "
              "photorealistic, keeping the same camera position, lens, room geometry (walls, windows, doors, "
              "columns, ceiling, floor) and natural light, and every part of the room the request does not "
              f"mention. Request: {message}. No people unless asked. No text, captions or logos."
              + (" The black bars are letterboxing outside the frame: keep them plain black." if letterboxed else ""))
    from agent.image_edit import ImageEditError, edit_image
    try:
        content, model, quality = edit_image(buf.getvalue(), prompt, size, client=client)
    except ImageEditError as error:
        raise EditUnavailable(str(error)) from None
    number = len(history["versions"]) + 1
    path = folder / f"v{number}.jpg"
    with Image.open(io.BytesIO(content)) as edited:
        frame = edited.convert("RGB").resize(canvas_size, Image.LANCZOS).crop(box)
        frame.resize((width, height), Image.LANCZOS).save(path, "JPEG", quality=92)
    history["versions"].append({"path": str(path.relative_to(ROOT)), "message": message, "model": model,
                                "quality": quality, "created_at": datetime.now(timezone.utc).isoformat()})
    (folder / "chat.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history
