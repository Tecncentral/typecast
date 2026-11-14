"""(f) Importer -> build -> index records are viewer-compatible."""
import json
import pathlib
import re
from urllib.parse import urlparse

import numpy as np
import pytest

from contracts.schemas import Shot
from index import build, store
from index.matterport import ingest_matterport
from index.search import ShotRetrievalIndex
from index.tests._audit_helpers import FakeCdn, FakeGraph, FakeResponse, jpeg_bytes, panos_body, public_dns

REPO = pathlib.Path(__file__).resolve().parents[2]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def browser_url(path: str) -> bool:
    """Root-relative URL under an app mount, or absolute http(s); never a filesystem path."""
    parsed = urlparse(path)
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    posix = pathlib.PurePosixPath(path)
    return (not parsed.scheme and "\\" not in path and path.startswith(("/cache/", "/mocks/"))
            and ".." not in posix.parts and not {"threads", "outbox"} & set(posix.parts)
            and posix.suffix.lower() in IMAGE_SUFFIXES)


@pytest.mark.parametrize("bad", ["C:\\Users\\x\\cache\\a.jpg", "/home/x/cache/a.jpg",
                                 "file:///tmp/a.jpg", "/cache/../.env", "/cache/threads/t.jpg",
                                 "images/m1/s1_face1.jpg", "/cache/views/a.json"])
def test_browser_url_rule_rejects_filesystem_and_private_paths(bad):
    assert not browser_url(bad)


