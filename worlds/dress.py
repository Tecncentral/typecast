"""AI-dressed sets with World Labs Atlas: restyle a real scan point, keep its geometry.

Pipeline per scan point (four real horizon faces, scan-relative headings 0/90/180/270):
  1. images2PosedRGBD  -> 1280x720 posed frames with cameras and linear depth
  2. atlasChisel       -> depth-only targets + a set-dressing prompt: new appearance, same geometry
  3. (optional) posedImages2Splats -> a walkable SPZ from the dressed frames (5,000 credits)

  python -m worlds.dress --demo [--only <scene_id>] [--api http://localhost:8004]
  python -m worlds.dress --shot <shot_id> --scene "INT. ..." [--scene-id custom]
  python -m worlds.dress --splat --shot <shot_id>      # only with --allow-spend-credits 5000

Everything generated is AI-imagined and is labelled that way wherever it is shown.
Output is aggregate only: no keys, images or source rows are printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import sys
from datetime import datetime, timezone
from typing import Callable, Optional

import requests
from dotenv import load_dotenv

from worlds.atlas import AtlasClient, AtlasError

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = "AI-imagined set dressing, not the real room"
SPLAT_CREDITS = 5000


def worlds_dir() -> pathlib.Path:
    return pathlib.Path(os.getenv("TYPECAST_WORLDS_DIR", str(ROOT / "cache" / "worlds")))


def _safe(part: str) -> str:
    return "".join(ch for ch in part if ch.isalnum() or ch in "-_")[:80]


def scan_point_dir(model_id: str, sweep_id: str) -> pathlib.Path:
    return worlds_dir() / _safe(model_id) / _safe(sweep_id)


def ledger(entry: dict) -> None:
    path = worlds_dir() / "atlas-operations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), **entry}, sort_keys=True) + "\n")


def dressing_prompt(scene: str) -> str:
    scene = " ".join(scene.split())[:500]
    return ("A photorealistic film set, dressed for this script scene: " + scene + " "
            "Same room, same walls, windows, columns and ceiling. Period-appropriate furniture, props, "
            "set dressing and practical lighting. Natural camera exposure, no people, no text, no logos.")


def camera_heading(camera: dict) -> dict:
    """Scan-relative heading, pitch and half-angle tangents of an Atlas pinhole camera."""
    ext, intr = camera["extrinsics"], camera["intrinsics"]
    x, y, z, w = ext["quaternion"]  # XYZW, camera-to-world
    forward_cam = (0.0, 0.0, -1.0) if ext.get("coordinateSystem", "rub") == "rub" else (0.0, 0.0, 1.0)
    # Rotate the camera's forward vector into the world: v' = q v q*.
    vx, vy, vz = forward_cam
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    fx_w = vx + w * tx + (y * tz - z * ty)
    fy_w = vy + w * ty + (z * tx - x * tz)
    fz_w = vz + w * tz + (x * ty - y * tx)
    if ext.get("coordinateSystem", "rub") == "rdf":
        fy_w = -fy_w  # RDF worlds are y-down
    yaw = (math.degrees(math.atan2(fx_w, -fz_w)) + 360) % 360
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, fy_w))))
    return {"yaw_deg": round(yaw, 3), "pitch_deg": round(pitch, 3),
            "tan_h": intr["width"] / (2 * intr["fx"]), "tan_v": intr["height"] / (2 * intr["fy"]),
            "width": intr["width"], "height": intr["height"]}


def scan_point(api: str, shot_id: str) -> dict:
    response = requests.get(f"{api}/api/sweep/{shot_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def top_pick_shot(api: str, scene: str) -> str:
    response = requests.post(f"{api}/scout", json={"scene": scene}, timeout=300)
    response.raise_for_status()
    for pick in response.json().get("picks") or []:
        for shot in pick.get("shots") or []:
            if shot.get("shot_id"):
                return shot["shot_id"]
    raise AtlasError("The scene returned no pick with a real frame")


def dress_scan_point(*, sweep: dict, scene: str, scene_id: str, client: AtlasClient,
                     log: Callable[[str], None] = print) -> dict:
    faces = sorted(sweep["faces"], key=lambda f: f["heading_deg"])
    paths = [ROOT / f["image_path"].lstrip("/") for f in faces]
    if len(paths) < 2 or not all(p.is_file() for p in paths):
        raise AtlasError("This scan point lacks local faces")
    out = scan_point_dir(sweep["model_id"], sweep["sweep_id"]) / "dressed"
    tag = f"tc-{_safe(sweep['model_id'])}-{_safe(sweep['sweep_id'])}"[:96]

    asset_ids = [client.upload_image(p) for p in paths]
    log(f"uploaded {len(asset_ids)} real faces")
    op = client.submit("images2PosedRGBD", {"frames": [{"imageAsset": {"assetId": a}} for a in asset_ids],
                                            "targetResolution": [1280, 720], "canonicalizeToFirstFrame": True},
                       idempotency_key=f"{tag}-posed")
    ledger({"task": "images2PosedRGBD", "operation": op.get("id"), "scene_id": scene_id})
    posed = client.wait(op)["response"]["frames"]
    log(f"posed RGBD ready: {len(posed)} frames")

    prompt = dressing_prompt(scene)
    op = client.submit("atlasChisel", {
        "targetFrames": [{"camera": f["camera"], "depth": {"depthAsset": {"assetId": f["depth"]["depthAsset"]["assetId"]}}}
                         for f in posed],
        "prompt": prompt,
        "enhancePrompt": True,
    }, idempotency_key=f"{tag}-chisel-{hashlib.sha1(prompt.encode()).hexdigest()[:10]}")
    ledger({"task": "atlasChisel", "operation": op.get("id"), "scene_id": scene_id})
    done = client.wait(op)
    dressed = done["response"]["frames"]
    log(f"dressed frames ready: {len(dressed)}")

    records = []
    for i, (face, real, new) in enumerate(zip(faces, posed, dressed)):
        ext = "png" if ".png" in str(new["imageAsset"].get("url", "")).split("?")[0] else "jpg"
        client.download(new["imageAsset"]["url"], out / f"dressed_{i}.{ext}")
        client.download(real["imageAsset"]["url"], out / f"real_{i}.jpg")
        records.append({"source_heading_deg": face["heading_deg"], "dressed": f"dressed_{i}.{ext}",
                        "real": f"real_{i}.jpg", "camera": new.get("camera") or real["camera"],
                        "depth_asset_id": real["depth"]["depthAsset"]["assetId"],
                        "image_asset_id": new["imageAsset"].get("assetId"),
                        **camera_heading(new.get("camera") or real["camera"])})
    record = {
        "scene_id": scene_id, "scene": scene, "prompt": prompt, "prompt_used": done["response"].get("promptUsed"),
        "created_at": datetime.now(timezone.utc).isoformat(), "label": LABEL,
        "shot_id": sweep["shot_id"], "model_id": sweep["model_id"], "sweep_id": sweep["sweep_id"],
        "faces": records, "splat": None,
    }
    (out / "dressed.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def splat_scan_point(*, sweep: dict, client: AtlasClient, log: Callable[[str], None] = print) -> dict:
    out = scan_point_dir(sweep["model_id"], sweep["sweep_id"]) / "dressed"
    record = json.loads((out / "dressed.json").read_text(encoding="utf-8"))
    frames = [{"imageAsset": {"assetId": f["image_asset_id"]}, "camera": f["camera"],
               "depth": {"depthAsset": {"assetId": f["depth_asset_id"]}}} for f in record["faces"]]
    op = client.submit("posedImages2Splats", {"posedFrames": frames, "prompt": record["prompt"][:400]},
                       idempotency_key=f"tc-splat-{_safe(sweep['sweep_id'])}"[:96])
    ledger({"task": "posedImages2Splats", "operation": op.get("id"), "scene_id": record["scene_id"],
            "credits": SPLAT_CREDITS})
    log("splat started; refined runs take 15 to 25 minutes")
    done = client.wait(op)
    splats = done["response"].get("refinedSplats") or {}
    if not splats:
        raise AtlasError("Splat finished without refinedSplats")
    key = sorted(splats, key=lambda k: int(k) if str(k).isdigit() else 0)[0]
    client.download(splats[key]["url"], out / "dressed.spz")
    record["splat"] = {"file": "dressed.spz", "splat_count": key, "operation": op.get("id"),
                       "coordinate_system": "atlas camera frames (rub, first frame at origin)"}
    (out / "dressed.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    log(f"splat saved ({key} splats)")
    return record


def load_dressed(model_id: str, sweep_id: str) -> Optional[dict]:
    path = scan_point_dir(model_id, sweep_id) / "dressed" / "dressed.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    record["dir"] = f"/cache/worlds/{_safe(model_id)}/{_safe(sweep_id)}/dressed"
    return record


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8004")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--only")
    parser.add_argument("--shot")
    parser.add_argument("--scene")
    parser.add_argument("--scene-id", default="custom")
    parser.add_argument("--splat", action="store_true")
    parser.add_argument("--allow-spend-credits", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    client = AtlasClient()
    if args.splat:
        if not args.shot:
            parser.error("--splat needs --shot")
        if args.allow_spend_credits < SPLAT_CREDITS:
            parser.error(f"a refined splat costs {SPLAT_CREDITS} credits; pass --allow-spend-credits {SPLAT_CREDITS}")
        splat_scan_point(sweep=scan_point(args.api, args.shot), client=client)
        return 0
    jobs = []
    if args.demo:
        demo = json.loads((ROOT / "cache" / "demo-set.json").read_text(encoding="utf-8"))
        jobs = [(s["id"], s["scene"], None) for s in demo["scenes"] if not args.only or s["id"] == args.only]
    elif args.shot and args.scene:
        jobs = [(args.scene_id, args.scene, args.shot)]
    else:
        parser.error("give --demo, or --shot with --scene")
    failures = 0
    for scene_id, scene, shot_id in jobs:
        try:
            shot_id = shot_id or top_pick_shot(args.api, scene)
            sweep = scan_point(args.api, shot_id)
            if load_dressed(sweep["model_id"], sweep["sweep_id"]) and not args.force:
                print(f"{scene_id}: already dressed, skipped")
                continue
            print(f"{scene_id}: dressing the top pick's scan point ({len(sweep['faces'])} faces)")
            record = dress_scan_point(sweep=sweep, scene=scene, scene_id=scene_id, client=client,
                                      log=lambda m, s=scene_id: print(f"{s}: {m}"))
            yaws = ", ".join(f"{f['yaw_deg']:.0f}" for f in record["faces"])
            print(f"{scene_id}: done; dressed camera headings {yaws}")
        except (AtlasError, requests.RequestException, KeyError, TypeError) as error:
            failures += 1
            print(f"{scene_id}: FAILED: {type(error).__name__}: {str(error)[:300]}")
            if "402" in str(error):
                break
    print("Check the remaining balance at https://atlas.worldlabs.ai/settings/credits/developer")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
