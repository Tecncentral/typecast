"""(e) Matterport importer under injected provider failures (fake sessions, no network)."""
import json

import httpx
import pytest

from index.matterport import MatterportIngestionError, ingest_matterport
from index.tests._audit_helpers import (FakeCdn, FakeGraph, FakeResponse, jpeg_bytes, pano,
                                        panos_body, public_dns)

AUTH = ("FAKE-KEY-123", "FAKE-TOKEN-456")


def _models(tmp_path, *ids):
    path = tmp_path / "models.json"
    path.write_text(json.dumps([{"model_id": m, "property_id": f"prop{m}"} for m in ids]))
    return path


def _run(tmp_path, graph, cdn, *ids, max_retries=2):
    sleeps = []
    result = ingest_matterport(models_path=_models(tmp_path, *ids), output_dir=tmp_path / "out",
                               auth=AUTH, graph_session=graph, cdn_session=cdn,
                               max_retries=max_retries, sleep_fn=sleeps.append,
                               dns_resolver=public_dns)
    return result, sleeps


def _ok_graph():
    return FakeGraph(lambda model: FakeResponse(json_data=panos_body(model)))


def _ok_cdn():
    return FakeCdn(lambda url: FakeResponse(content=jpeg_bytes()))


def _files(tmp_path):
    root = tmp_path / "out"
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def _assert_no_secrets(text):
    for secret in (*AUTH, "SIGNED-SECRET"):
        assert secret not in text


def _graph_failure(kind):
    def handler(model):
        if kind == "timeout":
            raise httpx.ReadTimeout("injected")
        if kind == "connect":
            raise httpx.ConnectError("injected")
        return {
            "401": FakeResponse(401, json_data={"errors": [{"message": "FAKE-KEY-123 denied"}]}),
            "403": FakeResponse(403),
            "500": FakeResponse(500),
            "429": FakeResponse(429),
            "302": FakeResponse(302, headers={"Location": "https://evil.example"}),
            "non-json": FakeResponse(200, json_data=ValueError("no json")),
            "json-list": FakeResponse(200, json_data=[]),
            "graphql-errors": FakeResponse(200, json_data={"errors": [{"message": "FAKE-TOKEN-456"}]}),
            "null-model": FakeResponse(200, json_data={"data": {"model": None}}),
            "no-panos": FakeResponse(200, json_data={"data": {"model": {"panoLocations": None}}}),
            "zero-panos": FakeResponse(200, json_data={"data": {"model": {"panoLocations": []}}}),
            "skybox-pending": FakeResponse(200, json_data=panos_body(model, status="processing")),
        }[kind]
    return handler


@pytest.mark.parametrize("kind", ["timeout", "connect", "401", "403", "500", "429", "302",
                                  "non-json", "json-list", "graphql-errors", "null-model",
                                  "no-panos", "zero-panos", "skybox-pending"])
def test_graphql_failure_writes_no_images_and_raises_clear_error(tmp_path, kind):
    with pytest.raises(MatterportIngestionError) as info:
        _run(tmp_path, FakeGraph(_graph_failure(kind)), _ok_cdn(), "m1")
    assert "zero valid" in str(info.value)
    files = _files(tmp_path)
    assert not [f for f in files if f.endswith((".jpg", ".tmp"))]
    manifest = json.loads((tmp_path / "out" / "source_manifest.json").read_text())
    assert manifest["records"] == []
    _assert_no_secrets(json.dumps(manifest))


@pytest.mark.parametrize("kind,attempts", [("timeout", 3), ("500", 3), ("429", 3), ("401", 1), ("403", 1)])
def test_retry_policy_only_retries_transient_failures(tmp_path, kind, attempts):
    graph = FakeGraph(_graph_failure(kind))
    with pytest.raises(MatterportIngestionError):
        _run(tmp_path, graph, _ok_cdn(), "m1", max_retries=2)
    assert graph.calls == attempts


def test_auth_failure_error_names_model_and_status_without_secrets(tmp_path):
    with pytest.raises(MatterportIngestionError):
        _run(tmp_path, FakeGraph(_graph_failure("401")), _ok_cdn(), "m1")
    summary = json.loads((tmp_path / "out" / "source_manifest.json").read_text())["summary"]
    assert summary["models_failed"] == 1
    assert any("m1" in e and "401" in e for e in summary["errors"])


@pytest.mark.parametrize("cdn_kind", ["403", "404", "truncated-jpeg", "html-200", "empty-200",
                                      "timeout", "redirect-private"])
