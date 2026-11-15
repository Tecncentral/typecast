"""Whole-room sets: cube rendering, cameras from the scan, the Atlas estimate check, dressing, the API."""
import json
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from agent.app import app
from agent.tests.test_worlds import KEY, _FakeIndex, _Resp, _Session
from contracts.schemas import Shot
from index import search
from worlds import atlas, dress, room

IDENTITY = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
QUARTER = {"x": 0.0, "y": 0.0, "z": math.sin(math.pi / 4), "w": math.cos(math.pi / 4)}  # 90° counter-clockwise


def _manifest(points):
    scan_points = [{"id": name, "position_m": dict(zip("xyz", xyz)), "rotation": rotation, "room_id": "r"}
                   for name, xyz, rotation in points]
    views = [{"file": f"view_{i:02d}.jpg", "scan_point": scan_points[p]["id"], "view_yaw_deg": yaw, "view_pitch_deg": pitch}
             for i, (p, yaw, pitch) in enumerate(room.view_plan(len(scan_points)))]
    return {"model_id": "m1", "anchor": scan_points[0]["id"], "scan_points": scan_points, "views": views}


def test_view_plan_fills_the_budget_and_keeps_the_anchor_level_views_first():
    plan = room.view_plan(6)
    assert len(plan) == room.MAX_VIEWS and plan[:4] == [(0, 0.0, 0.0), (0, 90.0, 0.0), (0, 180.0, 0.0), (0, 270.0, 0.0)]
    assert [sum(1 for p in plan if p[0] == i) for i in range(6)] == [8, 5, 5, 5, 5, 4]
    assert all(-5.0 <= pitch <= 0.0 for _, _, pitch in plan)  # stays inside the four horizon faces


