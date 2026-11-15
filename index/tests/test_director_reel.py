"""Movie-preview reel: Node contract tests, static hook checks and the served module route."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from index import production

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index"


@pytest.mark.parametrize('suite', [
    'index/tests/director_reel.test.js',
    'index/tests/director-project.test.cjs',
    'index/tests/director-checks.test.cjs',
    'index/tests/director-audit.mjs',
    'web/tests/viewfinder.test.cjs',
    'web/tests/lib.test.mjs',
])
def test_reel_contract_node_suite(suite):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    proc = subprocess.run([node, "--test", suite], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_director_html_loads_reel_before_editor_and_has_controls():
    html = (INDEX / "director.html").read_text(encoding="utf-8")
    reel, editor = '<script src="director-reel.js"></script>', '<script src="director.js"></script>'
    assert reel in html and editor in html
    assert html.index(reel) < html.index(editor)
    assert 'id="expReel"' in html and 'id="cancelReel"' in html


def test_director_js_uses_reel_api_without_untrusted_html():
    js = (INDEX / "director.js").read_text(encoding="utf-8")
    assert "TypecastReel.recordReel" in js and "TypecastReel.buildSnapshot" in js
    assert "innerHTML" not in js


def test_reel_module_has_no_html_audio_mic_or_network():
    src = (INDEX / "director-reel.js").read_text(encoding="utf-8")
    for banned in ("innerHTML", "getUserMedia", "AudioContext", "fetch(") :
        assert banned not in src, banned


def test_reel_module_is_served_as_javascript():
    app = FastAPI()
    app.include_router(production.router)
    res = TestClient(app).get("/director-reel.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]
