"""Whole-room AI sets: dress one room from several real scan points, so it can be walked.

One scan point gives four views from one spot, and a splat that only holds up there.
Atlas asks for 8 to 16 spread-out views per room. Here the views come from the real scan:

  1. Matterport: every scan point near the chosen one, with its six cube faces.
  2. Render 1280x720 pinhole views from each cube, 32 in all: atlasChisel holds 32
     depth-guided views per request, and so does a draft splat.
  3. images2PosedRGBD estimates depth for all views together. Its camera estimate is not
     used: every camera is built from Matterport's measured scan positions and rotations.
     The estimate is still compared with the scan, and gives the size of Atlas's world unit.
  4. atlasChisel dresses all 32 views in one request at those cameras, so the set agrees
     from every side, and returns depth rebuilt in the cameras' own frame and scale.
  5. posedImages2Splats (worlds.dress --splat) turns them into one walkable splat.

  python -m worlds.room --scene-id <dressed scene id> [--radius 8 | --points id,id] --fetch-only
  python -m worlds.room --scene-id <id> --pose-only            # Atlas: pose, check against the scan
  python -m worlds.room --scene-id <id> [--scene "INT. ..."]   # Atlas: dress the posed views

The result replaces the scan point's active look; the previous look is archived.
Everything generated is AI-imagined and is labelled that way wherever it is shown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import sys
from datetime import datetime, timezone
from typing import Callable, Optional

import numpy as np
from dotenv import load_dotenv
from PIL import Image

from worlds.atlas import AtlasClient, AtlasError
from worlds.dress import (LABEL, ROOT, _safe, archive_look, camera_heading, dressing_prompt, find_dressed, ledger,
                          scan_point_dir)

ROOM_QUERY = ('query Room($id: ID!) { model(id:$id) { panoLocations { id position {x y z} rotation {x y z w} '
              'anchor { room { id } } skybox(resolution:"2k") { status children } } } }')
VIEW_SIZE = (1280, 720)
VIEW_HFOV_DEG = 90.0
MAX_VIEWS = 32  # atlasChisel: 128 model views per request, 4 per depth-guided target
VIEWS_PER_POINT = 4


def scan_points(model_id: str) -> list[dict]:
    """Every scan point of a model that has a complete cube: id, position in metres, room, face URLs."""
    import httpx
    from index import matterport as mp
    with httpx.Client() as session:
        model = mp.fetch_model_record(session, model_id=model_id, auth=mp.load_matterport_credentials(ROOT / ".env"),
                                      query=ROOM_QUERY, timeout=30)
    points = []
    for pano in model.get("panoLocations") or []:
        position = mp._extract_position(pano)
        try:
            urls = mp._validate_skybox_children(pano, model_id=model_id, sweep_id=str(pano.get("id")))
        except mp.MatterportIngestionError:
            continue
        if position is None or not mp._SAFE_ID_RE.match(str(pano.get("id"))):
            continue
        rotation = pano.get("rotation") or {}
        if not all(isinstance(rotation.get(k), (int, float)) for k in "xyzw"):
            continue
        points.append({"id": pano["id"], "position_m": position, "rotation": {k: float(rotation[k]) for k in "xyzw"},
                       "urls": urls,
                       "room_id": ((pano.get("anchor") or {}).get("room") or {}).get("id")})
    return points


def nearest_points(points: list[dict], anchor_id: str, *, radius_m: float, limit: int) -> list[dict]:
    """The anchor first, then the closest scan points on the same level within the radius."""
    anchor = next((p for p in points if p["id"] == anchor_id), None)
    if anchor is None:
        raise AtlasError("The chosen scan point is not in the Matterport model")
    def flat(p):
        return math.dist([p["position_m"]["x"], p["position_m"]["y"]], [anchor["position_m"]["x"], anchor["position_m"]["y"]])
    near = [p for p in points if p["id"] != anchor_id and flat(p) <= radius_m
            and abs(p["position_m"]["z"] - anchor["position_m"]["z"]) < 1.0]
    return [anchor] + sorted(near, key=flat)[:limit - 1]


def download_cube(point: dict, dest: pathlib.Path) -> list[pathlib.Path]:
    """Six cube faces of one scan point: 0 up, 1 to 4 the horizon at 0/90/180/270, 5 down."""
    import httpx
    from index import matterport as mp
    paths = [dest / f"face_{i}.jpg" for i in range(6)]
    if all(mp.is_valid_local_image(p) for p in paths):
        return paths
    dest.mkdir(parents=True, exist_ok=True)
    with httpx.Client() as cdn:
        for url, path in zip(point["urls"], paths):
            data = mp.download_cdn_image_bytes(cdn, url, timeout=60)
            mp.validate_and_decode_image_bytes(data)
            mp.atomic_write_bytes(path, data)
    return paths


# ---- cube geometry ----
# Scan-point frame, as in the viewfinder: x right, y up, heading 0 looks down -z and grows toward +x.
# Only the four horizon faces are used. The views tilt at most 5° down, which stays inside them,
# so the up and down faces (whose rotation Matterport does not document) are never needed.

def _sample(faces: list[np.ndarray], rays: np.ndarray) -> np.ndarray:
    """Bilinear lookup in the horizon faces (index 1 to 4) for rays in the scan-point frame."""
    x, y, z = rays[..., 0], rays[..., 1], rays[..., 2]
    out = np.zeros(rays.shape[:-1] + (3,), np.float32)
    index = 1 + (np.round(np.degrees(np.arctan2(x, -z)) / 90).astype(int) % 4)
    for face in range(1, 5):
        mask = index == face
        if not mask.any():
            continue
        heading = math.radians((face - 1) * 90)
        lx = x[mask] * math.cos(heading) + z[mask] * math.sin(heading)
        lz = -x[mask] * math.sin(heading) + z[mask] * math.cos(heading)
        u, v = lx / -lz, -y[mask] / -lz
        image = faces[face]
        size = image.shape[0]
        px = np.clip((u + 1) / 2 * size - 0.5, 0, size - 1)
        py = np.clip((v + 1) / 2 * size - 0.5, 0, size - 1)
        x0, y0 = np.floor(px).astype(int), np.floor(py).astype(int)
        x1, y1 = np.minimum(x0 + 1, size - 1), np.minimum(y0 + 1, size - 1)
        wx, wy = (px - x0)[:, None], (py - y0)[:, None]
        out[mask] = (image[y0, x0] * (1 - wx) * (1 - wy) + image[y0, x1] * wx * (1 - wy)
                     + image[y1, x0] * (1 - wx) * wy + image[y1, x1] * wx * wy)
    return out


def render_view(faces: list[np.ndarray], *, yaw_deg: float, pitch_deg: float) -> Image.Image:
    """A 1280x720 pinhole view from the scan point, yaw and pitch in the scan-point frame."""
    width, height = VIEW_SIZE
    focal = width / 2 / math.tan(math.radians(VIEW_HFOV_DEG) / 2)
    xs = (np.arange(width) + 0.5 - width / 2) / focal
    ys = (np.arange(height) + 0.5 - height / 2) / focal
    u, v = np.meshgrid(xs, ys)
    x, y, z = u, -v, -np.ones_like(u)
    pitch, yaw = math.radians(pitch_deg), math.radians(yaw_deg)
    y, z = y * math.cos(pitch) - z * math.sin(pitch), y * math.sin(pitch) + z * math.cos(pitch)
    x, z = x * math.cos(yaw) - z * math.sin(yaw), x * math.sin(yaw) + z * math.cos(yaw)
    rays = np.stack([x, y, z], -1)
    rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
    return Image.fromarray(np.clip(_sample(faces, rays), 0, 255).astype(np.uint8))


ANCHOR_VIEWS = [(float(yaw), 0.0) for yaw in (0, 90, 180, 270)] + [(float(yaw), -5.0) for yaw in (45, 135, 225, 315)]


def view_plan(count: int) -> list[tuple[int, float, float]]:
    """(scan point index, yaw, pitch) for each view, MAX_VIEWS in all.

    The anchor's four level views come first: the 360° comparison in the viewfinder reads them.
    Four diagonal views follow, because views 90° apart share almost nothing and Atlas cannot
    pose them from each other. The rest of the budget is shared by the other scan points, evenly
    spaced in yaw, turned half a step on alternate points and tilted 5° down for the floor. That
    tilt stays inside the four horizon faces of the cube.
    """
    plan = [(0, yaw, pitch) for yaw, pitch in ANCHOR_VIEWS]
    others, budget = count - 1, MAX_VIEWS - len(ANCHOR_VIEWS)
    for point in range(1, count):
        views = budget // others + (1 if point <= budget % others else 0)
        step = 360.0 / views
        plan += [(point, (k * step + (step / 2 if point % 2 else 0.0)) % 360, -5.0) for k in range(views)]
    return plan


def prepare_views(record: dict, *, radius_m: float, only: Optional[list[str]] = None,
                  log: Callable[[str], None] = print) -> dict:
    """Download the scan points and render the views. No Atlas call.

    `only` names the scan points to use (id prefixes), for open-plan spaces that Matterport
    splits into several rooms; otherwise the nearest ones within the radius are taken.
    """
    out = scan_point_dir(record["model_id"], record["sweep_id"]) / "room"
    every = scan_points(record["model_id"])
    if only:
        chosen = [p for p in every if p["id"] != record["sweep_id"] and any(p["id"].startswith(x) for x in only)]
        anchor = next(p for p in every if p["id"] == record["sweep_id"])
        points = [anchor] + sorted(chosen, key=lambda p: math.dist(
            [p["position_m"]["x"], p["position_m"]["y"]], [anchor["position_m"]["x"], anchor["position_m"]["y"]]))
        points = points[:1 + (MAX_VIEWS - len(ANCHOR_VIEWS)) // VIEWS_PER_POINT]
    else:
        points = nearest_points(every, record["sweep_id"], radius_m=radius_m,
                                limit=1 + (MAX_VIEWS - len(ANCHOR_VIEWS)) // VIEWS_PER_POINT)
    if len(points) < 2:
        raise AtlasError("A room needs at least two scan points")
    for stale in out.glob("view_*.jpg"):
        stale.unlink()
    log(f"{len(points)} scan points")
    cubes = []
    for point in points:
        paths = download_cube(point, out / "cubes" / _safe(point["id"]))
        cubes.append([np.asarray(Image.open(p).convert("RGB"), np.float32) if 1 <= i <= 4 else None
                      for i, p in enumerate(paths)])
    views = []
    for i, (point, yaw, pitch) in enumerate(view_plan(len(points))):
        name = f"view_{i:02d}.jpg"
        render_view(cubes[point], yaw_deg=yaw, pitch_deg=pitch).save(out / name, quality=92)
        views.append({"file": name, "scan_point": points[point]["id"], "view_yaw_deg": yaw, "view_pitch_deg": pitch})
    manifest = {"model_id": record["model_id"], "anchor": record["sweep_id"], "radius_m": radius_m,
                "scan_points": [{"id": p["id"], "position_m": p["position_m"], "rotation": p["rotation"],
                                 "room_id": p["room_id"]} for p in points],
                "views": views}
    (out / "views.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"rendered {len(views)} views")
    return manifest


# ---- cameras from the scan ----
# Matterport measured where every scan point stood and how it was turned. The views were
# rendered from those points at known angles, so every camera is known exactly, in metres.
# Atlas's own camera estimate is used for two things only: the depth maps it comes with, and
# the size of its world unit, so the known cameras can be written in the units of that depth.
# Checked on this pipeline's first room: where Atlas posed a scan point consistently, its turn
# matched Matterport's rotation to about 1.5°. Cube heading 0 is the scan's local +x axis.

def _angle(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def view_camera(position: list[float], yaw_deg: float, pitch_deg: float) -> dict:
    """An Atlas pinhole camera (right/up/back) at a position, looking along a viewfinder yaw and pitch."""
    width, height = VIEW_SIZE
    focal = width / 2 / math.tan(math.radians(VIEW_HFOV_DEG) / 2)
    half_yaw, half_pitch = -math.radians(yaw_deg) / 2, math.radians(pitch_deg) / 2
    quaternion = [math.cos(half_yaw) * math.sin(half_pitch), math.sin(half_yaw) * math.cos(half_pitch),
                  -math.sin(half_yaw) * math.sin(half_pitch), math.cos(half_yaw) * math.cos(half_pitch)]
    return {"extrinsics": {"position": [float(v) for v in position], "quaternion": quaternion, "coordinateSystem": "rub"},
            "intrinsics": {"fx": focal, "fy": focal, "cx": width / 2, "cy": height / 2, "width": width, "height": height}}


def scan_azimuth(rotation: dict) -> float:
    """Degrees clockwise from Matterport's +y, seen from above, of a scan point's cube heading 0."""
    x, y, z, w = (rotation[k] for k in "xyzw")
    forward = (1 - 2 * (y * y + z * z), 2 * (x * y + w * z))  # the local +x axis in the floor plane
    return math.degrees(math.atan2(forward[0], forward[1])) % 360


def scan_cameras(manifest: dict, units_per_m: float) -> list[dict]:
    """Every view's camera from Matterport's measurements, in a world scaled to `units_per_m`.

    The world is the viewfinder's: the anchor scan point's heading 0 looks down -z, x is to its
    right, y is up from the scan's floor.
    """
    points = {p["id"]: p for p in manifest["scan_points"]}
    anchor = manifest["scan_points"][0]
    zero = scan_azimuth(anchor["rotation"])
    cameras = []
    for view in manifest["views"]:
        point = points[view["scan_point"]]
        dx = point["position_m"]["x"] - anchor["position_m"]["x"]
        dy = point["position_m"]["y"] - anchor["position_m"]["y"]
        bearing = math.radians(math.degrees(math.atan2(dx, dy)) - zero)
        reach = math.hypot(dx, dy) * units_per_m
        position = [reach * math.sin(bearing), point["position_m"]["z"] * units_per_m, -reach * math.cos(bearing)]
        turn = scan_azimuth(point["rotation"]) - zero
        cameras.append(view_camera(position, (view["view_yaw_deg"] + turn) % 360, view["view_pitch_deg"]))
    return cameras


def estimate_report(manifest: dict, estimated: list[dict]) -> dict:
    """How Atlas's estimated cameras compare with the scan, and the size of Atlas's world unit.

    A scan point is "consistent" when most of its views were given one centre and one turn.
    The unit comes from distances between neighbouring consistent scan points, which stay
    right even where the estimate bends over a long room.
    """
    truth = {p["id"]: p for p in manifest["scan_points"]}
    groups: dict[str, list[int]] = {}
    for i, view in enumerate(manifest["views"]):
        groups.setdefault(view["scan_point"], []).append(i)
    rigs, centres = [], {}
    for point, members in groups.items():
        turns = [(camera_heading(estimated[i])["yaw_deg"] - manifest["views"][i]["view_yaw_deg"]) % 360 for i in members]
        turn = min(turns, key=lambda t: sum(sorted(_angle(t, other) for other in turns)[:max(2, len(turns) // 2 + 1)]))
        agree = [i for i, t in zip(members, turns) if _angle(t, turn) <= 5.0]
        consistent = len(agree) >= 0.8 * len(members)
        if consistent:
            centres[point] = [float(np.median([estimated[i]["extrinsics"]["position"][k] for i in agree])) for k in range(3)]
        rigs.append({"scan_point": point, "views": len(members), "views_agreeing": len(agree), "consistent": consistent,
                     "estimated_turn_deg": turn, "max_turn_error_deg": max(_angle(t, turn) for t in turns)})
    def metres(a, b):
        return math.dist([truth[a]["position_m"][k] for k in "xy"], [truth[b]["position_m"][k] for k in "xy"])

    def units(a, b):
        return math.dist([centres[a][0], centres[a][2]], [centres[b][0], centres[b][2]])

    ratios = [units(a, b) / metres(a, b) for a in centres for b in centres if a < b and 0.5 < metres(a, b) <= 4.0]
    if not ratios:
        # A hall scanned every 6 to 8 m has no pair that close: each scan point's nearest neighbour then.
        for a in centres:
            near = min((b for b in centres if b != a and metres(a, b) > 0.5), key=lambda b: metres(a, b), default=None)
            if near:
                ratios.append(units(a, near) / metres(a, near))
    # Turn check: between consistent scan points, Atlas's turns and Matterport's must differ by one constant.
    offsets = [(r["estimated_turn_deg"] - scan_azimuth(truth[r["scan_point"]]["rotation"])) % 360 for r in rigs if r["consistent"]]
    spread = max((_angle(a, b) for a in offsets for b in offsets), default=None)
    return {"rigs": rigs, "consistent_scan_points": len(centres), "units_per_m": float(np.median(ratios)) if ratios else None,
            "unit_samples": len(ratios), "turn_agreement_deg": spread,
            "estimate_rms_m": pose_agreement(manifest, estimated)["rms_m"]}


def pose_agreement(manifest: dict, cameras: list[dict]) -> dict:
    """Compare the scan-point layout in the Atlas world with Matterport's measured one.

    Both are reduced to the floor plane. A similarity fit (scale, rotation, shift) maps Atlas
    world units onto metres; the residual says how well the cameras match the real scan.
    """
    truth = {p["id"]: p["position_m"] for p in manifest["scan_points"]}
    groups: dict[str, list] = {}
    for view, camera in zip(manifest["views"], cameras):
        groups.setdefault(view["scan_point"], []).append(camera["extrinsics"]["position"])
    ids = [i for i in truth if i in groups]
    if len(ids) < 2:
        return {"scan_points": len(ids), "units_per_m": None, "rms_m": None, "max_m": None}
    est = np.array([[np.median([p[0] for p in groups[i]]), np.median([p[2] for p in groups[i]])] for i in ids])
    # Matterport is z-up; its floor plane is (x, y). Atlas is y-up; its floor plane is (x, z).
    real = np.array([[truth[i]["x"], truth[i]["y"]] for i in ids])
    best = None
    for mirror in (1.0, -1.0):  # the two floor planes may differ in handedness
        e = (est - est.mean(0)) * [1.0, mirror]
        r = real - real.mean(0)
        a, b = (e * r).sum(), (e[:, 0] * r[:, 1] - e[:, 1] * r[:, 0]).sum()
        metres_per_unit = math.hypot(a, b) / (e ** 2).sum()
        angle = math.atan2(b, a)
        rot = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        residual = np.linalg.norm(e @ rot.T * metres_per_unit - r, axis=1)
        fit = {"scan_points": len(ids), "units_per_m": 1 / metres_per_unit,
               "rms_m": float(np.sqrt((residual ** 2).mean())), "max_m": float(residual.max())}
        if best is None or fit["rms_m"] < best["rms_m"]:
            best = fit
    return best


def scan_point_positions(faces: list[dict]) -> list[list[float]]:
    """Where each scan point stands in the set's world."""
    seen: dict[str, list[float]] = {}
    for face in faces:
        seen.setdefault(face["scan_point"], face["camera"]["extrinsics"]["position"])
    return list(seen.values())