def test_cdn_face_failures_leave_no_partial_files(tmp_path, cdn_kind):
    def handler(url):
        if cdn_kind == "timeout":
            raise httpx.ReadTimeout("injected")
        return {
            "403": FakeResponse(403), "404": FakeResponse(404),
            "truncated-jpeg": FakeResponse(200, content=jpeg_bytes()[:40]),
            "html-200": FakeResponse(200, content=b"<html>login</html>"),
            "empty-200": FakeResponse(200, content=b""),
            "redirect-private": FakeResponse(302, headers={"Location": "https://10.0.0.5/x.jpg"}),
        }[cdn_kind]
    with pytest.raises(MatterportIngestionError):
        _run(tmp_path, _ok_graph(), FakeCdn(handler), "m1")
    assert not [f for f in _files(tmp_path) if f.endswith((".jpg", ".tmp"))]
    manifest_text = (tmp_path / "out" / "source_manifest.json").read_text()
    _assert_no_secrets(manifest_text)


def test_one_bad_model_does_not_poison_good_model(tmp_path):
    graph = FakeGraph(lambda m: FakeResponse(401) if m == "bad" else FakeResponse(json_data=panos_body(m)))
    (manifest, report), _ = _run(tmp_path, graph, _ok_cdn(), "good", "bad")
    assert report.models_succeeded == 1 and report.models_failed == 1
    assert {r["model_id"] for r in manifest["records"]} == {"good"}
    assert len(manifest["records"]) == 4
    for record in manifest["records"]:
        assert (tmp_path / "out" / record["image_path"]).is_file()


# Manifest preservation: regressions for the fix in 9a6fea1 (index/matterport.py merged_records).

def test_failed_rerun_preserves_previous_good_manifest(tmp_path):
    """End-to-end: a real (fake-session) ingest, then a total auth failure."""
    _run(tmp_path, _ok_graph(), _ok_cdn(), "m1")
    good = json.loads((tmp_path / "out" / "source_manifest.json").read_text())["records"]
    with pytest.raises(MatterportIngestionError, match="preserved"):
        _run(tmp_path, FakeGraph(_graph_failure("401")), _ok_cdn(), "m1")
    after = json.loads((tmp_path / "out" / "source_manifest.json").read_text())["records"]
    assert after == good


def test_partial_rerun_keeps_previously_ingested_model_records(tmp_path):
    _run(tmp_path, _ok_graph(), _ok_cdn(), "m1", "m2")
    before = {r["shot_id"]: r for r in
              json.loads((tmp_path / "out" / "source_manifest.json").read_text())["records"]}
    graph = FakeGraph(lambda m: FakeResponse(503) if m == "m1" else FakeResponse(json_data=panos_body(m)))
    (manifest, report), _ = _run(tmp_path, graph, _ok_cdn(), "m1", "m2", max_retries=0)
    assert report.models_failed == 1
    assert {r["model_id"] for r in manifest["records"]} == {"m1", "m2"}
    m1_after = {r["shot_id"]: r for r in manifest["records"] if r["model_id"] == "m1"}
    assert m1_after == {k: v for k, v in before.items() if v["model_id"] == "m1"}
    assert len(manifest["records"]) == len(before)  # no duplicates after merge


def test_preserved_records_require_valid_local_images(tmp_path):
    """A prior record is only carried forward if its image is still a valid local file;
    a deleted or corrupted image must not be re-published by a failed refresh."""
    _run(tmp_path, _ok_graph(), _ok_cdn(), "m1")
    out = tmp_path / "out"
    records = json.loads((out / "source_manifest.json").read_text())["records"]
    (out / records[0]["image_path"]).unlink()
    (out / records[1]["image_path"]).write_bytes(b"<html>not a jpeg</html>")
    with pytest.raises(MatterportIngestionError):
        _run(tmp_path, FakeGraph(_graph_failure("401")), _ok_cdn(), "m1")
    kept = {r["shot_id"] for r in json.loads((out / "source_manifest.json").read_text())["records"]}
    assert kept == {r["shot_id"] for r in records[2:]}


def test_spatial_sampling_drops_colocated_duplicates(tmp_path):
    graph = FakeGraph(lambda m: FakeResponse(json_data={"data": {"model": {"panoLocations": [
        pano(m, "a", x=0.0), pano(m, "b", x=0.1), pano(m, "c", x=6.0)]}}}))
    (manifest, report), _ = _run(tmp_path, graph, _ok_cdn(), "m1")
    assert {r["sweep_id"] for r in manifest["records"]} == {"a", "c"}


def test_unready_pano_does_not_suppress_nearby_ready_pano(tmp_path):
    """Regression for Codex P2 (fixed in 9a6fea1: select_spread_panos validates readiness first)."""
    graph = FakeGraph(lambda m: FakeResponse(json_data={"data": {"model": {"panoLocations": [
        pano(m, "pending", x=0.0, status="processing"), pano(m, "ready", x=0.1)]}}}))
    (manifest, _report), _ = _run(tmp_path, graph, _ok_cdn(), "m1")
    assert {r["sweep_id"] for r in manifest["records"]} == {"ready"}
