"""PR30 dressed-set regressions, fixed in this candidate.

Ported from the PR35 audit (origin/cursor/pr30-regression-audit-c56a 02f5d64, baseline
dbceec2), where seven of these were xfail(strict=True) reproductions. Assertions keep
their meaning; fixtures now write tiny SYNTHETIC image bytes and genuine model/sweep ids,
and positive, traversal, symlink and provenance cases were added. Synthetic QA only:
nothing here is live World Labs output.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import agent.app as app_module
from agent.app import CachedImages, app
from contracts.schemas import Shot
from index import search
from worlds import dress

ROOT = Path(__file__).resolve().parents[2]
SHOT_ID = "p1-m1-s1-0.000-abc"
SHOT = Shot(shot_id=SHOT_ID, model_id="m1", sweep_id="s1", heading_deg=0.0,
            image_path="/cache/views/p1-m1-s1-0.000-abc.jpg", property_id="p1")
FACE = {"dressed": "dressed_0.jpg", "real": "real_0.jpg", "yaw_deg": 0, "pitch_deg": 0,
        "tan_h": 1, "tan_v": 0.5, "source_heading_deg": 0}
IDS = {"model_id": "m1", "sweep_id": "s1"}      # genuine records always name their scan point


class _Index:
    def __init__(self, shots):
        self.shots = shots

    def get_shot(self, shot_id):
        for shot in self.shots:
            if shot.shot_id == shot_id:
                return shot
        raise KeyError(shot_id)


@pytest.fixture
def worlds(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPECAST_WORLDS_DIR", str(tmp_path))
    monkeypatch.delenv("TYPECAST_ENABLE_DRESSED", raising=False)
    search.configure_index(_Index([SHOT]))
    yield tmp_path
    search.configure_index(None)


def _write(tmp_path, record, images=("dressed_0.jpg", "real_0.jpg")):
    out = tmp_path / "m1" / "s1" / "dressed"
    out.mkdir(parents=True)
    for name in images:
        (out / name).write_bytes(b"SYNTHETIC-QA")
    if isinstance(record, dict):
        record = {**IDS, **record}
    (out / "dressed.json").write_text(record if isinstance(record, str) else json.dumps(record), encoding="utf-8")
    return out


def _client(raise_server_exceptions=True):
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_absent_dressed_cache_is_a_404(worlds):
    response = _client().get(f"/api/dressed/{SHOT_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "No dressed set for this scan point"


def test_cache_does_not_serve_a_non_image(tmp_path):
    (tmp_path / "secret.txt").write_text("SECRET", encoding="utf-8")
    mini = FastAPI()
    mini.mount("/cache", CachedImages(directory=tmp_path, check_dir=False), name="cache")
    response = TestClient(mini).get("/cache/secret.txt")
    assert response.status_code == 404
    assert b"SECRET" not in response.content


def test_dressed_response_keeps_the_canonical_label_and_drops_secret_text(worlds):
    _write(worlds, {
        "scene": "INT. KITCHEN - DAY.", "scene_id": "k", "label": "Real captured Matterport property photograph",
        "prompt": "sk-TESTKEY private /home/user/.ssh/id_rsa", "faces": [FACE],
    })
    body = _client().get(f"/api/dressed/{SHOT_ID}").json()
    raw = json.dumps(body)
    assert body["label"] == dress.LABEL
    assert "Real captured" not in raw
    assert "sk-TESTKEY" not in raw
    assert "/home/" not in raw


def test_missing_cache_label_still_ships_the_canonical_label(worlds):
    _write(worlds, {"scene": "INT. KITCHEN - DAY.", "faces": [FACE], "prompt": "p"})
    body = _client().get(f"/api/dressed/{SHOT_ID}").json()
    assert body["label"] == dress.LABEL


def test_viewfinder_badge_ignores_a_real_capture_label():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('web/viewfinder.js', 'utf8')
  .replace('export { Viewfinder, shotIdFromSrc };', 'globalThis.TestViewfinder = Viewfinder;');
const context = {
  document: { body: {}, querySelectorAll: () => [] },
  MutationObserver: class { observe() {} },
  fetch: async () => ({ ok: true, json: async () => ({
    label: 'Real captured Matterport property photograph',
    scene: 'INT. KITCHEN - DAY.',
    faces: [{ yaw_deg: 0, pitch_deg: 0, tan_h: 1, tan_v: 0.5, dressed_url: '/cache/worlds/m/s/dressed/x.jpg' }],
  }) }),
  Image: class { decode() { return Promise.resolve(); } },
  matchMedia: () => ({ matches: true }),
  cancelAnimationFrame() {}, requestAnimationFrame() { return 1; },
};
vm.createContext(context);
vm.runInContext(source, context);
const nodes = new Map();
const vf = Object.create(context.TestViewfinder.prototype);
Object.assign(vf, {
  dialog: { open: true, classList: { contains: () => false } },
  generation: 1, renderer: { setDressedFace() {} },
  $(sel) { if (!nodes.has(sel)) nodes.set(sel, { textContent: '', hidden: true }); return nodes.get(sel); },
});
vf.loadDressed('shot', 1, vf.renderer).then(() => {
  process.stdout.write(nodes.get('.vf-ai-badge').textContent);
});
"""
    proc = subprocess.run([node, "-e", script], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith(dress.LABEL)
    assert "Real captured" not in proc.stdout


def test_corrupt_dressed_json_degrades_without_a_500(worlds):
    _write(worlds, "{not json")
    response = _client(raise_server_exceptions=False).get(f"/api/dressed/{SHOT_ID}")
    assert response.status_code in (404, 422)


def test_incomplete_dressed_face_degrades_without_a_500(worlds):
    _write(worlds, {"label": dress.LABEL, "faces": [{"dressed": "dressed_0.jpg"}]})
    response = _client(raise_server_exceptions=False).get(f"/api/dressed/{SHOT_ID}")
    assert response.status_code in (404, 422)


def test_missing_dressed_image_is_not_announced_as_ready():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('web/viewfinder.js', 'utf8')
  .replace('export { Viewfinder, shotIdFromSrc };', 'globalThis.TestViewfinder = Viewfinder;');
const context = {
  document: { body: {}, querySelectorAll: () => [] },
  MutationObserver: class { observe() {} },
  fetch: async () => ({ ok: true, json: async () => ({
    label: 'AI-imagined set dressing, not the real room',
    scene: 'INT. KITCHEN - DAY.',
    faces: [{ yaw_deg: 0, pitch_deg: 0, tan_h: 1, tan_v: 0.5, dressed_url: '/cache/worlds/m/s/dressed/missing.jpg' }],
  }) }),
  Image: class { decode() { return Promise.reject(new Error('missing')); } },
  matchMedia: () => ({ matches: true }),
  cancelAnimationFrame() {}, requestAnimationFrame() { return 1; },
};
vm.createContext(context);
vm.runInContext(source, context);
const nodes = new Map();
const vf = Object.create(context.TestViewfinder.prototype);
Object.assign(vf, {
  dialog: { open: true, classList: { contains: () => false } },
  generation: 1, renderer: { setDressedFace() {} },
  $(sel) { if (!nodes.has(sel)) nodes.set(sel, { textContent: '', hidden: true }); return nodes.get(sel); },
});
vf.loadDressed('shot', 1, vf.renderer).then(() => {
  const dress = nodes.get('.vf-dress');
  const status = nodes.get('.vf-status');
  process.stdout.write(JSON.stringify({ hidden: dress ? dress.hidden : true, status: status ? status.textContent : '' }));
});
"""
    proc = subprocess.run([node, "-e", script], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert proc.returncode == 0, proc.stderr
    observed = json.loads(proc.stdout)
    assert observed["hidden"] is True
    assert "ready" not in observed["status"].lower()


def test_dressed_face_name_cannot_escape_onto_another_cache_image(worlds, tmp_path):
    cache = tmp_path / "served"
    (cache / "views").mkdir(parents=True)
    (cache / "views" / "real-property.jpg").write_bytes(b"REALJPEG")
    _write(worlds, {"label": dress.LABEL, "faces": [{**FACE, "dressed": "../../../../views/real-property.jpg"}]})
    response = _client(raise_server_exceptions=False).get(f"/api/dressed/{SHOT_ID}")
    # The traversal name is never advertised, so there is no URL that could serve the other image.
    assert response.status_code == 404
    assert "faces" not in response.json() and ".." not in response.text and "real-property" not in response.text


def test_pr30_node_regressions_pass():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    # GitHub's Node defaults to the spec reporter, which has no "# fail 0" line.
    proc = subprocess.run(
        [node, "--test", "--test-reporter=tap", "index/tests/pr30-regressions.mjs"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "# fail 0" in proc.stdout
    assert "# pass 2" in proc.stdout and "# todo 0" in proc.stdout


# ---- additions: positive cases, traversal variants, symlinks, provenance, corruption ----

def _get(worlds_unused=None):
    return _client(raise_server_exceptions=False).get(f"/api/dressed/{SHOT_ID}")


def test_valid_synthetic_dressing_is_served_with_canonical_label_and_exact_urls(worlds):
    _write(worlds, {"scene": "INT. KITCHEN - DAY.", "scene_id": "k", "label": dress.LABEL, "prompt": "x",
                    "created_at": "2026-11-14T00:00:00+00:00", "faces": [FACE]})
    body = _client().get(f"/api/dressed/{SHOT_ID}").json()
    assert body["label"] == dress.LABEL and body["scene"] == "INT. KITCHEN - DAY." and body["scene_id"] == "k"
    assert body["faces"][0]["dressed_url"] == "/cache/worlds/m1/s1/dressed/dressed_0.jpg"
    assert body["faces"][0]["real_url"] == "/cache/worlds/m1/s1/dressed/real_0.jpg"
    assert "prompt" not in body and "prompt_used" not in body


def test_prompt_and_cache_internals_are_never_returned(worlds):
    _write(worlds, {"scene": "INT. KITCHEN - DAY.", "prompt": "sk-TESTKEY /home/u/.ssh",
                    "prompt_used": "C:\\Users\\x\\key",
                    "faces": [{**FACE, "camera": {"secret": "sk-TESTKEY"}, "depth_asset_id": "sk-TESTKEY"}]})
    raw = _client().get(f"/api/dressed/{SHOT_ID}").text
    for needle in ("sk-TESTKEY", "/home/", "Users", "depth_asset_id", "camera", "prompt"):
        assert needle not in raw


@pytest.mark.parametrize("name", [
    "../../../../views/real-property.jpg", "/etc/passwd", "C:\\x.jpg", "sub/dressed_0.jpg", "..\\x.jpg",
    "dressed_0.txt", "dressed_0.jpg.txt", "dressed_0.spz", "..", ".", "", "dressed_0.jpg\x00.png", 7, None,
    "a" * 200 + ".jpg", "%2e%2e%2fviews%2fx.jpg", "dressed_0..jpg",
])
def test_unsafe_face_names_are_dropped_and_never_advertised(worlds, name):
    _write(worlds, {"faces": [{**FACE, "dressed": name}]})
    response = _get()
    assert response.status_code == 404
    assert "views" not in response.text and ".." not in response.text


def test_a_bad_face_is_dropped_but_valid_partial_coverage_is_kept(worlds):
    out = _write(worlds, {"faces": [FACE, {**FACE, "dressed": "../x.jpg", "yaw_deg": 90},
                                    {**FACE, "dressed": "dressed_2.jpg", "yaw_deg": 180}]})
    (out / "dressed_2.jpg").write_bytes(b"SYNTHETIC-QA")
    body = _client().get(f"/api/dressed/{SHOT_ID}").json()
    assert [f["yaw_deg"] for f in body["faces"]] == [0.0, 180.0]


def test_missing_image_file_is_not_advertised(worlds):
    _write(worlds, {"faces": [FACE]}, images=("real_0.jpg",))
    assert _get().status_code == 404


def test_symlinked_face_to_another_cache_image_is_rejected(worlds):
    out = _write(worlds, {"faces": [FACE]}, images=("real_0.jpg",))
    other = worlds / "views" / "real-property.jpg"
    other.parent.mkdir()
    other.write_bytes(b"REALJPEG")
    try:
        (out / "dressed_0.jpg").symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    assert _get().status_code == 404


def test_symlinked_dressed_directory_is_rejected(worlds, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    (elsewhere / "dressed_0.jpg").write_bytes(b"X")
    (elsewhere / "dressed.json").write_text(json.dumps({**IDS, "faces": [FACE]}), encoding="utf-8")
    (worlds / "m1" / "s1").mkdir(parents=True)
    try:
        (worlds / "m1" / "s1" / "dressed").symlink_to(elsewhere, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    assert _get().status_code == 404


@pytest.mark.parametrize("claim", [
    {"model_id": "m2", "sweep_id": "s1"}, {"model_id": "m1", "sweep_id": "other"}, {"model_id": None, "sweep_id": None},
])
def test_record_for_another_scan_point_is_not_served(worlds, claim):
    out = _write(worlds, {"faces": [FACE]})
    data = json.loads((out / "dressed.json").read_text(encoding="utf-8"))
    (out / "dressed.json").write_text(json.dumps({**data, **claim}), encoding="utf-8")
    assert _get().status_code == 404


@pytest.mark.parametrize("record", [
    "[]", "null", "42", '"text"', "{}", '{"faces": "x"}', '{"faces": []}', '{"faces": [null, 3, "x"]}',
    '{"model_id": "m1", "sweep_id": "s1", "faces": [{"dressed": "dressed_0.jpg", "real": "real_0.jpg"}]}',
    '{"model_id": "m1", "sweep_id": "s1", "faces": [{"dressed": "dressed_0.jpg", "yaw_deg": "x", "pitch_deg": 0, "tan_h": 1, "tan_v": 1}]}',
    '{"model_id": "m1", "sweep_id": "s1", "faces": [{"dressed": "dressed_0.jpg", "yaw_deg": NaN, "pitch_deg": 0, "tan_h": 1, "tan_v": 1}]}',
    '{"model_id": "m1", "sweep_id": "s1", "faces": [{"dressed": "dressed_0.jpg", "yaw_deg": 0, "pitch_deg": 0, "tan_h": 0, "tan_v": 1}]}',
    '{"model_id": "m1", "sweep_id": "s1", "faces": [{"dressed": "dressed_0.jpg", "yaw_deg": 0, "pitch_deg": 0, "tan_h": 1e999, "tan_v": 1}]}',
    "\ufffd\x00", "[" * 100000,
])
def test_corrupt_or_invalid_records_give_a_clean_404_without_leaking(worlds, record):
    _write(worlds, record)
    response = _get()
    assert response.status_code == 404
    assert response.json() == {"detail": "No dressed set for this scan point"}


def test_oversized_records_are_refused_and_dressed_json_is_never_servable(worlds):
    _write(worlds, {"faces": [FACE], "pad": "x" * 1_100_000})
    assert _get().status_code == 404
    assert not app_module._servable_cache_path("worlds/m1/s1/dressed/dressed.json")


def test_scene_text_is_bounded_and_scene_id_must_be_simple(worlds):
    _write(worlds, {"scene": "INT. " + "A" * 5000 + "\x00\n", "scene_id": "../../x", "faces": [FACE]})
    body = _client().get(f"/api/dressed/{SHOT_ID}").json()
    assert len(body["scene"]) <= 200 and "\x00" not in body["scene"] and body["scene_id"] is None


def test_splat_url_requires_a_safe_existing_spz(worlds):
    out = _write(worlds, {"faces": [FACE], "splat": {"file": "dressed.spz"}})
    assert _client().get(f"/api/dressed/{SHOT_ID}").json()["splat_url"] is None
    (out / "dressed.spz").write_bytes(b"S")
    assert _client().get(f"/api/dressed/{SHOT_ID}").json()["splat_url"] == "/cache/worlds/m1/s1/dressed/dressed.spz"
    (out / "dressed.json").write_text(json.dumps({**IDS, "faces": [FACE], "splat": {"file": "../../views/x.spz"}}),
                                      encoding="utf-8")
    assert _client().get(f"/api/dressed/{SHOT_ID}").json()["splat_url"] is None


def test_disabled_flag_and_unknown_shots_still_answer_cleanly(worlds, monkeypatch):
    _write(worlds, {"faces": [FACE]})
    assert _client().get("/api/dressed/p1-m1-s9-0.000-abc").status_code == 404
    monkeypatch.setenv("TYPECAST_ENABLE_DRESSED", "0")
    assert _client().get(f"/api/dressed/{SHOT_ID}").status_code == 404