def pose_views(*, record: dict, manifest: dict, client: AtlasClient, log: Callable[[str], None] = print) -> dict:
    """Estimate depth for all views together, and compare Atlas's cameras with the scan's."""
    src = scan_point_dir(record["model_id"], record["sweep_id"]) / "room"
    tag = f"tc-room-{_safe(record['model_id'])}-{_safe(record['sweep_id'])}"[:80]
    digest = views_digest(manifest)
    asset_ids = [client.upload_image(src / view["file"]) for view in manifest["views"]]
    log(f"uploaded {len(asset_ids)} real views")
    op = client.submit("images2PosedRGBD", {"frames": [{"imageAsset": {"assetId": a}} for a in asset_ids],
                                            "targetResolution": list(VIEW_SIZE), "canonicalizeToFirstFrame": True,
                                            "refinePoses": True},
                       idempotency_key=f"{tag}-posed-{digest}")
    ledger({"task": "images2PosedRGBD", "operation": op.get("id"), "scene_id": record["scene_id"], "views": len(asset_ids)})
    response = client.wait(op)["response"]
    posed = {"views_digest": digest, "pose_refinement_accepted": response.get("poseRefinementAccepted"), "frames": [
        {"estimated_camera": f["camera"], "depth_asset_id": f["depth"]["depthAsset"]["assetId"],
         "image_asset_id": f["imageAsset"].get("assetId")} for f in response["frames"]]}
    (src / "posed.json").write_text(json.dumps(posed, indent=2), encoding="utf-8")
    return posed


