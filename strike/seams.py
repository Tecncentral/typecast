"""Repair the joins between AI-dressed walls, so the dressed room has no visible seams.

  python -m strike.seams --scene la-warehouse-handoff        # every 4-wall v2 set of that scene
  python -m strike.seams --set <model_id>/<sweep_id>         # one scan point

The viewer shows four horizon walls (faces 0, 90, 180, 270) and switches between them at the 45-degree
joins. Each wall is dressed separately, so a pallet stack can end at a join or a floor line can jump.
For every join between two dressed walls:
  1. render a 100-degree view centred on the join from the dressed walls;
  2. one masked image edit repaints only a +-10 degree strip across the join so objects and lines continue;
  3. register the output to its input, then feather it in with a cosine ramp (no hard edge of its own);
  4. the Decisions API must say the join no longer shows a seam and the architecture still matches the real
     scan; otherwise the join is left as it was;
  5. the strip is resampled back into both walls with the same feather.
The previous set is archived beside it, never deleted. Labels are unchanged: AI-imagined, not the real room.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
from dotenv import load_dotenv
from PIL import Image

from strike import pano
from strike.core import Q_KEPT, ROOT, OpenAIClient, StrikeError, ledger
from strike.dress import BRIEFS, DRESS_MODEL, KEPT_MIN, worlds_dressed_dir

VIEW_W, VIEW_H, VIEW_FOV = 2304, 1536, 100.0
# Degrees. The model may repaint +-EDIT_HALF around the join. Near each edge of that strip, the switch from
# the original to the repaint follows a minimum-error cut (as in image quilting) through a band reaching
# CUT_IN inside and CUT_OUT outside the strip, then feathers over a few pixels. A wide cross-fade of
# different content leaves a double exposure, and a fixed straight edge leaves kinks in lines.
EDIT_HALF, CUT_IN, CUT_OUT, FEATHER_PX = 10.0, 8.0, 3.0, 3
CUT_ERROR_MAX = 14.0  # mean absolute difference (0-255) along the cut; above it the switch would show
# A floor line or shelf edge that breaks at the cut is short and sharp, so the mean misses it: also bound
# the worst 25-row stretch of the cut (a yellow line against bare concrete scores about 35 there).
CUT_WORST_MAX, CUT_WORST_GOOD, CUT_WINDOW = 28.0, 20.0, 25
FEATHER = CUT_OUT  # kept for the provenance text
FACE = 2048
Q_STRUCTURE = ("The second image is a retouched copy of the first. Is every column, pillar, wall corner, window and "
               "door that appears in the first image still present in the second, in the same place and at the "
               "same size, not removed, moved or hidden behind new objects?")
Q_SEAM = ("Look only at the vertical middle of this photograph. Is there a visible seam there: an object, shelf, "
          "pallet or piece of furniture cut off by a straight vertical line, a floor line or edge that jumps or "
          "breaks, a duplicated object, or a sudden change of lighting or colour?")


def _prompt(scene: str, brief: str) -> str:
    return ("This is one wide photograph of a film set dressed inside a real room. Scene: "
            f"{' '.join(scene.split()[:60])} Set dressing: {brief} "
            "Two separately dressed photographs were joined along a vertical line in the middle of this image, so "
            "objects, shelves, floor markings or furniture may be cut off, doubled or misaligned there. Repaint only "
            "the masked middle strip so that everything continues naturally and completes across it: whole objects, "
            "straight continuous floor lines, matching lighting, colour and perspective with the left and right "
            "sides. The second input image is the real, undressed room from the same camera: every column, pillar, "
            "wall corner, window, door and ceiling element in it must stay exactly where it is and stay visible; only "
            "complete movable objects (shelving, pallets, boxes, furniture, props) and floor markings around them. "
            "Do not change anything outside the middle strip. No people. Keep any signs and logos as they are.")


def _yaw_offset(center: float) -> np.ndarray:
    yaw, _ = pano.view_directions(center, VIEW_FOV, VIEW_W, VIEW_H)
    return np.abs(pano._wrap(yaw - center))


def _columns(center: float) -> np.ndarray:
    """Signed yaw offset of each view column from the join (a perspective view's yaw depends on x only)."""
    yaw, _ = pano.view_directions(center, VIEW_FOV, VIEW_W, 2)
    return pano._wrap(yaw[0] - center)


def _edit_mask(center: float) -> np.ndarray:
    return np.broadcast_to(np.abs(_columns(center)) <= EDIT_HALF, (VIEW_H, VIEW_W))


def min_cut(err: np.ndarray) -> np.ndarray:
    """Top-to-bottom path of least total error through err (H x W), one column per row, 8-connected."""
    h, w = err.shape
    cost = err.astype(np.float64).copy()
    back = np.zeros((h, w), np.int8)
    cols = np.arange(w)
    for r in range(1, h):
        prev = cost[r - 1]
        stack = np.vstack([np.r_[np.inf, prev[:-1]], prev, np.r_[prev[1:], np.inf]])
        pick = stack.argmin(axis=0)
        cost[r] += stack[pick, cols]
        back[r] = pick - 1
    path = np.empty(h, np.int64)
    path[-1] = int(cost[-1].argmin())
    for r in range(h - 1, 0, -1):
        path[r - 1] = path[r] + back[r, path[r]]
    return path


def cut_weight(view: np.ndarray, out: np.ndarray, center: float) -> tuple[np.ndarray, float, float]:
    """Blend weight (1 = repaint) switching along minimum-error cuts at both strip edges, the mean error
    along the cuts, and the worst short stretch of either cut."""
    from PIL import ImageFilter
    diff = np.abs(out - view).mean(axis=2)
    smooth = np.asarray(Image.fromarray(np.clip(diff, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(3)), np.float32)
    offsets = _columns(center)
    weight = np.zeros((VIEW_H, VIEW_W), np.float32)
    errors = []
    rows = np.arange(VIEW_H)
    left_band = np.nonzero((offsets >= -EDIT_HALF - CUT_OUT) & (offsets <= -EDIT_HALF + CUT_IN))[0]
    right_band = np.nonzero((offsets >= EDIT_HALF - CUT_IN) & (offsets <= EDIT_HALF + CUT_OUT))[0]
    left = left_band[0] + min_cut(smooth[:, left_band])
    right = right_band[0] + min_cut(smooth[:, right_band])
    errors += [diff[rows, left].mean(), diff[rows, right].mean()]
    window = np.ones(CUT_WINDOW) / CUT_WINDOW
    worst = max(float(np.convolve(diff[rows, path], window, mode="valid").max()) for path in (left, right))
    x = np.arange(VIEW_W)[None, :]
    weight[(x >= left[:, None]) & (x <= right[:, None])] = 1.0
    feathered = Image.fromarray((weight * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(FEATHER_PX))
    return np.asarray(feathered, np.float32) / 255.0, round(float(np.mean(errors)), 2), round(worst, 1)


def _png(array: np.ndarray, alpha: np.ndarray | None = None) -> bytes:
    image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))
    if alpha is not None:
        image = image.convert("RGBA")
        image.putalpha(Image.fromarray(alpha.astype(np.uint8)))
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def _edit(client: OpenAIClient, view: np.ndarray, edit: np.ndarray, prompt: str,
          reference: np.ndarray) -> np.ndarray:
    # A transparent mask pixel marks where the model may repaint; the mask applies to the first image.
    mask = _png(np.zeros_like(view), np.where(edit, 0, 255))
    body = client._post("/images/edits",
                        files=[("image[]", ("view.png", _png(view), "image/png")),
                               ("image[]", ("real.png", _png(reference), "image/png")),
                               ("mask", ("mask.png", mask, "image/png"))],
                        data={"model": DRESS_MODEL, "prompt": prompt, "size": f"{VIEW_W}x{VIEW_H}",
                              "quality": "high", "n": "1"}, timeout=500)
    try:
        image = Image.open(io.BytesIO(base64.b64decode(body["data"][0]["b64_json"]))).convert("RGB")
    except (KeyError, IndexError, TypeError, ValueError, OSError):
        raise StrikeError("The image edit returned no image") from None
    return np.asarray(image.resize((VIEW_W, VIEW_H), Image.LANCZOS), np.float32)


def seam_step(view: np.ndarray) -> float:
    """How much sharper the change is across the join line than across nearby columns (about 1 = no seam).

    The join is the view's vertical centre line. A cut object, a jumping floor line or a lighting change
    makes the step across it larger than the steps across columns beside it.
    """
    g = view.mean(axis=2)
    h, w = g.shape
    rows = slice(int(h * 0.12), int(h * 0.88))  # skip the filled floor and ceiling bands
    c = w // 2

    def step(x):
        return float(np.abs(g[rows, x + 2] - g[rows, x - 2]).mean())

    control = [step(c + k) for k in range(10, 80, 7)] + [step(c - k) for k in range(10, 80, 7)]
    return round(step(c) / (float(np.median(control)) + 1e-6), 3)


def _crop_middle(view: np.ndarray, fraction: float = 0.5) -> Image.Image:
    w = view.shape[1]
    a, b = int(w * (0.5 - fraction / 2)), int(w * (0.5 + fraction / 2))
    return Image.fromarray(np.clip(view[:, a:b], 0, 255).astype(np.uint8))


def _load(directory, record) -> tuple[dict, dict]:
    dressed, real = {}, {}
    for face in record["faces"]:
        h = int(face["source_heading_deg"])
        dressed[h] = np.asarray(Image.open(directory / face["dressed"]).convert("RGB").resize((FACE, FACE), Image.LANCZOS),
                                np.float32)
        real[h] = np.asarray(Image.open(directory / face["real"]).convert("RGB").resize((FACE, FACE), Image.LANCZOS),
                             np.float32)
    return dressed, real


def repair_join(client: OpenAIClient, dressed: dict, real: dict, left: int, scene: str, brief: str,
                attempts: int = 4) -> dict:
    """Repair the join between wall `left` and wall `left + 90`; returns the blended view and checks."""
    right, center = (left + 90) % 360, (left + 45) % 360
    pair = {left: dressed[left], right: dressed[right]}
    view, valid = pano.render_view(pair, center, VIEW_FOV, VIEW_W, VIEW_H)
    view = pano.fill_invalid(view, valid)
    real_view, real_valid = pano.render_view({left: real[left], right: real[right]}, center, VIEW_FOV, VIEW_W, VIEW_H)
    real_view = pano.fill_invalid(real_view, real_valid)
    edit = _edit_mask(center)
    before = client.predicates([_crop_middle(view)], [Q_SEAM])[0]
    # The dressing itself was checked against the real room when it was made; a repair must not make that
    # worse, and must keep every structural element of the dressed view it retouches.
    kept_before = client.predicates([_crop_middle(real_view, 0.4), _crop_middle(view, 0.4)], [Q_KEPT])[0]
    kept_floor = min(KEPT_MIN, kept_before - 0.1)
    step_before = seam_step(view)
    result = {"join_deg": center, "seam_before_p": round(before, 3), "step_before": step_before,
              "kept_before_p": round(kept_before, 3), "accepted": False}
    best, tried = None, []
    for attempt in range(1, attempts + 1):
        out = _edit(client, view, edit, _prompt(scene, brief), real_view)
        # Register on what must not move: everything outside the repainted strip.
        aligned, info = pano.register(view, out, weight=(~edit).astype(np.float32))
        weight, cut_error, cut_worst = cut_weight(view, aligned, center)
        blended = view * (1 - weight[..., None]) + aligned * weight[..., None]
        seam = client.predicates([_crop_middle(blended)], [Q_SEAM])[0]
        kept = client.predicates([_crop_middle(real_view, 0.4), _crop_middle(blended, 0.4)], [Q_KEPT])[0]
        structure = client.predicates([_crop_middle(view, 0.4), _crop_middle(blended, 0.4)], [Q_STRUCTURE])[0]
        candidate = {"attempt": attempt, "seam_after_p": round(seam, 3), "step_after": seam_step(blended),
                     "architecture_kept_p": round(kept, 3), "structure_kept_p": round(structure, 3),
                     "cut_error": cut_error, "cut_worst": cut_worst, "registration": info, "view": blended,
                     "weight": weight}
        tried.append({k: candidate[k] for k in ("step_after", "seam_after_p", "architecture_kept_p",
                                                "structure_kept_p", "cut_error", "cut_worst")})
        good = (kept >= kept_floor and structure >= 0.7 and seam < 0.5 and cut_error <= CUT_ERROR_MAX
                and cut_worst <= CUT_WORST_MAX)
        # Prefer a join as smooth as a real scan (step <= 1.3), then the cleanest cut.
        rank = lambda c: (c["step_after"] > 1.3, c["cut_worst"], c["step_after"])
        if good and (best is None or rank(candidate) < rank(best)):
            best = candidate
        if best is not None and best["step_after"] <= 1.3 and best["cut_worst"] <= CUT_WORST_GOOD:
            break
    result.update(attempts=attempt, tried=tried)
    # Keep the real architecture, and make the join clearly smoother (real scans measure 0.9-1.2 here).
    if best is not None and (best["step_after"] <= 1.3 or best["step_after"] <= 0.8 * step_before):
        result.update({k: v for k, v in best.items() if k != "attempt"}, accepted=True)
    elif best is not None:
        result.update({k: v for k, v in best.items() if k not in ("attempt", "view", "weight")})
    return result


def write_back(dressed: dict, joins: list[dict]) -> dict:
    """Resample each accepted strip into both of its walls with the same feather."""
    faces = {h: face.copy() for h, face in dressed.items()}
    for join in joins:
        if not join["accepted"]:
            continue
        center = join["join_deg"]
        for h in ((center - 45) % 360, (center + 45) % 360):
            strip, covered = pano.view_to_face(join["view"], center, VIEW_FOV, h, FACE)
            w3 = np.repeat(join["weight"][..., None], 3, axis=2)
            wface, _ = pano.view_to_face(w3, center, VIEW_FOV, h, FACE)
            w = (wface[..., :1] * covered[..., None]).astype(np.float32)
            faces[h] = faces[h] * (1 - w) + strip * w
    return faces


def repair_set(model_id: str, sweep_id: str, client: OpenAIClient, log=print, joins_only=None,
               skip_repaired: bool = False,
               attempts: int = 4) -> dict:
    out = worlds_dressed_dir(model_id, sweep_id)
    record = json.loads((out / "dressed.json").read_text(encoding="utf-8"))
    if record.get("room") or record.get("splat") or record.get("pipeline") != "v2-wide-context":
        raise StrikeError("Only four-wall v2 dressed sets are repaired here")
    brief = BRIEFS.get(record.get("scene_id"), "")
    dressed, real = _load(out, record)
    done = {j["join_deg"] for j in record.get("seam_repair", {}).get("joins", []) if j.get("accepted")}
    lefts = [h for h in (0, 90, 180, 270) if h in dressed and (h + 90) % 360 in dressed
             and (joins_only is None or (h + 45) % 360 in joins_only)
             and not (skip_repaired and (h + 45) % 360 in done)]
    if not lefts:
        raise StrikeError("No join left to repair")
    with ThreadPoolExecutor(4) as pool:
        joins = list(pool.map(lambda h: repair_join(client, dressed, real, h, record["scene"], brief, attempts), lefts))
    for join in joins:
        log(f"  join {join['join_deg']:3.0f}°: {'repaired' if join['accepted'] else 'kept as it was'} "
            f"(step {join['step_before']} → {join.get('step_after')}, cut {join.get('cut_error')}/"
            f"{join.get('cut_worst')}, "
            f"structure {join.get('structure_kept_p')}, kept {join.get('architecture_kept_p')}, "
            f"attempts {join.get('attempts')}; tried {join.get('tried')})")
        ledger({"task": "dress-seams", "model": DRESS_MODEL, "status": "repaired" if join["accepted"] else "rejected",
                "join": join["join_deg"], "attempts": join.get("attempts")})
    if not any(join["accepted"] for join in joins):
        return {"repaired": 0, "joins": len(joins)}
    faces = write_back(dressed, joins)
    staging = out.parent / "dressed.next"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(out, staging)
    for face in record["faces"]:
        h = int(face["source_heading_deg"])
        Image.fromarray(np.clip(faces[h], 0, 255).astype(np.uint8)).save(staging / face["dressed"], "JPEG", quality=95)
    previous = record.get("seam_repair", {}).get("joins", [])
    redone = {join["join_deg"] for join in joins}
    record["seam_repair"] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": (f"masked image edit ({DRESS_MODEL}) of a +-{EDIT_HALF:g} degree strip across each join with the "
                   "real room as reference, registered, switched in along minimum-error cuts at the strip edges with "
                   f"a {FEATHER_PX} px feather, Decisions API checked for kept architecture and structure"),
        "joins": [j for j in previous if j["join_deg"] not in redone]
                 + [{k: v for k, v in join.items() if k not in ("view", "weight")} for join in joins]}
    (staging / "dressed.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    out.rename(out.parent / f"dressed-preseam-archive-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}")
    staging.rename(out)
    return {"repaired": sum(join["accepted"] for join in joins), "joins": len(joins)}


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description="Repair the joins between AI-dressed walls")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scene")
    group.add_argument("--set", help="<model_id>/<sweep_id>")
    parser.add_argument("--joins", help="comma-separated join headings to redo, e.g. 45,135")
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--unrepaired", action="store_true", help="redo only joins not yet repaired")
    args = parser.parse_args(argv)
    joins_only = {float(j) for j in args.joins.split(",")} if args.joins else None
    if args.set:
        targets = [tuple(args.set.split("/", 1))]
    else:
        root = worlds_dressed_dir("x", "y").parents[2]
        targets = []
        for path in sorted(root.glob("*/*/dressed/dressed.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("scene_id") == args.scene and record.get("pipeline") == "v2-wide-context":
                targets.append((path.parts[-4], path.parts[-3]))
    client = OpenAIClient()
    print(f"{len(targets)} dressed sets, joins repaired with {DRESS_MODEL}", flush=True)
    for model_id, sweep_id in targets:
        lines = []
        try:
            result = repair_set(model_id, sweep_id, client, log=lines.append, joins_only=joins_only,
                                skip_repaired=args.unrepaired,
                                attempts=args.attempts)
            print(f"{model_id}/{sweep_id}: {result['repaired']} of {result['joins']} joins repaired", flush=True)
        except StrikeError as error:
            print(f"{model_id}/{sweep_id}: SKIPPED {error}", flush=True)
        for line in lines:
            print(line, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
