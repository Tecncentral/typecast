"""Offline pytest suite for index/matterport.py using injectable HTTP clients."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from typing import Any, Mapping
from PIL import Image
import pytest
import httpx

from index.matterport import (
    MATTERPORT_GRAPH_ENDPOINT,
    MatterportIngestionError,
    ORIENTATION_CAVEAT,
    ingest_matterport,
    main,
)


def _make_jpeg_bytes(color: tuple[int, int, int] = (120, 140, 160), size: tuple[int, int] = (16, 16)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    return buf.getvalue()


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        *,
        json_data: Any = None,
        content: bytes = b"",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.headers = dict(headers or {})

    def json(self) -> Any:
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class FakeGraphSession:
    def __init__(self, handler) -> None:
        self._handler = handler
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        json: Any = None,
        auth: tuple[str, str] | None = None,
        timeout: float | tuple[float, float] = 15.0,
        follow_redirects: bool = False,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "auth": auth,
                "timeout": timeout,
                "follow_redirects": follow_redirects,
            }
        )
        return self._handler(url, json, auth)


class FakeCdnSession:
    def __init__(self, handler) -> None:
        self._handler = handler
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        *,
        timeout: float | tuple[float, float] = 15.0,
        follow_redirects: bool = False,
        stream: bool = False,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "timeout": timeout,
                "follow_redirects": follow_redirects,
                "stream": stream,
            }
        )
        return self._handler(url)


def _write_models_file(tmp_path: Path, pairs: list[dict[str, str]]) -> Path:
    p = tmp_path / "models.json"
    p.write_text(json.dumps(pairs), encoding="utf-8")
    return p


def _public_dns(_: str) -> list[str]:
    return ["93.184.216.34"]


def test_successful_ingestion_writes_manifest_unknown_geometry_and_separated_sessions(
    tmp_path: Path,
) -> None:
    models_file = _write_models_file(
        tmp_path, [{"model_id": "model_abc", "property_id": "prop_xyz"}]
    )
    out_dir = tmp_path / "cache" / "matterport"
    valid_jpg = _make_jpeg_bytes()
    secret_key = "test_key_never_leaked"
    secret_token = "test_token_never_leaked"

    def graph_handler(url: str, body: dict, auth: tuple[str, str] | None) -> FakeResponse:
        assert url == MATTERPORT_GRAPH_ENDPOINT
        assert auth == (secret_key, secret_token)
        assert "panoLocations" in body["query"]
        assert body["variables"] == {"id": "model_abc"}
        return FakeResponse(
            200,
            json_data={
                "data": {
                    "model": {
                        "panoLocations": [
                            {
                                "id": "sweep_01",
                                "label": "Main Hall",
                                "position": {"x": 1.25, "y": -2.5, "z": 0.0},
                                "skybox": {
                                    "status": "ready",
                                    "children": [
                                        "https://cdn.example.test/up_0.jpg?sig=secret0",
                                        "https://cdn.example.test/h_1.jpg?sig=secret1",
                                        "https://cdn.example.test/h_2.jpg?sig=secret2",
                                        "https://cdn.example.test/h_3.jpg?sig=secret3",
                                        "https://cdn.example.test/h_4.jpg?sig=secret4",
                                        "https://cdn.example.test/down_5.jpg?sig=secret5",
                                    ],
                                },
                            }
                        ]
                    }
                }
            },
        )

    def cdn_handler(url: str) -> FakeResponse:
        # Only horizon indices 1..4 should ever be requested; never 0 (up) or 5 (down)
        assert "up_0" not in url and "down_5" not in url
        return FakeResponse(200, content=valid_jpg)

    graph_sess = FakeGraphSession(graph_handler)
    cdn_sess = FakeCdnSession(cdn_handler)
    fixed_now = datetime(2026, 11, 14, 10, 0, 0, tzinfo=timezone.utc)

    manifest, report = ingest_matterport(
        models_path=models_file,
        output_dir=out_dir,
        auth=(secret_key, secret_token),
        graph_session=graph_sess,
        cdn_session=cdn_sess,
        dns_resolver=_public_dns,
        now_fn=lambda: fixed_now,
    )

    # Verify strict session separation (CDN session has no auth attribute or credential forwarding)
    assert len(graph_sess.calls) == 1
    assert len(cdn_sess.calls) == 4
    assert all("auth" not in c for c in cdn_sess.calls)

    assert report.models_succeeded == 1
    assert report.shots_written == 4
    assert report.shots_resumed == 0
    assert report.shots_failed == 0

    records = manifest["records"]
    assert len(records) == 4
    assert [r["heading_deg"] for r in records] == [0.0, 90.0, 180.0, 270.0]

    for idx, rec in enumerate(records, start=1):
        assert rec["model_id"] == "model_abc"
        assert rec["sweep_id"] == "sweep_01"
        assert rec["property_id"] == "prop_xyz"
        assert rec["format"] == "perspective"
        assert rec["image_path"] == f"images/model_abc/sweep_01_face{idx}.jpg"
        assert (out_dir / rec["image_path"]).is_file()
        # Geometry unknown until measured; measure_on_site must be True
        assert rec["room_area_m2"] is None
        assert rec["ceiling_m"] is None
        assert rec["depth_m"] is None
        assert rec["measure_on_site"] is True
        # Provenance sidecar metadata
        prov = rec["provenance"]
        assert prov["cube_face_index"] == idx
        assert prov["position_m"] == {"x": 1.25, "y": -2.5, "z": 0.0}
        assert prov["fetched_at"] == fixed_now.isoformat()
        assert prov["orientation_caveat"] == ORIENTATION_CAVEAT

    # Ensure secrets and signed URL query tokens are never written to source_manifest.json
    written_text = (out_dir / "source_manifest.json").read_text(encoding="utf-8")
    assert secret_key not in written_text
    assert secret_token not in written_text
    assert "sig=secret" not in written_text


def test_malformed_skybox_faces_and_partial_failure_handling(tmp_path: Path) -> None:
    models_file = _write_models_file(
        tmp_path,
        [
            {"model_id": "model_partial", "property_id": "prop_1"},
            {"model_id": "model_broken", "property_id": "prop_2"},
        ],
    )
    out_dir = tmp_path / "cache" / "matterport"
    valid_jpg = _make_jpeg_bytes()

    def graph_handler(_: str, body: dict, __: Any) -> FakeResponse:
        mid = body["variables"]["id"]
        if mid == "model_broken":
            return FakeResponse(200, json_data={"errors": [{"message": "Model not accessible"}]})
        return FakeResponse(
            200,
            json_data={
                "data": {
                    "model": {
                        "panoLocations": [
                            # Malformed: only 4 children instead of 6
                            {
                                "id": "bad_sweep_len",
                                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                                "skybox": {"status": "ready", "children": ["https://cdn.example.test/a.jpg"] * 4},
                            },
                            # Malformed: skybox status not ready
                            {
                                "id": "bad_sweep_status",
                                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                                "skybox": {"status": "processing", "children": ["https://cdn.example.test/a.jpg"] * 6},
                            },
                            # Valid sweep
                            {
                                "id": "good_sweep",
                                "position": {"x": 2.0, "y": 3.0, "z": 1.0},
                                "skybox": {
                                    "status": "ready",
                                    "children": [
                                        f"https://cdn.example.test/f{i}.jpg" for i in range(6)
                                    ],
                                },
                            },
                        ]
                    }
                }
            },
        )

    def cdn_handler(url: str) -> FakeResponse:
        # Face 3 returns corrupt image bytes; faces 1, 2, 4 succeed
        if url.endswith("f3.jpg"):
            return FakeResponse(200, content=b"not-a-valid-jpeg")
        return FakeResponse(200, content=valid_jpg)

    manifest, report = ingest_matterport(
        models_path=models_file,
        output_dir=out_dir,
        auth=("k", "t"),
        graph_session=FakeGraphSession(graph_handler),
        cdn_session=FakeCdnSession(cdn_handler),
        max_retries=0,
        dns_resolver=_public_dns,
    )

    assert report.models_requested == 2
    assert report.models_succeeded == 1
    assert report.models_failed == 1
    assert report.sweeps_seen == 3
    assert report.sweeps_skipped == 2
    assert report.shots_written == 3
    assert report.shots_failed == 1
    assert len(manifest["records"]) == 3


def test_retries_on_transient_errors_and_blocks_private_redirect(tmp_path: Path) -> None:
    models_file = _write_models_file(tmp_path, [{"model_id": "model_retry", "property_id": "prop_r"}])
    out_dir = tmp_path / "cache" / "matterport"
    valid_jpg = _make_jpeg_bytes()
    sleeps: list[float] = []

    graph_attempts = {"count": 0}

    def graph_handler(_: str, __: dict, ___: Any) -> FakeResponse:
        graph_attempts["count"] += 1
        if graph_attempts["count"] == 1:
            return FakeResponse(503)
        return FakeResponse(
            200,
            json_data={
                "data": {
                    "model": {
                        "panoLocations": [
                            {
                                "id": "sw1",
                                "position": {"x": 0, "y": 0, "z": 0},
                                "skybox": {
                                    "status": "ready",
                                    "children": [
                                        "https://cdn.example.test/0.jpg",
                                        "https://cdn.example.test/1_flaky.jpg",
                                        "https://cdn.example.test/2_ssrf.jpg",
                                        "https://cdn.example.test/3_ok.jpg",
                                        "https://cdn.example.test/4_ok.jpg",
                                        "https://cdn.example.test/5.jpg",
                                    ],
                                },
                            }
                        ]
                    }
                }
            },
        )

    flaky_attempts = {"count": 0}

    def cdn_handler(url: str) -> FakeResponse:
        if "1_flaky.jpg" in url:
            flaky_attempts["count"] += 1
            if flaky_attempts["count"] == 1:
                raise httpx.TimeoutException("simulated timeout")
            return FakeResponse(200, content=valid_jpg)
        if "2_ssrf.jpg" in url:
            # Redirect to private RFC1918 address must be rejected
            return FakeResponse(302, headers={"Location": "https://127.0.0.1/internal.jpg"})
        return FakeResponse(200, content=valid_jpg)

    manifest, report = ingest_matterport(
        models_path=models_file,
        output_dir=out_dir,
        auth=("k", "t"),
        graph_session=FakeGraphSession(graph_handler),
        cdn_session=FakeCdnSession(cdn_handler),
        max_retries=2,
        backoff_base=0.1,
        sleep_fn=sleeps.append,
        dns_resolver=_public_dns,
    )

    assert graph_attempts["count"] == 2
    assert flaky_attempts["count"] == 2
    assert sleeps == [0.1, 0.1]
    assert report.shots_written == 3
    assert report.shots_failed == 1
    assert len(manifest["records"]) == 3


def test_resume_skips_valid_local_images_and_redownloads_corrupt_ones(tmp_path: Path) -> None:
    models_file = _write_models_file(tmp_path, [{"model_id": "model_res", "property_id": "prop_res"}])
    out_dir = tmp_path / "cache" / "matterport"
    img_dir = out_dir / "images" / "model_res"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Pre-seed face 1 as valid JPEG, face 2 as corrupt bytes; faces 3 & 4 absent
    (img_dir / "sw_res_face1.jpg").write_bytes(_make_jpeg_bytes((10, 20, 30)))
    (img_dir / "sw_res_face2.jpg").write_bytes(b"corrupted-partial-file")

    downloaded_urls: list[str] = []
    fresh_jpg = _make_jpeg_bytes((200, 210, 220))

    def graph_handler(_: str, __: dict, ___: Any) -> FakeResponse:
        return FakeResponse(
            200,
            json_data={
                "data": {
                    "model": {
                        "panoLocations": [
                            {
                                "id": "sw_res",
                                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                                "skybox": {
                                    "status": "ready",
                                    "children": [
                                        f"https://cdn.example.test/face_{i}.jpg" for i in range(6)
                                    ],
                                },
                            }
                        ]
                    }
                }
            },
        )

    def cdn_handler(url: str) -> FakeResponse:
        downloaded_urls.append(url)
        return FakeResponse(200, content=fresh_jpg)

    manifest, report = ingest_matterport(
        models_path=models_file,
        output_dir=out_dir,
        auth=("k", "t"),
        graph_session=FakeGraphSession(graph_handler),
        cdn_session=FakeCdnSession(cdn_handler),
        dns_resolver=_public_dns,
    )

    assert report.shots_resumed == 1
    assert report.shots_written == 3
    assert report.shots_failed == 0
    assert downloaded_urls == [
        "https://cdn.example.test/face_2.jpg",
        "https://cdn.example.test/face_3.jpg",
        "https://cdn.example.test/face_4.jpg",
    ]
    assert len(manifest["records"]) == 4


def test_spatial_sampling_covers_far_views_without_near_duplicates():
    from index.matterport import select_spread_panos
    panos = [dict(id=str(i), position=dict(x=x, y=0, z=1),
                  skybox={'status': 'available', 'children': ['https://example.test/image'] * 6})
             for i, x in enumerate([0, 0.1, 2, 10, 5])]
    result = select_spread_panos(panos, 3)
    assert [p['position']['x'] for p in result] == [0, 10, 5]


def test_failed_refresh_preserves_good_manifest_and_download_timestamp(tmp_path):
    from index.matterport import atomic_write_json
    models = _write_models_file(tmp_path, [{'model_id': 'new', 'property_id': 'p'}])
    root = tmp_path / 'cache/matterport'
    image = root / 'images/old.jpg'
    image.parent.mkdir(parents=True)
    image.write_bytes(_make_jpeg_bytes())
    prior = {'shot_id': 'old', 'image_path': 'images/old.jpg',
             'provenance': {'fetched_at': '2026-11-14T01:00:00+00:00'}}
    atomic_write_json(root / 'source_manifest.json', {'records': [prior]})
    with pytest.raises(MatterportIngestionError, match='preserved'):
        ingest_matterport(models_path=models, output_dir=root, auth=('fake', 'fake'),
            graph_session=FakeGraphSession(lambda *a: FakeResponse(401)),
            cdn_session=FakeCdnSession(lambda *a: None), max_retries=0)
    after = json.loads((root / 'source_manifest.json').read_text())
    assert after['records'] == [prior]
    assert after['summary']['models_failed'] == 1


def test_nonzero_exit_when_zero_valid_shots_produced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('index.matterport.ROOT', tmp_path)
    models_file = _write_models_file(tmp_path, [{"model_id": "model_fail", "property_id": "prop_f"}])
    out_dir = tmp_path / "cache" / "matterport"

    monkeypatch.setenv("MATTERPORT_API_KEY", "dummy_key")
    monkeypatch.setenv("MATTERPORT_API_TOKEN", "dummy_token")

    def failing_post(*args, **kwargs):
        return FakeResponse(401)

    monkeypatch.setattr("httpx.Client.post", failing_post)

    exit_code = main(["--models", str(models_file), "--output-dir", str(out_dir), "--max-retries", "0"])
    assert exit_code == 1
    assert (out_dir / "source_manifest.json").is_file()
