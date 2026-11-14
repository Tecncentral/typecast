"""AI-dressed sets: Atlas client safety, camera maths, the /api/dressed route and file serving."""
import json

import pytest
from fastapi.testclient import TestClient

from agent import app as app_module
from agent.app import app
from contracts.schemas import Shot
from index import search
from worlds import atlas, dress

KEY = "wl_live_TEST_SECRET_123"


def _cam(q):
    return {"extrinsics": {"position": [0, 0, 0], "quaternion": q, "coordinateSystem": "rub"},
            "intrinsics": {"fx": 640, "fy": 640, "cx": 640, "cy": 360, "width": 1280, "height": 720}}


@pytest.mark.parametrize("q, yaw", [([0, 0, 0, 1], 0), ([0, -0.70710678, 0, 0.70710678], 90),
                                    ([0, -1, 0, 0], 180), ([0, -0.70710678, 0, -0.70710678], 270)])
def test_camera_heading_matches_the_viewfinder_convention(q, yaw):
    h = dress.camera_heading(_cam(q))
    assert round(h["yaw_deg"]) % 360 == yaw and abs(h["pitch_deg"]) < 1e-6
    assert h["tan_h"] == pytest.approx(1.0) and h["tan_v"] == pytest.approx(0.5625)


class _Resp:
    def __init__(self, status, body=None, chunks=()):
        self.status_code, self._body, self._chunks = status, body, chunks

    def json(self):
        if self._body is None:
            raise ValueError
        return self._body

    def iter_content(self, _):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Session:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return self.replies.pop(0)

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self.replies.pop(0)


def test_client_uploads_submits_waits_and_never_leaks_the_key(tmp_path):
    img = tmp_path / "face.jpg"
    img.write_bytes(b"\xff\xd8fake")
    session = _Session([
        _Resp(200, {"id": "asset_1"}),
        _Resp(201, {"id": "op_1", "done": False}),
        _Resp(200, {"id": "op_1", "done": True, "response": {"frames": []}}),
        _Resp(402, {"code": "CREDITS_UNAVAILABLE", "message": f"no credits for {KEY}"}),
    ])
    client = atlas.AtlasClient(api_key=KEY, session=session, sleep=lambda s: None)
    assert client.upload_image(img) == "asset_1"
    body = json.loads(session.calls[0][2]["data"])
    assert body["asset"]["base64"].startswith("data:image/jpeg;base64,")
    op = client.submit("images2PosedRGBD", {"frames": []}, idempotency_key="k")
    assert client.wait(op)["done"] is True
    with pytest.raises(atlas.AtlasError) as err:
        client.submit("atlasChisel", {})
    assert "402" in str(err.value) and "CREDITS_UNAVAILABLE" in str(err.value) and KEY not in str(err.value)
    for method, url, kw in session.calls:
        assert url.startswith(atlas.ATLAS_BASE) and kw["allow_redirects"] is False


def test_failed_operation_and_insecure_downloads_are_refused(tmp_path):
    session = _Session([_Resp(200, {"id": "op_2", "done": True,
                                    "error": {"message": "boom", "details": [{"reason": "EXECUTION_FAILED"}]}})])
    client = atlas.AtlasClient(api_key=KEY, session=session)
    with pytest.raises(atlas.AtlasError, match="EXECUTION_FAILED"):
        client.wait({"id": "op_2", "done": False})
    with pytest.raises(atlas.AtlasError, match="non-HTTPS"):
        client.download("http://example.com/x.jpg", tmp_path / "x.jpg")


class _FakeIndex:
    def __init__(self, shots):
        self.shots = shots

    def get_shot(self, shot_id):
        for shot in self.shots:
            if shot.shot_id == shot_id:
                return shot
        raise KeyError(shot_id)


@pytest.fixture
def dressed_client(tmp_path, monkeypatch):
    shot = Shot(shot_id="p1-m1-s1-0.000-abc", model_id="m1", sweep_id="s1", heading_deg=0.0,
                image_path="/cache/views/p1-m1-s1-0.000-abc.jpg", property_id="p1")
    search.configure_index(_FakeIndex([shot]))
    monkeypatch.setenv("TYPECAST_WORLDS_DIR", str(tmp_path))
    out = tmp_path / "m1" / "s1" / "dressed"
    out.mkdir(parents=True)
    faces = [{"dressed": f"dressed_{i}.jpg", "real": f"real_{i}.jpg", "yaw_deg": i * 90.0, "pitch_deg": 0.0,
              "tan_h": 1.0, "tan_v": 0.56, "source_heading_deg": i * 90} for i in range(4)]
    (out / "dressed.json").write_text(json.dumps({"scene": "INT. WAREHOUSE - DAY.", "scene_id": "w", "prompt": "p",
                                                   "label": dress.LABEL, "faces": faces, "splat": None}))
    yield TestClient(app)
    search.configure_index(None)


def test_dressed_route_returns_labelled_faces(dressed_client):
    body = dressed_client.get("/api/dressed/p1-m1-s1-0.000-abc").json()
    assert body["label"] == "AI-imagined set dressing, not the real room"
    assert [f["yaw_deg"] for f in body["faces"]] == [0.0, 90.0, 180.0, 270.0]
    assert body["faces"][0]["dressed_url"] == "/cache/worlds/m1/s1/dressed/dressed_0.jpg"
    assert body["splat_url"] is None


