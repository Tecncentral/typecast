"""2D set dressing with an image model: strike the real room, then dress it for the scene.

  python -m strike.dress --demo          # re-dress the demo scan points that had single-point Atlas sets
  python -m strike.dress --demo --only la-warehouse-handoff

Per horizon face (the real 2048 px cube face, true camera: yaw = heading, 90 degree field of view):
  1. start from the struck face when Strike accepted one, else from the real face;
  2. one image edit dresses it for the scene with a per-scene art brief, so the four walls agree;
  3. the Decisions API checks the architecture is unchanged and that it reads as the scene; failures
     get one retry, then are dropped (that wall shows the real room, dimmed, in the viewer);
  4. results are written in the dressed.json format the viewfinder already reads, so D works as before.

Single-point Atlas dressings in the same folder are archived to dressed-atlas-archive/, never deleted.
Scan points that carry a walkable room or splat are refused: those belong to the Atlas walk.
Everything is labelled "AI-imagined set dressing, not the real room".
"""
from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from dotenv import load_dotenv
from PIL import Image

from strike.core import (Q_KEPT, ROOT, OpenAIClient, StrikeError, _safe, ledger,
                         scan_point_dir as strike_dir_for)

DRESS_MODEL = os.getenv("TYPECAST_DRESS_MODEL", "gpt-image-2.6-sunburst")
LABEL = "AI-imagined set dressing, not the real room"
KEPT_MIN, FITS_MIN = 0.6, 0.5

BRIEFS = {
    "la-warehouse-handoff": "A working industrial warehouse: wooden pallets stacked with cardboard cartons along the walls, "
                            "orange steel pallet racking, a pallet jack, a steel workbench with a few tools, yellow floor "
                            "safety lines, the central aisle left open. Daylight from the skylights.",
    "houston-apartment-conversation": "A lived-in modern apartment living room: a mid-century sofa in rust velvet facing a "
                                      "walnut coffee table, a cream wool rug, two lounge chairs, a low bookshelf with books "
                                      "and plants, a floor lamp, framed prints, bar stools at any kitchen counter. Bright "
                                      "natural daylight from the windows.",
    "houston-office-meeting": "A corporate meeting room set for a tense conversation: a long light-oak meeting table with "
                              "six black mesh office chairs, a wall-mounted display, a low credenza with binders, a tall "
                              "potted plant, a water carafe and glasses on the table. Even daylight and office lighting.",
    "la-empty-shop": "A rehearsal studio in a long empty shop: a row of folding chairs along one wall, a tall mirror on "
                     "wheels, an upright piano against a wall, a small table with scripts and water bottles, coloured "
                     "tape marks on the wooden floor, the centre of the floor kept clear for movement. Daylight and the "
                     "existing overhead lights.",
}


def prompt_for(scene: str, brief: str) -> str:
    scene = " ".join(scene.split()).split(" Parking for")[0][:400]
    return (f"Dress this real room as a photorealistic film set for this script scene: {scene} "
            f"Art direction, identical for every wall of this room: {brief} "
            "Keep the architecture exactly as photographed: the same walls, ceiling, roof structure, columns, windows "
            "and the view through them, doors, floor material, light fixtures, camera position and perspective. Place "
            "furniture and props believably on the floor and against walls, at real-world scale. Natural exposure. "
            "No people, no text, no logos.")


def worlds_dressed_dir(model_id: str, sweep_id: str) -> pathlib.Path:
    return pathlib.Path(os.getenv("TYPECAST_WORLDS_DIR", str(ROOT / "cache" / "worlds"))) / _safe(model_id) / _safe(sweep_id) / "dressed"


def edit(client: OpenAIClient, image: Image.Image, prompt: str) -> Image.Image:
    import base64
    buf = io.BytesIO()
    image.convert("RGB").resize((2048, 2048), Image.LANCZOS).save(buf, "PNG")
    body = client._post("/images/edits", files={"image": ("room.png", buf.getvalue(), "image/png")},
                        data={"model": DRESS_MODEL, "prompt": prompt, "size": "2048x2048", "quality": "high", "n": "1"},
                        timeout=400)
    try:
        return Image.open(io.BytesIO(base64.b64decode(body["data"][0]["b64_json"]))).convert("RGB")
    except (KeyError, IndexError, TypeError, ValueError, OSError):
        raise StrikeError("The image edit returned no image") from None