def views_digest(manifest: dict) -> str:
    return hashlib.sha1(json.dumps(manifest["views"], sort_keys=True).encode()).hexdigest()[:10]


def approved_faces(record: dict, manifest: dict, out: pathlib.Path) -> dict[int, dict]:
    """{view index: face} for 2D dressed cube faces that look exactly along one of the anchor's level views.

    A scan point dressed face by face (a square 90° cube face per heading) already has an approved
    look. Each such face covers the same direction as one level view of the anchor, so it can be
    handed to Atlas as a context photograph and the walk then carries that look.
    """
    found: dict[int, dict] = {}
    # A set already built round approved faces keeps them as wipe_faces; a new look reuses them.
    for face in record.get("wipe_faces") or record.get("faces") or []:
        if face.get("tan_h") != 1.0 or face.get("tan_v") != 1.0 or face.get("pitch_deg") != 0.0:
            continue
        if not isinstance(face.get("dressed"), str) or not (out / face["dressed"]).is_file():
            continue
        for index, view in enumerate(manifest["views"]):
            if (view["scan_point"] == record["sweep_id"] and view["view_pitch_deg"] == 0.0
                    and view["view_yaw_deg"] == float(face.get("source_heading_deg", -1)) % 360):
                found.setdefault(index, face)
    return found


