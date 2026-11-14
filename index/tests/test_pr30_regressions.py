"""Reproduced PR30 dressed-set failures at dbceec2.

The assertions state the honest behavior. They fail on this baseline and are
marked xfail(strict=True) so the suite stays green until the fix lands.
Bug ids match index/PR30-REGRESSION-AUDIT.md. PR31 e99082d does not change
agent/app.py, worlds/dress.py, or the badge/ready lines in web/viewfinder.js.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

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


def _write(tmp_path, record):
    out = tmp_path / "m1" / "s1" / "dressed"
    out.mkdir(parents=True)
    (out / "dressed.json").write_text(record if isinstance(record, str) else json.dumps(record), encoding="utf-8")


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


@pytest.mark.xfail(strict=True, reason="PR30-LABEL: /api/dressed echoes the cache label and prompt")
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


@pytest.mark.xfail(strict=True, reason="PR30-LABEL: a dressed record with no label is returned unlabeled")
def test_missing_cache_label_still_ships_the_canonical_label(worlds):
    _write(worlds, {"scene": "INT. KITCHEN - DAY.", "faces": [FACE], "prompt": "p"})
    body = _client().get(f"/api/dressed/{SHOT_ID}").json()
    assert body["label"] == dress.LABEL


@pytest.mark.xfail(strict=True, reason="PR30-LABEL: the viewfinder badge displays the cache label")
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
    faces: [{ yaw_deg: 0, pitch_deg: 0, tan_h: 1, tan_v: 0.5, dressed_url: '/x.jpg' }],
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
    proc = subprocess.run([node, "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith(dress.LABEL)
    assert "Real captured" not in proc.stdout


@pytest.mark.xfail(strict=True, reason="PR30-CACHE: corrupt dressed.json becomes HTTP 500")
def test_corrupt_dressed_json_degrades_without_a_500(worlds):
    _write(worlds, "{not json")
    response = _client(raise_server_exceptions=False).get(f"/api/dressed/{SHOT_ID}")
    assert response.status_code in (404, 422)


@pytest.mark.xfail(strict=True, reason="PR30-CACHE: a face missing yaw_deg becomes HTTP 500")
def test_incomplete_dressed_face_degrades_without_a_500(worlds):
    _write(worlds, {"label": dress.LABEL, "faces": [{"dressed": "dressed_0.jpg"}]})
    response = _client(raise_server_exceptions=False).get(f"/api/dressed/{SHOT_ID}")
    assert response.status_code in (404, 422)


@pytest.mark.xfail(strict=True, reason="PR30-CACHE: a failed dressed-image decode is announced as ready")
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
    faces: [{ yaw_deg: 0, pitch_deg: 0, tan_h: 1, tan_v: 0.5, dressed_url: '/missing.jpg' }],
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
  process.stdout.write(JSON.stringify({ hidden: dress.hidden, status: nodes.get('.vf-status').textContent }));
});
"""
    proc = subprocess.run([node, "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    observed = json.loads(proc.stdout)
    assert observed["hidden"] is True
    assert "ready" not in observed["status"].lower()


@pytest.mark.xfail(strict=True, reason="PR30-FACE-PATH: a dressed face name can read another cache image")
def test_dressed_face_name_cannot_escape_onto_another_cache_image(worlds, tmp_path):
    _write(worlds, {
        "label": dress.LABEL,
        "faces": [{**FACE, "dressed": "../../../../views/real-property.jpg"}],
    })
    body = _client().get(f"/api/dressed/{SHOT_ID}").json()
    url = body["faces"][0]["dressed_url"]
    cache = tmp_path / "served"
    (cache / "views").mkdir(parents=True)
    (cache / "views" / "real-property.jpg").write_bytes(b"REALJPEG")
    (cache / "worlds" / "m1" / "s1" / "dressed").mkdir(parents=True)
    mini = FastAPI()
    mini.mount("/cache", CachedImages(directory=cache, check_dir=False), name="cache")
    served = TestClient(mini).get(url)
    assert served.status_code == 404 and served.content != b"REALJPEG" and ".." not in url


def test_pr30_node_todos_stay_green():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    proc = subprocess.run(
        [node, "--test", "index/tests/pr30-regressions.mjs"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "# fail 0" in proc.stdout
    assert "# todo 2" in proc.stdout