def test_dressed_route_404_422_and_disable_flag(dressed_client, monkeypatch, tmp_path):
    assert dressed_client.get("/api/dressed/bad%20id").status_code == 422
    assert dressed_client.get("/api/dressed/p1-m1-s9-0.000-abc").status_code == 404
    monkeypatch.setenv("TYPECAST_ENABLE_DRESSED", "0")
    assert dressed_client.get("/api/dressed/p1-m1-s1-0.000-abc").status_code == 404


def test_cache_serves_splats_only_from_generated_worlds():
    ok = app_module._servable_cache_path
    assert ok("views/a.jpg") and ok("worlds/m/s/dressed/dressed_0.png")
    assert ok("worlds/m/s/dressed/dressed.spz")
    assert not ok("views/a.spz") and not ok("worlds/m/s/dressed/dressed.json") and not ok("join.parquet")


def _dressed_record(tmp_path):
    out = tmp_path / "m1" / "s1" / "dressed"
    record = json.loads((out / "dressed.json").read_text())
    cam = _cam([0, 0, 0, 1])
    cam["extrinsics"]["position"] = [0.0, 1.8, 0.0]
    for i, face in enumerate(record["faces"]):
        face.update(camera=cam, image_asset_id=f"img_{i}", depth_asset_id=f"depth_{i}")
    record.update(shot_id="p1-m1-s1-0.000-abc", model_id="m1", sweep_id="s1")
    (out / "dressed.json").write_text(json.dumps(record))
    return out


def test_splat_assets_reads_draft_and_refined_responses():
    asset = {"assetId": "a", "url": "https://x/s.spz"}
    assert dress.splat_assets({"draftSplat": asset, "refinedSplats": {}}) == {"draft": asset}
    assert dress.splat_assets({"refinedSplats": {"500000": asset, "2000000": asset}}).keys() == {"500000", "2000000"}
    assert dress.splat_assets({"refinedSplats": {}}) == {} and dress.splat_assets({}) == {}


def test_draft_splat_skips_refinement_and_reaches_the_viewer(dressed_client, tmp_path):
    out = _dressed_record(tmp_path)
    assert dress.find_dressed(scene_id="w")["sweep_id"] == "s1" and dress.find_dressed(shot_id="nope") is None
    session = _Session([
        _Resp(201, {"id": "op_s", "done": False}),
        _Resp(200, {"id": "op_s", "done": True,
                    "response": {"draftSplat": {"assetId": "asset_s", "url": "https://x/s.spz"}, "refinedSplats": {}}}),
        _Resp(200, chunks=[b"spz-bytes"]),
    ])
    client = atlas.AtlasClient(api_key=KEY, session=session, sleep=lambda s: None)
    record = dress.splat_scan_point(sweep={"model_id": "m1", "sweep_id": "s1"}, client=client, draft=True,
                                    log=lambda m: None)
    body = json.loads(session.calls[0][2]["data"])
    assert body["refine"] is False and len(body["posedFrames"]) == 4
    assert body["posedFrames"][0]["depth"] == {"depthAsset": {"assetId": "depth_0"}}
    assert (out / "dressed-draft.spz").read_bytes() == b"spz-bytes"
    assert record["splat"]["mode"] == "draft" and record["splat"]["eye"] == [0.0, 1.8, 0.0]
    ledger = (tmp_path / "atlas-operations.jsonl").read_text()
    assert '"credits": 500' in ledger and KEY not in ledger
    served = dressed_client.get("/api/dressed/p1-m1-s1-0.000-abc").json()
    assert served["splat"] == {"url": "/cache/worlds/m1/s1/dressed/dressed-draft.spz", "mode": "draft",
                               "splat_count": None, "eye": [0.0, 1.8, 0.0]}
    assert served["splat_url"] == served["splat"]["url"]


def test_refined_splat_is_the_default_and_wins_over_a_draft(dressed_client, tmp_path):
    out = _dressed_record(tmp_path)
    record = json.loads((out / "dressed.json").read_text())
    record["splats"] = {"draft": {"file": "dressed-draft.spz", "mode": "draft"}}
    (out / "dressed.json").write_text(json.dumps(record))
    session = _Session([
        _Resp(201, {"id": "op_r", "done": True,
                    "response": {"refinedSplats": {"2000000": {"assetId": "asset_r", "url": "https://x/r.spz"}}}}),
        _Resp(200, chunks=[b"refined"]),
    ])
    client = atlas.AtlasClient(api_key=KEY, session=session, sleep=lambda s: None)
    record = dress.splat_scan_point(sweep={"model_id": "m1", "sweep_id": "s1"}, client=client, log=lambda m: None)
    assert "refine" not in json.loads(session.calls[0][2]["data"])
    assert record["splat"]["file"] == "dressed.spz" and record["splat"]["splat_count"] == 2000000
    assert set(record["splats"]) == {"draft", "refined"}
    assert '"credits": 5000' in (tmp_path / "atlas-operations.jsonl").read_text()


def test_splat_cli_refuses_to_spend_without_the_matching_allowance(monkeypatch, capsys):
    monkeypatch.setenv("WORLDLABS_API_KEY", KEY)
    for argv in (["--splat", "--draft", "--scene-id", "w"], ["--splat", "--scene-id", "w", "--allow-spend-credits", "500"]):
        with pytest.raises(SystemExit):
            dress.main(argv)
    assert "pass --allow-spend-credits" in capsys.readouterr().err