def context_photograph(face_path: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    """The 16:9 band of a square 90° cube face: the same pixels a level 1280x720 view of 90° sees."""
    from PIL import Image
    with Image.open(face_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        band = round(width * VIEW_SIZE[1] / VIEW_SIZE[0])
        top = (height - band) // 2
        image.crop((0, top, width, top + band)).resize(VIEW_SIZE, Image.LANCZOS).save(target, quality=95)
    return target


def dress_room(*, record: dict, manifest: dict, posed: dict, scene: str, client: AtlasClient,
               brief: Optional[str] = None, use_context: bool = False,
               log: Callable[[str], None] = print) -> dict:
    """Dress every view in one request, at the scan's own cameras, so the set agrees from every side.

    With `use_context`, the scan point's existing 2D dressed faces are sent as context photographs
    and their four views are not regenerated: the walk takes its look from them, and the 360°
    comparison keeps showing them. `brief` is the art direction when it says more than the scene.
    """
    frames = posed["frames"]
    if len(frames) > MAX_VIEWS or len(frames) != len(manifest["views"]):
        raise AtlasError(f"atlasChisel holds {MAX_VIEWS} depth-guided views per request")
    report = estimate_report(manifest, [f["estimated_camera"] for f in frames])
    log("Atlas estimate vs scan: " + json.dumps({k: (round(v, 3) if isinstance(v, float) else v)
                                                 for k, v in report.items() if k != "rigs"}))
    if not report["units_per_m"]:
        raise AtlasError("No two neighbouring scan points were posed consistently, so the depth has no known scale")
    cameras = scan_cameras(manifest, report["units_per_m"])
    base = scan_point_dir(record["model_id"], record["sweep_id"])
    out = base / "dressed"
    tag = f"tc-room-{_safe(record['model_id'])}-{_safe(record['sweep_id'])}"[:80]
    prompt = dressing_prompt(brief or scene)
    approved = approved_faces(record, manifest, out) if use_context else {}
    if use_context and not approved:
        raise AtlasError("This scan point has no 2D dressed faces along the anchor's level views to use as context")
    targets = [i for i in range(len(frames)) if i not in approved]
    # One request holds 128 model views: 4 per depth-guided target, 1 per context photograph.
    if 4 * len(targets) + len(approved) > 4 * MAX_VIEWS:
        raise AtlasError("Too many views for one atlasChisel request")
    context = []
    for i, face in sorted(approved.items()):
        photo = context_photograph(out / face["dressed"], out / f"room-context_{i:02d}.jpg")
        context.append({"imageAsset": {"assetId": client.upload_image(photo)}, "camera": cameras[i]})
    if context:
        log(f"context photographs: {len(context)} approved faces; generating the other {len(targets)} views")
    look = hashlib.sha1((prompt + posed["views_digest"] + "scan-cameras"
                         + ("".join(c["imageAsset"]["assetId"] for c in context))).encode()).hexdigest()[:10]
    op = client.submit("atlasChisel", {
        "targetFrames": [{"camera": cameras[i], "depth": {"depthAsset": {"assetId": frames[i]["depth_asset_id"]}}}
                         for i in targets],
        **({"contextFrames": context} if context else {}),
        "prompt": prompt,
        "enhancePrompt": True,
        # The generated views come back with depth rebuilt in these cameras' own frame and scale.
        "returnDepth": True,
    }, idempotency_key=f"{tag}-chisel-{look}")
    ledger({"task": "atlasChisel", "operation": op.get("id"), "scene_id": record["scene_id"], "views": len(targets),
            "context": len(context)})
    done = client.wait(op)
    dressed = done["response"]["frames"]
    if len(dressed) != len(targets):
        raise AtlasError("Atlas returned a different number of frames than were asked for")
    log(f"dressed frames ready: {len(dressed)}")

    archive_look(out, record)
    faces = []
    for i, new in zip(targets, dressed):
        view, camera, real = manifest["views"][i], cameras[i], frames[i]
        ext = "png" if ".png" in str(new["imageAsset"].get("url", "")).split("?")[0] else "jpg"
        name = f"room_{i:02d}-{look}.{ext}"
        client.download(new["imageAsset"]["url"], out / name)
        (out / f"room-real_{i:02d}.jpg").write_bytes((base / "room" / view["file"]).read_bytes())
        rebuilt = ((new.get("depth") or {}).get("depthAsset") or {}).get("assetId")
        faces.append({"dressed": name, "real": f"room-real_{i:02d}.jpg", "camera": new.get("camera") or camera,
                      "depth_asset_id": rebuilt or real["depth_asset_id"], "depth_source": "dressed" if rebuilt else "real",
                      "layout_depth_asset_id": real["depth_asset_id"], "image_asset_id": new["imageAsset"].get("assetId"),
                      "real_image_asset_id": real["image_asset_id"], "scan_point": view["scan_point"],
                      "source_heading_deg": view["view_yaw_deg"], **camera_heading(new.get("camera") or camera)})
    new_record = {
        "scene_id": record["scene_id"], "scene": scene, "prompt": prompt, "prompt_used": done["response"].get("promptUsed"),
        "created_at": datetime.now(timezone.utc).isoformat(), "label": LABEL,
        "shot_id": record.get("shot_id"), "model_id": record["model_id"], "sweep_id": record["sweep_id"],
        "faces": faces, "splat": None,
        # The 360° comparison keeps the approved 2D faces; `faces` are the frames of the walkable set.
        **({"wipe_faces": [face for _, face in sorted(approved.items())],
            "source": f"{record.get('source') or '2D dressed faces'}; walk: Atlas depth-guided views with those faces as context"}
           if approved else {}),
        "room": {"scan_points": len(manifest["scan_points"]), "views": len(faces),
                 "cameras": "Matterport scan positions and rotations", "units_per_m": report["units_per_m"],
                 "atlas_estimate": {k: v for k, v in report.items() if k != "rigs"},
                 "scan_point_positions": scan_point_positions(faces)},
    }
    (out / "dressed.json").write_text(json.dumps(new_record, indent=2), encoding="utf-8")
    return new_record


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scene-id", help="scene id of an already dressed scan point")
    parser.add_argument("--shot")
    parser.add_argument("--scene", help="the look; defaults to the scan point's current scene")
    parser.add_argument("--brief", help="art direction for the dressing prompt, when it says more than the scene")
    parser.add_argument("--context-faces", action="store_true",
                        help="keep the scan point's 2D dressed faces and hand them to Atlas as context photographs")
    parser.add_argument("--radius", type=float, default=8.0, help="metres around the scan point")
    parser.add_argument("--points", help="comma-separated scan point id prefixes to use instead of the radius")
    parser.add_argument("--fetch-only", action="store_true", help="download and render the views; no Atlas call")
    parser.add_argument("--pose-only", action="store_true", help="stop after depth estimation and the scan check")
    args = parser.parse_args(argv)
    record = find_dressed(shot_id=args.shot) if args.shot else find_dressed(scene_id=args.scene_id)
    if not record:
        parser.error("no dressed scan point in the local cache for that id")
    try:
        src = scan_point_dir(record["model_id"], record["sweep_id"]) / "room"
        if (src / "views.json").is_file() and not args.fetch_only:
            manifest = json.loads((src / "views.json").read_text(encoding="utf-8"))
        else:
            only = [x.strip() for x in (args.points or "").split(",") if x.strip()]
            manifest = prepare_views(record, radius_m=args.radius, only=only or None)
        if args.fetch_only:
            return 0
        client = AtlasClient()
        posed = json.loads((src / "posed.json").read_text(encoding="utf-8")) if (src / "posed.json").is_file() else {}
        if posed.get("views_digest") != views_digest(manifest):
            posed = pose_views(record=record, manifest=manifest, client=client)
        if args.pose_only:
            report = estimate_report(manifest, [f["estimated_camera"] for f in posed["frames"]])
            print(json.dumps({k: v for k, v in report.items() if k != "rigs"}))
            return 0
        new = dress_room(record=record, manifest=manifest, posed=posed, scene=args.scene or record["scene"],
                         brief=args.brief, use_context=args.context_faces, client=client)
        print(f"room dressed: {new['room']['views']} views from {new['room']['scan_points']} scan points")
    except Exception as error:  # sanitized: no URLs, keys or source rows
        print(f"FAILED: {type(error).__name__}: {str(error)[:300]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
