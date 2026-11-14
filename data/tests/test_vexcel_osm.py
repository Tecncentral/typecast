"""OSM transport failures and source uncertainty, using synthetic responses."""
import json

from PIL import Image
import pytest

from contracts.schemas import Property
from data.vexcel_client import OVERPASS_ENDPOINTS, OVERPASS_URL, ProviderError, VexcelClient, overpass_query
from data.vexcel_precompute import precompute_property


class Response:
    def __init__(self, status=200, content=b'{"elements":[]}'):
        self.status_code = status
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield self.content


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def test_osm_explicit_endpoint_no_key_or_automatic_rotation(monkeypatch):
    selected = "https://overpass-api.de/api/interpreter"
    monkeypatch.setenv("TYPECAST_OVERPASS_URL", selected)
    session = Session(Response(406))
    client = VexcelClient("synthetic-secret", session=session)
    with pytest.raises(ProviderError, match="OSM HTTP 406"):
        client.osm(34, -118)
    assert len(session.calls) == 1
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", selected)
    assert "synthetic-secret" not in str(session.calls)
    assert not kwargs["allow_redirects"]
    assert "Typecast" in kwargs["headers"]["User-Agent"]
    assert kwargs["timeout"] == (10, 55)


@pytest.mark.parametrize("endpoint", [
    "https://unexpected.example/interpreter",
    OVERPASS_URL + "?api_key=synthetic-secret",
    "http://ovp.dresel.systems/api-na/interpreter",
])
def test_unlisted_endpoint_rejected_before_request(endpoint):
    session = Session(Response())
    with pytest.raises(ProviderError, match="allowlist"):
        VexcelClient("synthetic-secret", session=session, overpass_url=endpoint)
    assert not session.calls


def test_partial_overpass_results_remain_unavailable(monkeypatch):
    monkeypatch.delenv("TYPECAST_OVERPASS_URL", raising=False)
    session = Session(Response(content=b'{"elements":[],"remark":"runtime error: timed out"}'))
    with pytest.raises(ProviderError, match="partial results"):
        VexcelClient("synthetic-secret", session=session).osm(34, -118)
    assert session.calls[0][1] == OVERPASS_URL
    assert OVERPASS_URL in OVERPASS_ENDPOINTS


def test_osm_query_is_bounded_and_invalid_coordinates_never_request():
    query = overpass_query(34, -118)
    assert "[timeout:30]" in query and "[maxsize:67108864]" in query
    assert "around:3050" in query and "out body geom;" in query
    session = Session(Response())
    client = VexcelClient("synthetic-secret", session=session)
    for lat, lon in [(float("nan"), 0), (0, float("inf")), (90, 0), (0, -181)]:
        with pytest.raises(ValueError, match="coordinates"):
            client.osm(lat, lon)
    assert not session.calls


def test_vexcel_403_is_coverage_failure_without_body_or_credentials():
    session = Session(Response(403, b'private provider body: synthetic-secret'))
    with pytest.raises(ProviderError, match="outside Vexcel coverage") as failure:
        VexcelClient("synthetic-secret", session=session).property(34, -118)
    assert str(failure.value) == "Vexcel HTTP 403: outside Vexcel coverage"


def test_osm_repair_reuses_vexcel_successes_and_derives_real_mapped_parking(tmp_path):
    directory = tmp_path / "vexcel/test-osm-repair"
    directory.mkdir(parents=True)
    for filename in ("property.json", "search.json", "detection.json"):
        (directory / filename).write_text('{"features": []}')
    (directory / "aerial-extent.json").write_text("[-200, -200, 200, 200]")
    Image.new("RGB", (1024, 1024)).save(directory / "aerial.png")
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    ring = [(0, 0), (.001, 0), (.001, .001), (0, .001), (0, 0)]
    osm = {"elements": [{"type": "way", "id": 1,
                         "tags": {"amenity": "parking", "parking": "surface"},
                         "geometry": [{"lon": x, "lat": y} for x, y in ring]}]}

    class OSMOnly:
        def __init__(self):
            self.calls = 0

        def osm(self, lat, lon):
            self.calls += 1
            return osm

        def __getattr__(self, name):
            pytest.fail("A missing-OSM repair attempted to refresh a successful Vexcel source")

    client = OSMOnly()
    prop = Property(property_id="test-osm-repair", address="Synthetic", city="Test", type="office", lat=0, lon=0)
    record = precompute_property(prop, client, cache_root=tmp_path)
    assert client.calls == 1 and not record["failures"]
    assert all((directory / name).read_bytes() == content for name, content in before.items())
    assert json.loads((directory / "osm.json").read_text()) == osm
    logistics = record["logistics"]
    assert logistics["parking_status"] == "estimated" and logistics["car_spaces"] > 0
    assert any("OSM mapped" in evidence["claim"] for evidence in logistics["source_evidence"])
    assert logistics["walk_m"] is None and logistics["walk_status"] == "unknown"
    assert logistics["noise_status"] == "estimated" and not logistics["noise_flags"]
    assert any("does not establish quiet" in evidence["claim"] for evidence in logistics["source_evidence"])

    # Once repaired, offline derivation uses the same raw source with no calls.
    offline = precompute_property(prop, None, cache_root=tmp_path, offline=True)
    assert offline["logistics"]["car_spaces"] == logistics["car_spaces"]
    assert not offline["failures"]