@pytest.fixture
def built(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(store, "ROOT", tmp_path)
    monkeypatch.delenv("TYPECAST_INDEX_DIR", raising=False)
    out = tmp_path / "cache" / "matterport"
    models = tmp_path / "cache" / "models.json"
    models.parent.mkdir(parents=True)
    models.write_text(json.dumps([{"model_id": "m1", "property_id": "p1"},
                                  {"model_id": "m2", "property_id": "p2"}]))
    colours = iter([(10 * i, 200 - 10 * i, 90) for i in range(64)])
    ingest_matterport(models_path=models, output_dir=out, auth=("k", "t"),
                      graph_session=FakeGraph(lambda m: FakeResponse(json_data=panos_body(m, ("s1", "s2")))),
                      cdn_session=FakeCdn(lambda u: FakeResponse(content=jpeg_bytes(next(colours)))),
                      sleep_fn=lambda _s: None, dns_resolver=public_dns)
    shots = build.prepare("cache/matterport/source_manifest.json")
    return tmp_path, shots


def test_importer_manifest_builds_into_contract_valid_browser_shots(built):
    root, shots = built
    assert len(shots) == 2 * 2 * 4
    for s in shots:
        assert Shot.model_validate(s.model_dump()) == s
        assert browser_url(s.image_path), s.image_path
        assert (root / s.image_path.lstrip("/")).is_file()
        assert s.model_id in {"m1", "m2"} and s.sweep_id in {"s1", "s2"}
        assert s.heading_deg in {0.0, 90.0, 180.0, 270.0}
        assert s.measure_on_site and s.depth_m is None and s.ceiling_m is None


def test_built_index_serves_lookalike_across_buildings_only(built):
    _root, shots = built
    vectors = np.array([[1.0, 0.1 * (i % 4), 0.0] for i, _ in enumerate(shots)], dtype=np.float32)
    idx = ShotRetrievalIndex(shots, vectors, text_encoder=lambda _t: np.ones(3, np.float32))
    source = shots[0]
    got = idx.search_shots(query_shot_id=source.shot_id)
    assert got and {s.model_id for s in got} == {"m2"}
    fit = idx.check_shot(source.shot_id)
    assert fit.status == "unknown" and fit.fits is False


def test_python_and_typescript_shot_fields_match():
    ts = (REPO / "contracts" / "schemas.ts").read_text()
    body = re.search(r"interface Shot \{([^}]*)\}", ts).group(1)
    assert {m.group(1) for m in re.finditer(r"(\w+)\??\s*:", body)} == set(Shot.model_fields)


def test_api_mounts_cover_index_and_fixture_image_paths():
    from fastapi.testclient import TestClient
    from agent.app import app
    from index.search import ShotRetrievalIndex as Index

    mounts = {getattr(r, "path", None) for r in app.routes}
    assert {"/cache", "/mocks"} <= mounts
    client = TestClient(app)
    for s in Index.from_mocks().shots:
        url = s.image_path if s.image_path.startswith("/") else "/" + s.image_path
        response = client.get(url)
        assert response.status_code == 200, url
        assert response.headers["content-type"].startswith("image/")


@pytest.mark.xfail(strict=True, reason=(
    "OPEN: fixture paths in mocks/shot.json are repo-relative ('mocks/img/...') while built "
    "index paths are root-relative ('/cache/views/...', index/build.py:69). The viewer "
    "receives two URL forms; one fails when resolved against a non-root page such as /app/."))
def test_fixture_and_index_image_paths_use_same_url_form():
    from index.search import ShotRetrievalIndex as Index
    assert all(browser_url(s.image_path) for s in Index.from_mocks().shots)


ID_CASES = ["sweep.v2", "A_b-c.9", "x" * 128, ".hidden", "..", "-lead", "a/b", "a b", "x" * 129, ""]


@pytest.mark.parametrize("identifier", ID_CASES, ids=[f"id{i}" for i in range(len(ID_CASES))])
def test_importer_and_builder_agree_on_identifier_rules(tmp_path, monkeypatch, identifier):
    """Regression (fixed in 9a6fea1): index/build.py now uses the importer's id rule
    (index/matterport.py _SAFE_ID_RE). Every id is accepted by both or rejected by both."""
    from index.matterport import _SAFE_ID_RE
    monkeypatch.setattr(build, "ROOT", tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "f.jpg").write_bytes(jpeg_bytes())
    rec = dict(property_id="p1", model_id="m1", sweep_id=identifier, image_path="cache/f.jpg",
               format="perspective", heading_deg=0.0)
    (cache / "src.json").write_text(json.dumps({"records": [rec]}))
    importer_ok = bool(_SAFE_ID_RE.fullmatch(identifier))
    if importer_ok:
        assert len(build.prepare("cache/src.json")) == 1
    else:
        with pytest.raises(ValueError):
            build.prepare("cache/src.json")


# ---- index/preview.py offline smoke (TestClient; no browser, no network, fake index) ----

@pytest.fixture
def preview(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from index import preview as preview_module
    from index import search as search_module
    from index.tests._audit_helpers import fake_text_encoder, shot

    views = tmp_path / "cache" / "views"
    views.mkdir(parents=True)
    (views / "v1.jpg").write_bytes(jpeg_bytes())
    (views / "v2.jpg").write_bytes(jpeg_bytes((10, 20, 30)))
    (tmp_path / "cache" / "view-provenance.json").write_text(json.dumps(
        {"v1": {"classification": "kitchen", "fetched_at": "2026-11-14T10:00:00Z"}}))
    (tmp_path / ".env").write_text("SHOULD-NOT-BE-SERVED")
    shots = [shot("v1", "p1", image_path="/cache/views/v1.jpg", depth_m=None, ceiling_m=None,
                  measure_on_site=True),
             shot("v2", "p2", image_path="/cache/views/v2.jpg"),
             shot("escape", "p3", image_path="/cache/../.env"),
             shot("missing", "p4", image_path="/cache/views/missing.jpg")]
    vectors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0.5, 0.5, 0]], dtype=np.float32)
    monkeypatch.setattr(preview_module, "ROOT", tmp_path)
    search_module.configure_index(ShotRetrievalIndex(shots, vectors, text_encoder=fake_text_encoder))
    yield TestClient(preview_module.app, raise_server_exceptions=False)
    search_module.configure_index(None)


def test_preview_home_page_renders(preview):
    response = preview.get("/")
    assert response.status_code == 200 and "Typecast" in response.text
    assert "not a probability" in response.text      # honesty notice is on the page


