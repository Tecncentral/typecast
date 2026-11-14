"""Synthetic contracts for live adapters; never used as live source fallbacks."""
import base64
import io
import json

from PIL import Image
import pytest
import requests
from shapely.geometry import Point, Polygon, mapping

from contracts.schemas import Logistics, Property
from data import vexcel_tools
from data.vexcel_client import ProviderError, VexcelClient
from data.vexcel_geometry import (mapped_walk, noise_flags, parcel_and_footprint,
                                 parking_candidate, project, segmented_parking)
from data.vexcel_precompute import derive_logistics, indexed_property_ids, precompute_property


def property_record():
    return Property(property_id="test-p1", address="Synthetic", city="Test", type="office",
                    lat=0, lon=0, parking_flags={"hasNoParkingAvailable": False})


def segmentation(mask=None, pixel_size=None):
    mask = mask or Image.new("L", (10, 10), color=255)
    content = io.BytesIO()
    mask.save(content, format="PNG")
    detection = {"imageId": "ortho-1", "confidence": .9,
                 "bbox": "POLYGON ((0 0,0.001 0,0.001 0.001,0 0.001,0 0))",
                 "pixel-bbox": [0, 0, *(pixel_size or mask.size)],
                 "pixel-mask": base64.b64encode(content.getvalue()).decode()}
    return {"features": [{"properties": {"label": "parking lot", "detections": [detection]}}],
            "images": [{"image-id": "ortho-1", "metadata": {"srid": 4326}}]}


def test_mask_trace_preserves_holes_and_deduplicates_overlap():
    mask = Image.new("L", (10, 10), color=255)
    for x in range(3, 7):
        for y in range(3, 7):
            mask.putpixel((x, y), 0)
    data = segmentation(mask)
    data["features"] *= 2
    polygon = segmented_parking(data, 0, 0)
    assert polygon is not None and len(polygon.interiors) == 1
    assert polygon.area == pytest.approx(.001 * .001 * .84)
    # A bounding rectangle would fill the genuine masked-out courtyard.
    assert not polygon.covers(Point(.0005, .0005))


def test_no_mask_never_promotes_search_or_detection_box_to_parking():
    data = segmentation()
    del data["features"][0]["properties"]["detections"][0]["pixel-mask"]
    assert segmented_parking(data, 0, 0) is None
    data = segmentation(pixel_size=(50, 50))
    assert segmented_parking(data, 0, 0) is None
    logistics, _, _ = derive_logistics(property_record(), {"search": {"features": [{"geometry": mapping(Polygon([(0,0),(1,0),(1,1),(0,0)]))}]}}, None)
    assert logistics.car_spaces is None and logistics.parking_polygon == []
    assert logistics.walk_m is None and logistics.noise_status == "unknown"


def test_nearest_parcel_is_not_silently_a_property_join():
    far = Polygon([(1,1),(2,1),(2,2),(1,1)])
    assert parcel_and_footprint({"features": [{"geometry": mapping(far)}]}, 0, 0) == (None, None, None)


def test_hardscape_is_not_automatically_confirmed_parking():
    parcel = Polygon([(-.01,-.01),(.01,-.01),(.01,.01),(-.01,.01),(-.01,-.01)])
    data = {"features": [{"geometry": mapping(parcel), "properties": {"hardscapes.area": 900, "structures": []}}]}
    result, _, _ = derive_logistics(property_record(), {"property": data}, None)
    assert result.car_spaces is None
    assert any("not parking capacity" in e.claim for e in result.source_evidence)
    assert any(e.source == "costar" and e.status == "measured" for e in result.source_evidence)
    data["features"][0]["properties"]["structures"] = None
    assert derive_logistics(property_record(), {"property": data}, None)[0].car_spaces is None


def test_shared_pool_reallocates_for_refine_without_double_counting():
    original = Logistics(property_id="test", truck_spaces=0, car_spaces=50,
                         parking_area_m2=1500, parking_status="estimated")
    first = vexcel_tools.allocate_parking(original, 3)
    second = vexcel_tools.allocate_parking(first, 5)
    assert (first.truck_spaces, first.car_spaces) == (3, 38)
    assert (second.truck_spaces, second.car_spaces) == (5, 30)
    assert not vexcel_tools.enough_parking(second, 6, 30)
    assert vexcel_tools.enough_parking(second, 5, 30)
    assert original.truck_spaces == 0
    assert not vexcel_tools.enough_parking(Logistics(property_id="unknown"), 0, 0)


@pytest.mark.parametrize("area", [-1, float("nan"), float("inf"), True])
def test_invalid_area_never_becomes_capacity(area):
    with pytest.raises(ValueError):
        vexcel_tools.spaces_from_area(area)


def test_runtime_cache_missing_invalid_or_image_missing_is_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(vexcel_tools, "ROOT", tmp_path)
    monkeypatch.setattr(vexcel_tools, "USE_MOCKS", False)
    with pytest.raises(FileNotFoundError):
        vexcel_tools.plan_logistics("test-p1")
    directory = tmp_path / "cache/vexcel/test-p1"
    directory.mkdir(parents=True)
    value = Logistics(property_id="test-p1", aerial_image_path="cache/vexcel/test-p1/aerial-logistics.png")
    cache = {"schema_version": 1, "property_id": "test-p1", "logistics": value.model_dump()}
    (directory / "logistics.json").write_text(json.dumps(cache))
    result = vexcel_tools.plan_logistics("test-p1")
    assert result.aerial_image_path is None
    cache["logistics"]["aerial_image_path"] = "cache/threads/private.json"
    (directory / "logistics.json").write_text(json.dumps(cache))
    with pytest.raises(RuntimeError, match="invalid"):
        vexcel_tools.plan_logistics("test-p1")
    with pytest.raises(ValueError):
        vexcel_tools.plan_logistics("../escape")