def test_render_view_reads_the_right_cube_faces():
    colours = [(9, 9, 9), (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (90, 90, 90)]
    faces = [np.full((64, 64, 3), c, np.float32) for c in colours]
    for yaw, colour in ((0, colours[1]), (90, colours[2]), (180, colours[3]), (270, colours[4])):
        view = np.asarray(room.render_view(faces, yaw_deg=yaw, pitch_deg=-5))
        assert view.shape == (720, 1280, 3) and tuple(view[360, 640]) == colour
    diagonal = np.asarray(room.render_view(faces, yaw_deg=45, pitch_deg=-5))
    assert tuple(diagonal[360, 100]) == colours[1] and tuple(diagonal[360, 1180]) == colours[2]
    assert {tuple(c) for c in diagonal.reshape(-1, 3)} == {colours[1], colours[2]}  # no cap face at this tilt


def test_cameras_come_from_the_scan_positions_and_rotations():
    manifest = _manifest([("a", (10.0, 5.0, 1.3), IDENTITY), ("b", (12.0, 5.0, 1.3), QUARTER)])
    assert room.scan_azimuth(IDENTITY) == pytest.approx(90.0) and room.scan_azimuth(QUARTER) == pytest.approx(0.0)
    cameras = room.scan_cameras(manifest, 0.5)
    first = cameras[0]
    assert first["extrinsics"]["position"] == pytest.approx([0.0, 0.65, 0.0])
    assert first["intrinsics"] == {"fx": pytest.approx(640.0), "fy": pytest.approx(640.0), "cx": 640.0, "cy": 360.0,
                                   "width": 1280, "height": 720}
    b_views = [(v, c) for v, c in zip(manifest["views"], cameras) if v["scan_point"] == "b"]
    # b stands 2 m straight ahead of a's heading 0, and its own cube is turned 90° to the left.
    assert b_views[0][1]["extrinsics"]["position"] == pytest.approx([0.0, 0.65, -1.0], abs=1e-9)
    for view, camera in b_views:
        heading = dress.camera_heading(camera)
        assert heading["yaw_deg"] == pytest.approx((view["view_yaw_deg"] - 90) % 360, abs=1e-6)
        assert heading["pitch_deg"] == pytest.approx(view["view_pitch_deg"], abs=1e-6)


def _turned(camera, degrees, scale):
    """The same camera in a world turned about the vertical and rescaled, as an estimate would give it."""
    heading = dress.camera_heading(camera)
    x, y, z = camera["extrinsics"]["position"]
    a = math.radians(degrees)
    position = [(x * math.cos(a) - z * math.sin(a)) * scale, y * scale, (x * math.sin(a) + z * math.cos(a)) * scale]
    return room.view_camera(position, heading["yaw_deg"] + degrees, heading["pitch_deg"])


def test_estimate_report_finds_the_unit_and_flags_scan_points_posed_inconsistently():
    manifest = _manifest([("a", (0.0, 0.0, 1.3), IDENTITY), ("b", (0.0, 2.5, 1.3), QUARTER),
                          ("c", (2.0, 4.5, 1.3), IDENTITY), ("d", (2.0, 7.0, 1.3), QUARTER)])
    truth = room.scan_cameras(manifest, 1.0)
    estimate = [_turned(camera, 33.0, 0.8) for camera in truth]
    report = room.estimate_report(manifest, estimate)
    assert report["consistent_scan_points"] == 4 and report["units_per_m"] == pytest.approx(0.8, rel=1e-6)
    assert report["turn_agreement_deg"] == pytest.approx(0.0, abs=1e-6) and report["estimate_rms_m"] < 1e-6
    # Atlas loses scan point b: half its views get another turn and place.
    scrambled = list(estimate)
    b_views = [i for i, v in enumerate(manifest["views"]) if v["scan_point"] == "b"]
    for i in b_views[::2]:
        scrambled[i] = _turned(truth[i], 60.0, 1.4)
    report = room.estimate_report(manifest, scrambled)
    rigs = {r["scan_point"]: r for r in report["rigs"]}
    assert not rigs["b"]["consistent"] and rigs["a"]["consistent"] and report["consistent_scan_points"] == 3
    assert report["units_per_m"] == pytest.approx(0.8, rel=1e-6)  # still read from the consistent neighbours


@pytest.fixture
def room_client(tmp_path, monkeypatch):
    shot = Shot(shot_id="p1-m1-a-0.000-abc", model_id="m1", sweep_id="a", heading_deg=0.0,
                image_path="/cache/views/p1-m1-a-0.000-abc.jpg", property_id="p1")
    search.configure_index(_FakeIndex([shot]))
    monkeypatch.setenv("TYPECAST_WORLDS_DIR", str(tmp_path))
    yield TestClient(app)
    search.configure_index(None)


def test_dress_room_uses_scan_cameras_asks_for_rebuilt_depth_and_reaches_the_viewer(room_client, tmp_path):
    manifest = _manifest([("a", (0.0, 0.0, 1.3), IDENTITY), ("b", (0.0, 2.5, 1.3), QUARTER)])
    count = len(manifest["views"])
    base = tmp_path / "m1" / "a"
    (base / "room").mkdir(parents=True)
    (base / "dressed").mkdir()
    for view in manifest["views"]:
        (base / "room" / view["file"]).write_bytes(b"real")
    old = {"scene_id": "w", "scene": "INT. OFFICE - DAY.", "shot_id": "p1-m1-a-0.000-abc", "model_id": "m1", "sweep_id": "a",
           "faces": [{"dressed": "dressed_0.jpg"}], "splat": None}
    (base / "dressed" / "dressed_0.jpg").write_bytes(b"old")
    (base / "dressed" / "dressed.json").write_text(json.dumps(old))
    estimate = [_turned(camera, 20.0, 0.8) for camera in room.scan_cameras(manifest, 1.0)]
    posed = {"views_digest": room.views_digest(manifest), "frames": [
        {"estimated_camera": camera, "depth_asset_id": f"depth_{i}", "image_asset_id": f"real_{i}"}
        for i, camera in enumerate(estimate)]}
    frames = [{"imageAsset": {"assetId": f"new_{i}", "url": f"https://x/{i}.jpg"},
               "depth": {"depthAsset": {"assetId": f"rebuilt_{i}"}}} for i in range(count)]
    session = _Session([_Resp(201, {"id": "op_c", "done": True, "response": {"frames": frames, "promptUsed": "used"}})]
                       + [_Resp(200, chunks=[b"new"]) for _ in range(count)])
    client = atlas.AtlasClient(api_key=KEY, session=session, sleep=lambda s: None)
    record = room.dress_room(record=old, manifest=manifest, posed=posed, scene="INT. PRECINCT - NIGHT.", client=client,
                             log=lambda m: None)
    body = json.loads(session.calls[0][2]["data"])
    assert body["returnDepth"] is True and len(body["targetFrames"]) == count
    assert body["targetFrames"][0]["camera"]["intrinsics"]["fx"] == pytest.approx(640.0)
    assert body["targetFrames"][0]["camera"]["extrinsics"]["position"] == pytest.approx([0.0, 1.3 * 0.8, 0.0])
    assert [f["depth"]["depthAsset"]["assetId"] for f in body["targetFrames"]] == [f"depth_{i}" for i in range(count)]
    assert all(f["depth_asset_id"] == f"rebuilt_{i}" and f["depth_source"] == "dressed" for i, f in enumerate(record["faces"]))
    assert [f["yaw_deg"] for f in record["faces"][:4]] == pytest.approx([0.0, 90.0, 180.0, 270.0], abs=1e-6)
    assert record["room"]["units_per_m"] == pytest.approx(0.8) and len(record["room"]["scan_point_positions"]) == 2
    assert (base / "dressed" / "looks" / "1" / "dressed_0.jpg").read_bytes() == b"old"

    # A draft splat of the room, then what the viewer is told.
    session = _Session([_Resp(201, {"id": "op_s", "done": True, "response": {
        "draftSplat": {"assetId": "asset_s", "url": "https://x/s.spz"}, "refinedSplats": {}}}), _Resp(200, chunks=[b"spz"])])
    client = atlas.AtlasClient(api_key=KEY, session=session, sleep=lambda s: None)
    dress.splat_scan_point(sweep={"model_id": "m1", "sweep_id": "a"}, client=client, draft=True, log=lambda m: None)
    sent = json.loads(session.calls[0][2]["data"])
    assert len(sent["posedFrames"]) == count and sent["posedFrames"][0]["depth"] == {"depthAsset": {"assetId": "rebuilt_0"}}
    served = room_client.get("/api/dressed/p1-m1-a-0.000-abc").json()
    assert served["room"] == {"scan_points": 2, "views": count}
    assert served["splat"]["units_per_m"] == pytest.approx(0.8) and served["splat"]["floor_y"] == 0.0
    assert len(served["splat"]["scan_points"]) == 2 and served["splat"]["eye"] == pytest.approx([0.0, 1.04, 0.0])


def test_estimate_report_reads_the_unit_from_nearest_neighbours_in_a_sparsely_scanned_hall():
    manifest = _manifest([("a", (0.0, 0.0, 1.3), IDENTITY), ("b", (7.0, 0.0, 1.3), IDENTITY), ("c", (14.5, 0.0, 1.3), QUARTER)])
    estimate = [_turned(camera, 10.0, 0.8) for camera in room.scan_cameras(manifest, 1.0)]
    report = room.estimate_report(manifest, estimate)
    assert report["unit_samples"] == 3 and report["units_per_m"] == pytest.approx(0.8, rel=1e-6)


def test_dress_room_hands_approved_2d_faces_to_atlas_as_context_and_keeps_them_for_the_comparison(room_client, tmp_path):
    from PIL import Image
    manifest = _manifest([("a", (0.0, 0.0, 1.3), IDENTITY), ("b", (0.0, 7.0, 1.3), QUARTER)])
    count = len(manifest["views"])
    base = tmp_path / "m1" / "a"
    (base / "room").mkdir(parents=True)
    (base / "dressed").mkdir()
    for view in manifest["views"]:
        (base / "room" / view["file"]).write_bytes(b"real")
    approved = [{"dressed": f"dressed_{h:03d}.jpg", "real": None, "yaw_deg": float(h), "pitch_deg": 0.0, "tan_h": 1.0,
                 "tan_v": 1.0, "source_heading_deg": h} for h in (0, 90, 180, 270)]
    for face in approved:
        Image.new("RGB", (64, 64), (200, 40, 160)).save(base / "dressed" / face["dressed"])
    old = {"scene_id": "disco", "scene": "INT. ROLLER DISCO - NIGHT.", "model_id": "m1", "sweep_id": "a",  # no shot id
           "faces": approved, "splat": None, "source": "image edit"}
    (base / "dressed" / "dressed.json").write_text(json.dumps(old))
    posed = {"views_digest": room.views_digest(manifest), "frames": [
        {"estimated_camera": camera, "depth_asset_id": f"depth_{i}", "image_asset_id": f"real_{i}"}
        for i, camera in enumerate(_turned(c, 20.0, 0.8) for c in room.scan_cameras(manifest, 1.0))]}
    frames = [{"imageAsset": {"assetId": f"new_{i}", "url": f"https://x/{i}.jpg"},
               "depth": {"depthAsset": {"assetId": f"rebuilt_{i}"}}} for i in range(count - 4)]
    session = _Session([_Resp(200, {"id": f"ctx_{i}"}) for i in range(4)]
                       + [_Resp(201, {"id": "op_c", "done": True, "response": {"frames": frames}})]
                       + [_Resp(200, chunks=[b"new"]) for _ in range(count - 4)])
    client = atlas.AtlasClient(api_key=KEY, session=session, sleep=lambda s: None)
    record = room.dress_room(record=old, manifest=manifest, posed=posed, scene=old["scene"], brief="Mirror ball, neon.",
                             use_context=True, client=client, log=lambda m: None)
    body = json.loads(session.calls[4][2]["data"])
    assert [c["imageAsset"]["assetId"] for c in body["contextFrames"]] == [f"ctx_{i}" for i in range(4)]
    assert body["contextFrames"][1]["camera"] == room.scan_cameras(manifest, 0.8)[1]
    assert len(body["targetFrames"]) == count - 4 and 4 * len(body["targetFrames"]) + 4 <= 128
    assert [f["depth"]["depthAsset"]["assetId"] for f in body["targetFrames"]][:2] == ["depth_4", "depth_5"]
    assert "Mirror ball, neon." in body["prompt"] and record["scene"] == "INT. ROLLER DISCO - NIGHT."
    with Image.open(base / "dressed" / "room-context_00.jpg") as photo:
        assert photo.size == (1280, 720)
    assert len(record["faces"]) == count - 4 and record["wipe_faces"] == approved
    assert all(f["scan_point"] and f["depth_asset_id"].startswith("rebuilt_") for f in record["faces"])
    # The viewer's 360° comparison still gets the approved faces; the room record rides along.
    served = room_client.get("/api/dressed/p1-m1-a-0.000-abc").json()
    assert [f["dressed_url"].rsplit("/", 1)[1] for f in served["faces"]] == [f["dressed"] for f in approved]
    assert served["room"] == {"scan_points": 2, "views": count - 4}