def test_preview_search_returns_live_results_with_context(preview):
    body = preview.get("/api/search", params={"q": "brick warehouse"}).json()
    assert body["mode"] == "live" and body["indexed_views"] == 4 and body["properties"] == 4
    first = body["shots"][0]
    assert first["shot_id"] == "v1" and first["context"]["classification"] == "kitchen"
    for s in body["shots"]:
        Shot.model_validate({k: v for k, v in s.items() if k != "context"})


def test_preview_example_only_search_excludes_source_building(preview):
    """Regression (fixed in 9a6fea1): example-only requests are accepted (was 422)."""
    response = preview.get("/api/search", params={"example": "v1"})
    assert response.status_code == 200
    body = response.json()
    assert body["shots"] and all(s["property_id"] != "p1" for s in body["shots"])


def test_preview_requires_scene_or_example(preview):
    assert preview.get("/api/search").status_code == 400
    assert preview.get("/api/search", params={"q": ""}).status_code in (400, 422)


def test_preview_serves_cached_view_privately(preview):
    response = preview.get("/image/v1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert "no-store" in response.headers["cache-control"]


@pytest.mark.parametrize("shot_id", ["escape", "missing", "unknown-id"])
def test_preview_refuses_paths_outside_views_and_unknown_ids(preview, shot_id):
    response = preview.get(f"/image/{shot_id}")
    assert response.status_code == 404
    assert "SHOULD-NOT-BE-SERVED" not in response.text


def test_preview_without_index_is_503_not_500(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from index import preview as preview_module
    from index import search as search_module
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "0")
    monkeypatch.setattr(search_module, "USE_MOCKS", search_module._INITIAL_USE_MOCKS)
    search_module.configure_index(None, cache_dir=tmp_path / "absent")
    try:
        client = TestClient(preview_module.app, raise_server_exceptions=False)
        response = client.get("/api/search", params={"q": "kitchen"})
        assert response.status_code == 503 and "PRIVATE-DETAIL" not in response.text
    finally:
        search_module.configure_index(None)


def test_preview_encoder_failure_is_controlled_503(tmp_path, monkeypatch):
    """Regression (fixed in 9a6fea1): a failure inside the real text-encoder path (not just a
    patched search_shots) becomes 503 without leaking the exception text."""
    from fastapi.testclient import TestClient
    from index import preview as preview_module
    from index import search as search_module
    from index.tests._audit_helpers import shot

    def broken_encoder(_text):
        raise OSError("model hub unreachable (injected) PRIVATE-DETAIL")
    search_module.configure_index(ShotRetrievalIndex([shot("v1", "p1")], np.eye(1, 3, dtype=np.float32),
                                                     text_encoder=broken_encoder))
    try:
        client = TestClient(preview_module.app, raise_server_exceptions=False)
        response = client.get("/api/search", params={"q": "kitchen"})
        assert response.status_code == 503 and "PRIVATE-DETAIL" not in response.text
    finally:
        search_module.configure_index(None)


def test_preview_image_root_follows_index_mode(tmp_path, monkeypatch):
    """Regression for the 9a6fea1 mock image fallback: mock indexes serve only mocks/img,
    live indexes serve only cache/views; neither mode serves the other's directory."""
    from fastapi.testclient import TestClient
    from index import preview as preview_module
    from index import search as search_module
    from index.tests._audit_helpers import shot

    for rel in ("mocks/img/fixture.jpg", "cache/views/real.jpg"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(jpeg_bytes())
    monkeypatch.setattr(preview_module, "ROOT", tmp_path)
    shots = [shot("fixture", "p1", image_path="mocks/img/fixture.jpg"),
             shot("real", "p2", image_path="/cache/views/real.jpg")]
    client = TestClient(preview_module.app, raise_server_exceptions=False)
    try:
        search_module.configure_index(ShotRetrievalIndex(shots, None, is_mock=True))
        assert client.get("/image/fixture").status_code == 200
        assert client.get("/image/real").status_code == 404
        search_module.configure_index(ShotRetrievalIndex(
            shots, np.eye(2, 3, dtype=np.float32), text_encoder=lambda _t: np.eye(1, 3, dtype=np.float32)[0]))
        assert client.get("/image/fixture").status_code == 404
        assert client.get("/image/real").status_code == 200
    finally:
        search_module.configure_index(None)
