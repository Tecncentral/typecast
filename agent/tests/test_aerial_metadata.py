import json
import math
import os
import subprocess

from PIL import Image
import pytest

from agent.aerial_metadata import AerialMetadataUnavailable, read_aerial_metadata


@pytest.fixture
def aerial_cache(tmp_path):
    directory = tmp_path / "vexcel" / "12345"
    directory.mkdir(parents=True)
    lat, lon = 40., -74.
    x = 6_378_137 * math.radians(lon)
    y = 6_378_137 * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    (directory / "aerial-extent.json").write_text(json.dumps([x - 200, y - 200, x + 200, y + 200]))
    (directory / "source-coordinates.json").write_text(json.dumps([lat, lon]))
    (directory / "logistics.json").write_text(json.dumps({
        "schema_version": 1, "property_id": "12345", "coordinates": [lat, lon],
        "logistics": {"property_id": "12345", "private_field": "must stay private"},
        "private_provider_payload": "must stay private",
    }))
    Image.new("RGB", (32, 24)).save(directory / "aerial.png")
    return tmp_path, directory


def assert_unavailable(root, property_id="12345"):
    with pytest.raises(AerialMetadataUnavailable, match=r"^Aerial metadata unavailable\.$") as error:
        read_aerial_metadata(property_id, root)
    assert str(root) not in str(error.value)


def test_returns_only_bound_georeferencing(aerial_cache):
    root, directory = aerial_cache
    result = read_aerial_metadata("12345", root)
    assert result == {
        "property_id": "12345", "crs": "EPSG:3857",
        "extent": json.loads((directory / "aerial-extent.json").read_text()),
        "width": 32, "height": 24,
        "image_path": "cache/vexcel/12345/aerial.png", "coordinates": [40., -74.],
    }


def test_api_returns_only_safe_metadata_and_keeps_missing_response_generic(aerial_cache, monkeypatch):
    from fastapi.testclient import TestClient
    from agent import app as app_module

    root, _ = aerial_cache
    monkeypatch.setattr("agent.aerial_metadata.read_aerial_metadata",
                        lambda property_id, _: read_aerial_metadata(property_id, root))
    client = TestClient(app_module.app)
    response = client.get("/api/aerial/12345")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == read_aerial_metadata("12345", root)
    assert "private" not in response.text
    missing = client.get("/api/aerial/99999")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Aerial metadata unavailable."}
    assert missing.headers["cache-control"] == "no-store"
    assert client.get("/cache/vexcel/12345/aerial-extent.json").status_code == 404


@pytest.mark.parametrize("property_id", ["../12345", "12345/..", "1/2345", "", "mock-p1",
                                         "1234567890123", "１２３４５", 12345, None])
def test_rejects_ids_outside_numeric_allowlist(aerial_cache, property_id):
    assert_unavailable(aerial_cache[0], property_id)


@pytest.mark.parametrize("extent", [[0, 0, 0, 1], [2, 0, 1, 1], [0, 2, 1, 1],
                                     [0, 0, 1], [False, 0, 1, 1], ["0", 0, 1, 1],
                                     [0, 0, float("nan"), 1], [0, 0, float("inf"), 1],
                                     {"extent": [0, 0, 1, 1]}, [0, 0, 1, 1]])
def test_rejects_invalid_or_unbound_extent(aerial_cache, extent):
    root, directory = aerial_cache
    (directory / "aerial-extent.json").write_text(json.dumps(extent))
    assert_unavailable(root)


@pytest.mark.parametrize("field,value", [("coordinates", [41., -74.]),
                                         ("coordinates", [True, -74.]),
                                         ("property_id", "67890"), ("schema_version", True),
                                         ("logistics", {"property_id": "67890"}),
                                         ("logistics", None)])
def test_rejects_mismatched_record_binding(aerial_cache, field, value):
    root, directory = aerial_cache
    target = directory / "logistics.json"
    record = json.loads(target.read_text())
    record[field] = value
    target.write_text(json.dumps(record))
    assert_unavailable(root)


@pytest.mark.parametrize("coordinates", [[91., -74.], [40., -181.], [True, -74.],
                                          [float("nan"), -74.], [40.], [41., -74.]])
def test_rejects_invalid_or_mismatched_source_coordinates(aerial_cache, coordinates):
    root, directory = aerial_cache
    (directory / "source-coordinates.json").write_text(json.dumps(coordinates))
    assert_unavailable(root)


@pytest.mark.parametrize("filename", ["aerial.png", "aerial-extent.json", "source-coordinates.json", "logistics.json"])
def test_rejects_missing_cache_component(aerial_cache, filename):
    root, directory = aerial_cache
    (directory / filename).unlink()
    assert_unavailable(root)


@pytest.mark.parametrize("filename", ["aerial.png", "aerial-extent.json", "source-coordinates.json", "logistics.json"])
def test_rejects_malformed_cache_component(aerial_cache, filename):
    root, directory = aerial_cache
    (directory / filename).write_bytes(b"invalid cache data")
    assert_unavailable(root)


def link_directory(link, target):
    """Create a directory alias without needing special privileges.

    Uses a real symlink when permitted. Windows accounts without the symlink
    privilege get a junction (mklink /J), which also resolves to another path
    and therefore exercises the same containment check. Never changes privileges.
    """
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        if done.returncode != 0:
            pytest.skip("neither symlink nor junction creation is available")


def test_rejects_property_directory_symlink(aerial_cache, tmp_path):
    root, directory = aerial_cache
    other = tmp_path / "other-property"
    directory.rename(other)
    link_directory(directory, other)
    assert directory.resolve() != directory  # the alias is real
    assert_unavailable(root)


def test_rejects_vexcel_directory_symlink(aerial_cache, tmp_path):
    root, _ = aerial_cache
    other = tmp_path / "other-vexcel"
    (root / "vexcel").rename(other)
    link_directory(root / "vexcel", other)
    assert (root / "vexcel").resolve() != root / "vexcel"
    assert_unavailable(root)


CACHE_FILES = ["aerial.png", "aerial-extent.json", "source-coordinates.json", "logistics.json"]


@pytest.mark.parametrize("filename", CACHE_FILES)
def test_rejects_symlinked_cache_file(aerial_cache, tmp_path, filename):
    root, directory = aerial_cache
    original = directory / filename
    outside = tmp_path / filename
    original.rename(outside)
    try:
        original.symlink_to(outside)
    except OSError:
        pytest.skip("file symlinks need a privilege this account lacks (Windows junctions cannot alias files); "
                    "test_rejects_aliased_cache_file covers the same check portably")
    assert_unavailable(root)


@pytest.mark.parametrize("filename", CACHE_FILES)
def test_rejects_aliased_cache_file(aerial_cache, monkeypatch, filename):
    """Portable equivalent: make one cache file resolve elsewhere, as a symlink would."""
    root, directory = aerial_cache
    victim = directory / filename
    real_resolve = type(victim).resolve

    def resolve(self, *args, **kwargs):
        resolved = real_resolve(self, *args, **kwargs)
        return resolved.with_name("elsewhere-" + resolved.name) if resolved == victim else resolved

    monkeypatch.setattr(type(victim), "resolve", resolve)
    assert_unavailable(root)


def test_rejects_non_png_image(aerial_cache):
    root, directory = aerial_cache
    Image.new("RGB", (32, 24)).save(directory / "aerial.png", format="JPEG")
    assert_unavailable(root)
