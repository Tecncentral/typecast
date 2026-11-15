"""Strike: empty a real scanned room, the way an art department strikes a location before dressing it.

Idea from Matterport's defurnishing research (Slavcheva et al., "An Empty Room is All We Want",
CVPR 2024 workshops, arXiv:2405.03682): inpaint furniture away, then blend so only the furniture
pixels change. We have no fine-tuned model, so:
  1. an OpenAI image edit removes movable furniture from one horizon face (1024 px);
  2. a difference mask keeps every unchanged pixel from the real 2048 px scan, so walls, windows
     and the view stay the real photograph (the paper's blending idea);
  3. the OpenAI Decisions API checks, as calibrated yes/no probabilities, that the architecture
     was kept and the furniture is gone. Faces that fail are never served.

Everything produced is AI-edited and labelled that way. Output stays in cache/strike/ (git-ignored).
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import pathlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import numpy as np
import requests
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = "AI-edited: furniture removed, not the real room"
OPENAI = "https://api.openai.com/v1"
EDIT_MODEL = os.getenv("TYPECAST_STRIKE_MODEL", "gpt-image-2.6-flare")
DECISION_MODEL = os.getenv("TYPECAST_DECISION_MODEL", "gpt-6-luna")
KEEP_ARCHITECTURE_MIN = 0.7      # Decisions API probability needed to serve a struck face
FURNISHED_MIN = 0.5              # below this a face is treated as already empty and left alone
MAX_CHANGED = 0.65               # an edit that repaints most of the frame is rejected

PROMPT = ("Remove all furniture and movable objects from this room: sofas, chairs, stools, tables, beds, rugs, "
          "lamps, plants, decor, art, cushions, boxes and pallets. Keep everything architectural exactly as it "
          "is: walls, windows and their frames, the view outside, doors, the floor material, the ceiling, "
          "columns, built-in cabinets and counters, light fixtures and the lighting. Fill the cleared areas "
          "with the same floor and wall so the room looks empty and unfurnished, photographed the same way. "
          "Do not add anything.")

Q_FURNISHED = "Does this room contain movable furniture or loose objects such as sofas, chairs, tables, beds, rugs, boxes or decor?"
Q_KEPT = ("The first image is a real room; the second is an edited copy. Ignoring furniture and loose objects, "
          "are the walls, windows, window frames, doors, floor material, ceiling, columns and built-in fixtures "
          "in the second image the same as in the first, in the same places?")
Q_EMPTY = "Is the second image an empty room with no movable furniture or loose objects left in it?"


class StrikeError(RuntimeError):
    """Sanitized: never contains the key or image data."""


def strike_dir() -> pathlib.Path:
    return pathlib.Path(os.getenv("TYPECAST_STRIKE_DIR", str(ROOT / "cache" / "strike")))


def _safe(part: str) -> str:
    return "".join(ch for ch in part if ch.isalnum() or ch in "-_")[:80]


def scan_point_dir(model_id: str, sweep_id: str) -> pathlib.Path:
    return strike_dir() / _safe(model_id) / _safe(sweep_id)


def ledger(entry: dict) -> None:
    path = strike_dir() / "ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), **entry}, sort_keys=True) + "\n")


# ---------------------------------------------------------------- blending (offline, testable)
def _soft(mask: Image.Image, radius: float) -> Image.Image:
    return mask.filter(ImageFilter.GaussianBlur(radius))


def change_mask(original: Image.Image, edited: Image.Image) -> np.ndarray:
    """Alpha in [0, 1] where the edit really changed the room, at the edited image's size.

    Generative edits shift colour and noise slightly everywhere, so the difference is low-passed,
    thresholded above the frame's own background change, cleaned with an open/close, grown a little
    and feathered. Pixels outside the mask keep the real photograph.
    """
    size = edited.size
    a = np.asarray(original.convert("RGB").resize(size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(2)), dtype=np.float32)
    b = np.asarray(edited.convert("RGB").filter(ImageFilter.GaussianBlur(2)), dtype=np.float32)
    diff = np.sqrt(((a - b) ** 2).sum(axis=2)) / (255 * math.sqrt(3))
    background = float(np.percentile(diff, 50))
    threshold = max(0.05, background * 2.5)
    binary = Image.fromarray(((diff > threshold) * 255).astype(np.uint8))
    k = max(3, (size[0] // 256) * 2 + 1)                                   # odd kernel, ~9 px at 1024
    binary = binary.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))  # open: drop speckle
    for _ in range(2):                                                                 # close: bridge gaps
        binary = binary.filter(ImageFilter.MaxFilter(3 * k)).filter(ImageFilter.MinFilter(3 * k))
    binary = _fill_holes(binary)          # a removed rug can match the new floor inside its outline
    for _ in range(3):                    # grow past furniture edges, shadows and fringes
        binary = binary.filter(ImageFilter.MaxFilter(k))
    return np.asarray(_soft(binary, size[0] / 128), dtype=np.float32) / 255.0


def _fill_holes(binary: Image.Image) -> Image.Image:
    """Set every background pixel that cannot reach the frame border to foreground."""
    from PIL import ImageDraw
    work = binary.point(lambda v: 0 if v > 127 else 255)          # background = 255
    w, h = work.size
    px = work.load()
    for x, y in [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + \
                [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]:
        if px[x, y] == 255:
            ImageDraw.floodfill(work, (x, y), 128)
    arr = np.asarray(work)
    return Image.fromarray(np.where(arr == 128, 0, 255).astype(np.uint8))


def blend(original: Image.Image, edited: Image.Image) -> tuple[Image.Image, float]:
    """Real photograph everywhere except where furniture was removed; returns (image, changed share)."""
    alpha = change_mask(original, edited)
    full = original.convert("RGB")
    mask = Image.fromarray((alpha * 255).astype(np.uint8)).resize(full.size, Image.BILINEAR)
    up = edited.convert("RGB").resize(full.size, Image.LANCZOS)
    out = Image.composite(up, full, mask)
    return out, float((alpha > 0.5).mean())


# ---------------------------------------------------------------- OpenAI clients
def _jpeg_data_url(image: Image.Image, side: int = 768) -> str:
    buf = io.BytesIO()
    image.convert("RGB").resize((side, side), Image.LANCZOS).save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@dataclass
class OpenAIClient:
    api_key: Optional[str] = None
    session: Any = None
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self):
        self.api_key = (self.api_key or os.getenv("VISION_API_KEY") or os.getenv("LLM_API_KEY")
                        or os.getenv("OPENAI_API_KEY") or "").strip()
        if not self.api_key:
            raise StrikeError("No OpenAI key is configured (VISION_API_KEY or LLM_API_KEY)")
        self.session = self.session or requests.Session()

    def _post(self, path: str, *, json_body=None, files=None, data=None, timeout=300) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for attempt in range(3):
            try:
                r = self.session.post(OPENAI + path, headers=headers, json=json_body, files=files, data=data,
                                      timeout=timeout, allow_redirects=False)
            except requests.RequestException as error:
                raise StrikeError(f"OpenAI network failure ({type(error).__name__})") from None
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                self.sleep(4 * (attempt + 1))
                continue
            if r.status_code >= 300:
                try:
                    message = str((r.json().get("error") or {}).get("message", ""))[:240]
                except ValueError:
                    message = ""
                raise StrikeError(f"OpenAI HTTP {r.status_code} on {path}: {message.replace(self.api_key, '<key>')}")
            try:
                return r.json()
            except ValueError:
                raise StrikeError("OpenAI returned non-JSON") from None
        raise StrikeError(f"OpenAI kept failing on {path}")

    def remove_furniture(self, image: Image.Image) -> Image.Image:
        buf = io.BytesIO()
        image.convert("RGB").resize((1024, 1024), Image.LANCZOS).save(buf, "PNG")
        body = self._post("/images/edits", files={"image": ("room.png", buf.getvalue(), "image/png")},
                          data={"model": EDIT_MODEL, "prompt": PROMPT, "size": "1024x1024", "quality": "high", "n": "1"})
        try:
            return Image.open(io.BytesIO(base64.b64decode(body["data"][0]["b64_json"]))).convert("RGB")
        except (KeyError, IndexError, TypeError, ValueError, OSError):
            raise StrikeError("The image edit returned no image") from None

    def predicates(self, images: list[Image.Image], questions: list[str]) -> list[float]:
        """Calibrated yes-probabilities from the Decisions API, one per question."""
        content = [{"type": "input_image", "image_url": _jpeg_data_url(im)} for im in images]
        body = self._post("/decisions", json_body={
            "model": DECISION_MODEL,
            "input": [{"type": "message", "role": "user", "content": content}],
            "questions": [{"type": "predicate", "instructions": q} for q in questions],
        }, timeout=120)
        answers = body.get("answers") or []
        out = []
        for answer in answers[:len(questions)]:
            p = answer.get("probability") if isinstance(answer, dict) else None
            out.append(float(p) if isinstance(p, (int, float)) and math.isfinite(p) and 0 <= p <= 1 else float("nan"))
        if len(out) != len(questions):
            raise StrikeError("The Decisions API returned an incomplete answer set")
        return out


# ---------------------------------------------------------------- pipeline
def strike_face(original: Image.Image, client: OpenAIClient, *, force: bool = False) -> dict:
    """One horizon face: decide, edit, blend, check. Returns a record; `image` only when accepted."""
    (furnished,) = client.predicates([original], [Q_FURNISHED])
    if furnished < FURNISHED_MIN and not force:
        return {"status": "already_empty", "furnished_p": round(furnished, 3)}
    edited = client.remove_furniture(original)
    struck, changed = blend(original, edited)
    kept, empty = client.predicates([original, struck], [Q_KEPT, Q_EMPTY])
    accepted = kept >= KEEP_ARCHITECTURE_MIN and changed <= MAX_CHANGED
    reason = None if accepted else ("architecture_changed" if kept < KEEP_ARCHITECTURE_MIN else "edit_too_large")
    return {"status": "struck" if accepted else "rejected", "reason": reason, "image": struck if accepted else None,
            "furnished_p": round(furnished, 3), "architecture_kept_p": round(kept, 3),
            "empty_p": round(empty, 3), "changed_share": round(changed, 3)}


def strike_scan_point(sweep: dict, client: OpenAIClient, *, log: Callable[[str], None] = print,
                      force: bool = False, retry_rejected: bool = False) -> dict:
    """All horizon faces at one scan point -> cache/strike/<model>/<sweep>/strike.json + struck_<heading>.jpg.

    With retry_rejected, faces already struck or empty are kept and only rejected faces get one new edit.
    """
    out = scan_point_dir(sweep["model_id"], sweep["sweep_id"])
    out.mkdir(parents=True, exist_ok=True)
    previous = {}
    if retry_rejected and (out / "strike.json").is_file():
        try:
            previous = {f["heading_deg"]: f for f in json.loads((out / "strike.json").read_text(encoding="utf-8"))["faces"]}
        except (OSError, ValueError, KeyError, TypeError):
            previous = {}
    faces = []
    for face in sorted(sweep["faces"], key=lambda f: f["heading_deg"]):
        heading = int(round(float(face["heading_deg"]))) % 360
        if previous.get(heading, {}).get("status") in {"struck", "already_empty"}:
            faces.append(previous[heading])
            continue
        # A rejected face was already judged furnished, so it goes straight to a new edit.
        face_force = force or (retry_rejected and previous.get(heading, {}).get("status") == "rejected")
        path = ROOT / str(face["image_path"]).lstrip("/")
        if not path.is_file():
            faces.append({"heading_deg": heading, "status": "missing_source"})
            continue
        started = time.time()
        result = strike_face(Image.open(path).convert("RGB"), client, force=face_force)
        image = result.pop("image", None)
        record = {"heading_deg": heading, **result, "seconds": round(time.time() - started, 1)}
        if image is not None:
            name = f"struck_{heading:03d}.jpg"
            tmp = out / (name + ".part")
            image.save(tmp, "JPEG", quality=90)
            tmp.replace(out / name)
            record["struck"] = name
        faces.append(record)
        ledger({"model": EDIT_MODEL if result["status"] != "already_empty" else None, "status": result["status"],
                "heading": heading, "scan_point": f"{_safe(sweep['model_id'])[:4]}…/{_safe(sweep['sweep_id'])[:4]}…"})
        log(f"face {heading:3d}°: {result['status']}"
            + (f" (kept {result.get('architecture_kept_p')}, empty {result.get('empty_p')}, changed {result.get('changed_share')})"
               if result["status"] != "already_empty" else f" (furnished p={result['furnished_p']})"))
    record = {"label": LABEL, "edit_model": EDIT_MODEL, "decision_model": DECISION_MODEL,
              "created_at": datetime.now(timezone.utc).isoformat(), "model_id": sweep["model_id"],
              "sweep_id": sweep["sweep_id"], "faces": faces,
              "method": "OpenAI image edit + change-mask blend into the real scan + Decisions API checks"}
    (out / "strike.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def load_strike(model_id: str, sweep_id: str) -> Optional[dict]:
    """Validated record for exactly this scan point, or None. Cache contents are untrusted."""
    if not model_id or not sweep_id or _safe(model_id) != model_id or _safe(sweep_id) != sweep_id:
        return None
    directory = scan_point_dir(model_id, sweep_id)
    path = directory / "strike.json"
    try:
        if directory.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000:
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(record, dict) or record.get("model_id") != model_id or record.get("sweep_id") != sweep_id:
        return None
    faces = []
    for face in record.get("faces") or []:
        if not isinstance(face, dict) or not isinstance(face.get("heading_deg"), int):
            continue
        name = face.get("struck")
        ok = (isinstance(name, str) and name == f"struck_{face['heading_deg'] % 360:03d}.jpg"
              and (directory / name).is_file() and not (directory / name).is_symlink())
        num = lambda k: face.get(k) if isinstance(face.get(k), (int, float)) and math.isfinite(face.get(k)) else None
        faces.append({"heading_deg": face["heading_deg"] % 360,
                      "status": face.get("status") if face.get("status") in {"struck", "rejected", "already_empty", "missing_source"} else "unknown",
                      "struck_url": f"/cache/strike/{model_id}/{sweep_id}/{name}" if ok and face.get("status") == "struck" else None,
                      "architecture_kept_p": num("architecture_kept_p"), "empty_p": num("empty_p"),
                      "furnished_p": num("furnished_p"), "changed_share": num("changed_share")})
    return {"label": LABEL, "faces": faces,
            "edit_model": record.get("edit_model") if isinstance(record.get("edit_model"), str) else None,
            "created_at": str(record.get("created_at"))[:40] if record.get("created_at") else None}