def dress_face(client: OpenAIClient, real: Image.Image, start: Image.Image, scene: str, prompt: str) -> dict:
    q_fits = f"Does the second image look like a believable, fully dressed film set for this scene: {scene.split('.')[0]}. {scene.split('.')[1] if '.' in scene else ''}?"
    best = None
    for attempt in (1, 2):
        dressed = edit(client, start, prompt)
        kept, fits = client.predicates([real, dressed], [Q_KEPT, q_fits])
        result = {"image": dressed, "architecture_kept_p": round(kept, 3), "fits_scene_p": round(fits, 3), "attempts": attempt}
        if kept >= KEPT_MIN and fits >= FITS_MIN:
            return {"status": "dressed", **result}
        if best is None or kept + fits > best["architecture_kept_p"] + best["fits_scene_p"]:
            best = result
    return {"status": "rejected", **{k: v for k, v in best.items() if k != "image"}, "image": None}


def dress_scan_point(target: dict, client: OpenAIClient, log=print) -> dict:
    model_id, sweep_id, scene_id = target["model_id"], target["sweep_id"], target["scene_id"]
    out = worlds_dressed_dir(model_id, sweep_id)
    existing = json.loads((out / "dressed.json").read_text(encoding="utf-8")) if (out / "dressed.json").is_file() else {}
    if existing.get("room") or existing.get("splat"):
        raise StrikeError("This scan point carries a walkable Atlas set; refusing to replace it")
    gen = pathlib.Path(ROOT / "cache" / "shot-index" / (ROOT / "cache/shot-index/CURRENT").read_text().strip() / "shots.json")
    rows = json.loads(gen.read_text())
    rows = rows if isinstance(rows, list) else rows["shots"]
    faces = sorted([r for r in rows if r["model_id"] == model_id and r["sweep_id"] == sweep_id], key=lambda r: r["heading_deg"])
    struck = {}
    srec = strike_dir_for(model_id, sweep_id) / "strike.json"
    if srec.is_file():
        for f in json.loads(srec.read_text())["faces"]:
            if f.get("status") == "struck":
                struck[f["heading_deg"]] = strike_dir_for(model_id, sweep_id) / f["struck"]
    prompt = prompt_for(target["scene"], BRIEFS[scene_id])

    def one(row):
        heading = int(round(row["heading_deg"])) % 360
        real = Image.open(ROOT / row["image_path"].lstrip("/")).convert("RGB")
        start = Image.open(struck[heading]).convert("RGB") if heading in struck else real
        t0 = time.time()
        result = dress_face(client, real, start, target["scene"], prompt)
        return heading, real, result, round(time.time() - t0, 1), heading in struck

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(one, faces))
    staging = out.parent / "dressed.next"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    records = []
    for heading, real, result, seconds, from_struck in sorted(results, key=lambda r: r[0]):
        image = result.pop("image")
        rec = {"source_heading_deg": heading, "yaw_deg": float(heading), "pitch_deg": 0.0, "tan_h": 1.0, "tan_v": 1.0,
               "from": "struck" if from_struck else "real", "seconds": seconds, **result}
        if image is not None:
            image.save(staging / f"dressed_{heading:03d}.jpg", "JPEG", quality=88)
            real.resize((1024, 1024), Image.LANCZOS).save(staging / f"real_{heading:03d}.jpg", "JPEG", quality=85)
            rec.update({"dressed": f"dressed_{heading:03d}.jpg", "real": f"real_{heading:03d}.jpg"})
            records.append(rec)
        ledger({"task": "dress", "model": DRESS_MODEL, "status": result["status"], "heading": heading,
                "attempts": result.get("attempts")})
        log(f"  face {heading:3d}°: {result['status']} (kept {result['architecture_kept_p']}, fits {result['fits_scene_p']}, "
            f"from {'struck' if from_struck else 'real'}, {seconds}s)")
    if not records:
        shutil.rmtree(staging)
        raise StrikeError("No face passed the checks; the existing set was left in place")
    record = {"scene_id": scene_id, "scene": target["scene"], "prompt": prompt, "label": LABEL,
              "created_at": datetime.now(timezone.utc).isoformat(), "model_id": model_id, "sweep_id": sweep_id,
              "faces": records, "splat": None, "source": f"openai image edit ({DRESS_MODEL}) over strike, Decisions API checked"}
    (staging / "dressed.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    if out.exists():
        archive = out.parent / "dressed-atlas-archive"
        if not archive.exists():
            out.rename(archive)
        else:
            shutil.rmtree(out)
    staging.rename(out)
    return record


def fill_missing(target: dict, client: OpenAIClient, log=print) -> int:
    """Retry walls that failed, keeping existing signage (the usual cause: 'no logos' erased a real sign)."""
    out = worlds_dressed_dir(target["model_id"], target["sweep_id"])
    record = json.loads((out / "dressed.json").read_text(encoding="utf-8"))
    if not str(record.get("source", "")).startswith("openai"):
        return 0
    have = {int(f["source_heading_deg"]) for f in record["faces"]}
    gen = (ROOT / "cache/shot-index/CURRENT").read_text().strip()
    rows = json.loads((ROOT / "cache/shot-index" / gen / "shots.json").read_text())
    rows = rows if isinstance(rows, list) else rows["shots"]
    missing = [r for r in rows if r["model_id"] == target["model_id"] and r["sweep_id"] == target["sweep_id"]
               and int(round(r["heading_deg"])) % 360 not in have]
    prompt = record["prompt"].replace("No people, no text, no logos.",
                                      "No people. Keep every existing sign, lettering and logo on the walls exactly as it is.")
    added = 0
    for row in missing:
        heading = int(round(row["heading_deg"])) % 360
        real = Image.open(ROOT / row["image_path"].lstrip("/")).convert("RGB")
        result = dress_face(client, real, real, target["scene"], prompt)
        log(f"  face {heading:3d}°: {result['status']} (kept {result['architecture_kept_p']}, fits {result['fits_scene_p']})")
        ledger({"task": "dress-fill", "model": DRESS_MODEL, "status": result["status"], "heading": heading})
        image = result.pop("image")
        if image is None:
            continue
        image.save(out / f"dressed_{heading:03d}.jpg", "JPEG", quality=88)
        real.resize((1024, 1024), Image.LANCZOS).save(out / f"real_{heading:03d}.jpg", "JPEG", quality=85)
        record["faces"].append({"source_heading_deg": heading, "yaw_deg": float(heading), "pitch_deg": 0.0, "tan_h": 1.0,
                                "tan_v": 1.0, "from": "real", "signage_kept": True, **result,
                                "dressed": f"dressed_{heading:03d}.jpg", "real": f"real_{heading:03d}.jpg"})
        added += 1
    record["faces"].sort(key=lambda f: f["source_heading_deg"])
    tmp = out / "dressed.json.part"
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    tmp.replace(out / "dressed.json")
    return added


def demo_targets() -> list[dict]:
    root = pathlib.Path(os.getenv("TYPECAST_WORLDS_DIR", str(ROOT / "cache" / "worlds")))
    out = []
    for f in sorted(root.glob("*/*/dressed*/dressed.json")):
        if f.parent.name not in {"dressed", "dressed-atlas-archive"}:
            continue
        d = json.loads(f.read_text())
        known = d.get("scene_id") in BRIEFS or str(d.get("source", "")).startswith("openai")
        if d.get("room") or d.get("splat") or not known:
            continue
        if not any(t["scene_id"] == d["scene_id"] for t in out):
            out.append({"scene_id": d["scene_id"], "scene": d["scene"], "model_id": d["model_id"], "sweep_id": d["sweep_id"]})
    return out


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--only")
    parser.add_argument("--shot", help="custom scene: any shot at the scan point to dress")
    parser.add_argument("--scene-id")
    parser.add_argument("--scene")
    parser.add_argument("--brief")
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--fill-missing", action="store_true", help="retry failed walls, keeping signage")
    args = parser.parse_args(argv)
    if args.shot:
        if not (args.scene_id and args.scene and args.brief):
            parser.error("--shot needs --scene-id, --scene and --brief")
        import requests
        sweep = requests.get(f"{args.api}/api/sweep/{args.shot}", timeout=60).json()
        BRIEFS[args.scene_id] = args.brief
        target = {"scene_id": args.scene_id, "scene": args.scene, "model_id": sweep["model_id"], "sweep_id": sweep["sweep_id"]}
        dress_scan_point(target, OpenAIClient())
        return 0
    if not args.demo:
        parser.error("give --demo or --shot")
    def done(t):
        f = worlds_dressed_dir(t["model_id"], t["sweep_id"]) / "dressed.json"
        return f.is_file() and str(json.loads(f.read_text()).get("source", "")).startswith("openai")
    targets = [t for t in demo_targets() if (not args.only or t["scene_id"] == args.only) and (args.only or not done(t))]
    client = OpenAIClient()
    if args.fill_missing:
        for t in [t for t in demo_targets() if not args.only or t["scene_id"] == args.only]:
            print(t["scene_id"], "fill missing walls:", fill_missing(t, client), "added")
        return 0
    print(f"{len(targets)} scan points to dress with {DRESS_MODEL}")
    for t in targets:
        print(t["scene_id"])
        try:
            dress_scan_point(t, client)
        except StrikeError as error:
            print(f"  FAILED: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ================================================================ v2: seam-aware dressing through wide views
# Each wall is dressed inside a 120-degree view of the room (the paper's "more context" lesson). Walls 0 and
# 180 go first; walls 90 and 270 are then dressed in views whose outer strips are the already-dressed
# neighbours, so furniture and style continue across every seam. Each output is registered back to its input
# (FFT phase correlation, small scale search) before only the wall's own region is composited.
import numpy as np  # noqa: E402

from strike import pano  # noqa: E402

VIEW_W, VIEW_H, VIEW_FOV, FACE = 2304, 1536, 120.0, 2048
CORRIDOR_RULE = ("Keep corridors, hallways, doorways and walkways completely clear: place furniture only where the "
                 "room has open floor, never inside a corridor or blocking a door.")
Q_CORRIDOR = ("Is there any furniture or object placed inside a corridor, hallway, doorway or narrow walkway, "
              "blocking the path?")
BRIEFS.setdefault("la-office-confrontation",
                  "A tense corporate office: a glass-walled meeting room with a long walnut table, black leather "
                  "chairs, a whiteboard with diagrams, laptops and coffee cups, tall plants. Even office lighting.")


def _wide_prompt(base: str, with_context: bool) -> str:
    extra = ("This is one wide 120-degree photograph of the room. " + CORRIDOR_RULE)
    if with_context:
        extra += (" The outer left and right strips of this photograph are already dressed: keep them exactly as "
                  "they are and continue their furniture, props, style and lighting seamlessly into the middle.")
    return base.replace("No people, no text, no logos.",
                        extra + " No people. Keep any existing signs and logos on the walls as they are.")


def _edit_view(client: OpenAIClient, view: np.ndarray, prompt: str) -> np.ndarray:
    import base64
    buf = io.BytesIO()
    Image.fromarray(np.clip(view, 0, 255).astype(np.uint8)).save(buf, "PNG")
    body = client._post("/images/edits", files={"image": ("view.png", buf.getvalue(), "image/png")},
                        data={"model": DRESS_MODEL, "prompt": prompt, "size": f"{VIEW_W}x{VIEW_H}",
                              "quality": "high", "n": "1"}, timeout=500)
    try:
        img = Image.open(io.BytesIO(base64.b64decode(body["data"][0]["b64_json"]))).convert("RGB")
    except (KeyError, IndexError, TypeError, ValueError, OSError):
        raise StrikeError("The image edit returned no image") from None
    return np.asarray(img.resize((VIEW_W, VIEW_H), Image.LANCZOS), np.float32)


def _faces_for(model_id: str, sweep_id: str):
    gen = (ROOT / "cache/shot-index/CURRENT").read_text().strip()
    rows = json.loads((ROOT / "cache/shot-index" / gen / "shots.json").read_text())
    rows = rows if isinstance(rows, list) else rows["shots"]
    real = {}
    for r in rows:
        if r["model_id"] == model_id and r["sweep_id"] == sweep_id:
            real[int(round(r["heading_deg"])) % 360] = np.asarray(
                Image.open(ROOT / r["image_path"].lstrip("/")).convert("RGB").resize((FACE, FACE), Image.LANCZOS), np.float32)
    start = dict(real)
    srec = strike_dir_for(model_id, sweep_id) / "strike.json"
    if srec.is_file():
        for f in json.loads(srec.read_text())["faces"]:
            if f.get("status") == "struck":
                start[f["heading_deg"]] = np.asarray(Image.open(strike_dir_for(model_id, sweep_id) / f["struck"]).convert("RGB")
                                                     .resize((FACE, FACE), Image.LANCZOS), np.float32)
    return real, start


def _gate(client: OpenAIClient, real: np.ndarray, dressed: np.ndarray, scene: str):
    q_fits = ("Does the second image look like a believable, dressed and lived-in film set that fits the setting of this "
              f"scene (any part of that space, such as a kitchen or entrance of a home): {' '.join(scene.split()[:40])}?")
    kept, fits, blocked = client.predicates([Image.fromarray(real.astype(np.uint8)), Image.fromarray(np.clip(dressed, 0, 255).astype(np.uint8))],
                                            [Q_KEPT, q_fits, Q_CORRIDOR])
    ok = kept >= KEPT_MIN and fits >= 0.3 and blocked < 0.5
    return ok, {"architecture_kept_p": round(kept, 3), "fits_scene_p": round(fits, 3), "corridor_blocked_p": round(blocked, 3)}


def dress_scan_point_v2(target: dict, client: OpenAIClient, log=print) -> dict:
    model_id, sweep_id, scene_id = target["model_id"], target["sweep_id"], target["scene_id"]
    out = worlds_dressed_dir(model_id, sweep_id)
    existing = json.loads((out / "dressed.json").read_text(encoding="utf-8")) if (out / "dressed.json").is_file() else {}
    if existing.get("room") or existing.get("splat"):
        raise StrikeError("This scan point carries a walkable Atlas set; refusing to replace it")
    real, start = _faces_for(model_id, sweep_id)
    if sorted(real) != [0, 90, 180, 270]:
        raise StrikeError("Scan point lacks four horizon faces")
    base = prompt_for(target["scene"], BRIEFS[scene_id])
    dressed, meta = {}, {}

    def first_round(h):
        view, valid = pano.render_view(start, h, VIEW_FOV, VIEW_W, VIEW_H)
        view = pano.fill_invalid(view, valid)
        for attempt in (1, 2):
            outv = _edit_view(client, view, _wide_prompt(base, with_context=False))
            aligned, info = pano.register(view, outv)
            face, cov = pano.view_to_face(aligned, h, VIEW_FOV, h, FACE)
            ok, checks = _gate(client, real[h], face, target["scene"])
            if ok or attempt == 2:
                return h, face, ok, {**checks, "registration": info, "attempts": attempt, "context": "none"}

    def second_round(h):
        src = {(h - 90) % 360: dressed[(h - 90) % 360], h: start[h], (h + 90) % 360: dressed[(h + 90) % 360]}
        view, valid = pano.render_view(src, h, VIEW_FOV, VIEW_W, VIEW_H)
        view = pano.fill_invalid(view, valid)
        bands = pano.band_mask(h, VIEW_FOV, VIEW_W, VIEW_H, 45.0).astype(np.float32)
        for attempt in (1, 2):
            outv = _edit_view(client, view, _wide_prompt(base, with_context=True))
            aligned, info = pano.register(view, outv, weight=bands)
            face, cov = pano.view_to_face(aligned, h, VIEW_FOV, h, FACE)
            ok, checks = _gate(client, real[h], face, target["scene"])
            if ok or attempt == 2:
                return h, face, ok, {**checks, "registration": info, "attempts": attempt, "context": "dressed neighbours"}

    with ThreadPoolExecutor(2) as pool:
        for h, face, ok, m in pool.map(first_round, (0, 180)):
            dressed[h], meta[h] = face, {**m, "ok": ok}
    with ThreadPoolExecutor(2) as pool:
        for h, face, ok, m in pool.map(second_round, (90, 270)):
            dressed[h], meta[h] = face, {**m, "ok": ok}

    staging = out.parent / "dressed.next"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    records = []
    for h in (0, 90, 180, 270):
        m = meta[h]
        log(f"  face {h:3d}°: {'dressed' if m['ok'] else 'rejected'} (kept {m['architecture_kept_p']}, fits {m['fits_scene_p']}, "
            f"corridor {m['corridor_blocked_p']}, shift {m['registration'].get('dx')},{m['registration'].get('dy')} "
            f"x{m['registration'].get('scale')}, {m['context']})")
        ledger({"task": "dress-v2", "model": DRESS_MODEL, "status": "dressed" if m["ok"] else "rejected", "heading": h,
                "attempts": m["attempts"]})
        if not m["ok"]:
            continue
        Image.fromarray(np.clip(dressed[h], 0, 255).astype(np.uint8)).save(staging / f"dressed_{h:03d}.jpg", "JPEG", quality=88)
        Image.fromarray(real[h].astype(np.uint8)).resize((1024, 1024), Image.LANCZOS).save(staging / f"real_{h:03d}.jpg", "JPEG", quality=85)
        records.append({"source_heading_deg": h, "yaw_deg": float(h), "pitch_deg": 0.0, "tan_h": 1.0, "tan_v": 1.0,
                        "dressed": f"dressed_{h:03d}.jpg", "real": f"real_{h:03d}.jpg", **{k: v for k, v in m.items() if k != "ok"}})
    if not records:
        shutil.rmtree(staging)
        raise StrikeError("No wall passed the checks; the existing set was left in place")
    record = {"scene_id": scene_id, "scene": target["scene"], "prompt": _wide_prompt(base, False), "label": LABEL,
              "created_at": datetime.now(timezone.utc).isoformat(), "model_id": model_id, "sweep_id": sweep_id,
              "faces": records, "splat": None, "pipeline": "v2-wide-context",
              "source": f"openai image edit ({DRESS_MODEL}) through 120-degree context views, registered, Decisions API checked"}
    (staging / "dressed.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    if out.exists():
        kind = "v1" if str(existing.get("source", "")).startswith("openai") else "atlas"
        out.rename(out.parent / f"dressed-{kind}-archive-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}")
    staging.rename(out)
    return record


def stage_targets(ranks: int = 3) -> list[dict]:
    """Scan points behind the top `ranks` cards of each demo scene in the latest stage rehearsal."""
    import requests
    demo = json.loads((ROOT / "cache" / "demo-set.json").read_text(encoding="utf-8"))
    scenes = [(s["id"], s["scene"]) for s in demo["scenes"]]
    out, seen = [], set()
    for rank in range(ranks):
        for engine in ("deep",):
            root = ROOT / "cache" / "demo-checks" / "warm" / engine
            run = sorted(p for p in root.iterdir() if p.is_dir())[-1]
            for f in sorted(run.glob("scene-*.response.json")):
                n = int(f.name.split("-")[1].split(".")[0]) - 1
                if n >= len(scenes):
                    continue
                d = json.loads(f.read_text())
                resp = d.get("response") if isinstance(d.get("response"), dict) else d
                picks = resp.get("picks") or []
                if rank >= len(picks):
                    continue
                for shot in (picks[rank].get("shots") or [])[:1]:
                    sw = requests.get(f"http://localhost:8010/api/sweep/{shot['shot_id']}", timeout=60)
                    if not sw.ok:
                        continue
                    sw = sw.json()
                    key = (sw["model_id"], sw["sweep_id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"scene_id": scenes[n][0], "scene": scenes[n][1], "model_id": key[0], "sweep_id": key[1],
                                "rank": rank + 1})
    return out


def main_v2(argv=None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description="Seam-aware dressing through wide context views")
    parser.add_argument("--ranks", type=int, default=3)
    parser.add_argument("--only")
    parser.add_argument("--include-roller-disco", action="store_true")
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--max", type=int, default=99)
    args = parser.parse_args(argv)
    targets = stage_targets(args.ranks)
    if args.include_roller_disco:
        targets = [t for t in demo_targets() if t["scene_id"] == "la-roller-disco"] + targets
    if args.only:
        targets = [t for t in targets if t["scene_id"] == args.only]
    targets.sort(key=lambda t: t.get("rank", 0))
    targets = targets[: args.max]
    print(f"{len(targets)} scan points, v2 with {DRESS_MODEL}")
    client = OpenAIClient()

    def run(t):
        lines = []
        try:
            dress_scan_point_v2(t, client, log=lines.append)
            return f"{t['scene_id']} rank {t.get('rank', '-')}:\n" + "\n".join(lines)
        except StrikeError as error:
            return f"{t['scene_id']} rank {t.get('rank', '-')}: SKIPPED {error}"
    with ThreadPoolExecutor(args.parallel) as pool:
        for text in pool.map(run, targets):
            print(text, flush=True)
    return 0