def test_offline_cache_preserves_unknown_and_never_calls_provider(tmp_path):
    class Forbidden:
        def __getattr__(self, name):
            pytest.fail("Offline mode called a provider")
    result = precompute_property(property_record(), Forbidden(), cache_root=tmp_path, offline=True)
    assert result["logistics"]["car_spaces"] is None
    assert result["logistics"]["walk_m"] is None
    assert not result["logistics"]["aerial_image_path"]
    assert set(result["failures"]) == {"property", "search", "detection", "osm", "aerial"}


def test_failed_coordinate_refresh_never_rebinds_old_sources(tmp_path):
    old = property_record()
    directory = tmp_path / "vexcel/test-p1"
    directory.mkdir(parents=True)
    (directory / "source-coordinates.json").write_text("[0, 0]")
    (directory / "detection.json").write_text(json.dumps(segmentation()))
    (directory / "private-old-evidence.txt").write_text("preserve this generation")
    changed = old.model_copy(update={"lat": 1.0, "lon": 1.0})
    with pytest.raises(RuntimeError, match="coordinates changed"):
        precompute_property(changed, None, cache_root=tmp_path, offline=True)
    class Failed:
        def __getattr__(self, name):
            def call(*args):
                raise ProviderError("Synthetic network failure")
            return call
    result = precompute_property(changed, Failed(), cache_root=tmp_path, refresh=True)
    assert result["logistics"]["car_spaces"] is None
    assert not (directory / "detection.json").exists()
    archived = list((tmp_path / "vexcel/.history/test-p1").glob("*/private-old-evidence.txt"))
    assert len(archived) == 1 and archived[0].read_text() == "preserve this generation"
    assert json.loads((directory / "source-coordinates.json").read_text()) == [1, 1]
    offline = precompute_property(changed, None, cache_root=tmp_path, offline=True)
    assert not offline["sources"]["detection"] and offline["logistics"]["car_spaces"] is None


def test_network_failures_redact_credential_query_urls():
    class Session:
        def request(self, *args, **kwargs):
            raise requests.ConnectionError("https://provider/?api_key=SECRET")
    with pytest.raises(ProviderError) as failure:
        VexcelClient("SECRET", session=Session()).property(0, 0)
    assert "SECRET" not in str(failure.value) and "api_key" not in str(failure.value)


def test_key_only_goes_to_official_host_and_redirects_disabled():
    calls = []
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield b'{"features":[],"elements":[]}'
    class Session:
        def request(self, method, url, **kwargs):
            calls.append((url, kwargs))
            return Response()
    client = VexcelClient("SECRET", session=Session())
    client.property(0, 0)
    client.osm(0, 0)
    assert calls[0][0].startswith("https://api.vexcelgroup.com/v2/")
    assert calls[0][1]["params"]["api_key"] == "SECRET"
    assert "SECRET" not in str(calls[1])
    assert all(not kw["allow_redirects"] for _, kw in calls)
    with pytest.raises(ValueError):
        client._get("https://unexpected.example", {})


def test_noise_distance_thresholds_and_empty_lookup_semantics():
    def way(tags, x):
        return {"type": "way", "tags": tags, "geometry": [{"lon": x,"lat": -.001},{"lon": x,"lat": .001}]}
    data = {"elements": [way({"highway":"motorway"}, .001),
                         way({"railway":"rail"}, .002), way({"aeroway":"runway"}, .02),
                         way({"highway":"motorway"}, .01)]}
    flags = noise_flags(data, 0, 0)
    assert len(flags) == 3 and any("Freeway" in f for f in flags)
    result, _, _ = derive_logistics(property_record(), {"osm": {"elements": []}}, None)
    assert result.noise_status == "estimated" and result.noise_flags == []
    assert "does not establish quiet" in result.source_evidence[-1].claim


def test_walking_requires_connected_source_entrance_and_path():
    parking = Polygon([(-.001,-.001),(.0001,-.001),(.0001,.001),(-.001,.001),(-.001,-.001)])
    footprint = Polygon([(.0009,-.001),(.002,-.001),(.002,.001),(.0009,.001),(.0009,-.001)])
    osm = {"elements": [{"type":"way", "tags":{"highway":"footway"}, "nodes":[1,2],
                         "geometry":[{"lon":0,"lat":0},{"lon":.001,"lat":0}]},
                        {"type":"node", "id":2, "lon":.001,"lat":0, "tags":{"entrance":"main"}}]}
    assert mapped_walk(osm, parking, footprint, 0, 0) == pytest.approx(111.2, abs=.1)
    osm["elements"][0]["tags"]["access"] = "private"
    assert mapped_walk(osm, parking, footprint, 0, 0) is None
    del osm["elements"][0]["tags"]["access"]
    osm["elements"][1]["tags"]["access"] = "private"
    assert mapped_walk(osm, parking, footprint, 0, 0) is None
    del osm["elements"][1]["tags"]["access"]
    osm["elements"][1]["tags"]["foot"] = "no"
    assert mapped_walk(osm, parking, footprint, 0, 0) is None


def test_generation_index_is_used_and_path_traversal_rejected(tmp_path):
    (tmp_path / "generation").mkdir()
    (tmp_path / "CURRENT").write_text("generation")
    (tmp_path / "generation/shots.json").write_text('[{"property_id":"test-p1"},{"property_id":"test-p1"}]')
    assert indexed_property_ids(tmp_path) == ["test-p1"]
    (tmp_path / "CURRENT").write_text("../outside")
    with pytest.raises(ValueError):
        indexed_property_ids(tmp_path)
