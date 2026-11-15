"""ObliqueClient: endpoint allowlist, 429 retry, spend guard and request fields. HTTP is faked."""

import json
import re

import pytest
import requests

from data import vexcel_budget as budget
from data import vexcel_oblique as vo
from data.vexcel_client import VEXCEL_BASE, ProviderError, VexcelClient

KEY = "SECRET-KEY-VALUE"

# Request fields from the public Vexcel specs (api.vexcelgroup.com/v2/api-docs/*), read 2026-11-15.
EMBEDDING_PARAMS = {
    "buffer-meter", "collect-year", "collection", "graysky-event", "include", "layer",
    "max-first-capture-date", "max-first-publish-date", "max-last-capture-date", "max-last-publish-date",
    "min-first-capture-date", "min-first-publish-date", "min-last-capture-date", "min-last-publish-date",
    "page", "page-size", "search-image", "search-location", "search-refinement", "search-text",
    "search-url", "search-vector", "source.product-type", "total-records", "wkt",
}  # fmt: skip
EMBEDDING_PRODUCT_TYPES = {
    "all",
    "oblique",
    "oblique-north",
    "oblique-south",
    "oblique-east",
    "oblique-west",
    "final-ortho",
}
EMBEDDING_INCLUDE = {
    "score",
    "geometry",
    "quadkey",
    "collection",
    "vector",
    "search-vector",
    "product-type",
    "refinement-score",
}
ORIENTED_PARAMS = {
    "attribution", "bands", "bbox-dimensions", "buffer-meter", "buffer-pixel", "collect-year", "collection",
    "crop", "crosshair", "crosshair-color", "crosshair-line-width", "dem-priority", "destination-dimensions",
    "downsample", "graysky-event", "image-format", "image-name", "layer", "max-capture-date",
    "max-first-publish-date", "max-last-publish-date", "min-capture-date", "min-first-publish-date",
    "min-last-publish-date", "order-by", "product-type", "rotation", "spatial-operation", "srid", "wkt",
}  # fmt: skip
ORIENTED_PRODUCT_TYPES = {
    "nadir",
    "oblique-north",
    "oblique-south",
    "oblique-east",
    "oblique-west",
}
ORIENTED_ORDER_BY = {
    "layer-asc", "layer-desc", "image-name-asc", "image-name-desc", "image-center-distance-asc",
    "image-center-distance-desc", "image-border-distance-asc", "image-border-distance-desc",
    "collection-first-capture-date-asc", "collection-first-capture-date-desc",
    "collection-last-capture-date-asc", "collection-last-capture-date-desc", "image-date-asc",
    "image-date-desc", "collection-avg-gsd-asc", "collection-avg-gsd-desc",
}  # fmt: skip
ORIENTED_IMAGE_FORMATS = {"jpeg", "png", "tiff", "jpeg/png"}
ORIENTED_LAYERS = {"urban", "urban-r", "urban-g", "wide-area", "graysky", "graysky-g"}
DTM_PARAMS = {"dem-priority", "srid", "unit-system", "wkt"}
DSM_PARAMS = {
    "collect-year", "collection", "layer", "max-first-capture-date", "max-first-publish-date",
    "max-last-capture-date", "max-last-publish-date", "min-first-capture-date", "min-first-publish-date",
    "min-last-capture-date", "min-last-publish-date", "order-by", "srid", "unit-system", "wkt",
}  # fmt: skip

TILES = json.dumps(
    {
        "features": [
            {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-118.25, 34.04],
                            [-118.24, 34.04],
                            [-118.24, 34.05],
                            [-118.25, 34.04],
                        ]
                    ],
                },
                "properties": {"score": 0.2, "quadkey": "0231", "collection": "c1"},
            }
        ]
    }
).encode()
ELEVATION = json.dumps(
    {"wkt": "LINESTRING Z(-118.3 34.1 345.7, -118.3 34.13 464.4)"}
).encode()


class FakeResponse:
    def __init__(self, status=200, body=b""):
        self.status_code, self._body = status, body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, size):
        yield self._body


class FakeSession:
    def __init__(self, *responses):
        self.queue, self.calls = list(responses), []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        assert self.queue, "unexpected extra HTTP request"
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "cache" / "vexcel" / "ledger.jsonl"
    monkeypatch.setattr(budget, "LEDGER", path)
    return path


@pytest.fixture
def sleeps(monkeypatch):
    waited = []
    monkeypatch.setattr(vo.time, "sleep", waited.append)
    return waited


def client_with(*responses):
    session = FakeSession(*responses)
    return vo.ObliqueClient(api_key=KEY, session=session), session


def ledger_rows(path):
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def params_of(session, index=0):
    return {k: v for k, v in session.calls[index]["params"].items() if k != "api_key"}


# --- allowlist -------------------------------------------------------------------------------------------


def test_allowlist_is_exactly_the_four_intended_endpoints():
    assert vo.ENDPOINTS == {
        "embedding/extract",
        "oriented/extract",
        "dtm/elevation",
        "dsm/elevation",
    }


@pytest.mark.parametrize(
    "endpoint",
    [
        "embedding/refine", "oriented/query", "oriented/tile", "dtm/extract", "dtm/tile", "embedding/collections",
        "property/extract", "ortho/extract", "elements/detect", "../dtm/elevation", "dtm/elevation/", "DTM/elevation", "",
    ],
)  # fmt: skip
def test_unlisted_endpoints_are_rejected_before_the_ledger_and_the_network(
    ledger, endpoint
):
    client, session = client_with()
    with pytest.raises(ValueError, match="Unsupported Vexcel endpoint"):
        client._call(endpoint, {})
    assert session.calls == [] and not ledger.exists()


@pytest.mark.parametrize("endpoint", sorted(vo.ENDPOINTS))
def test_each_intended_endpoint_is_sent_once_to_the_documented_url_without_redirects(
    ledger, endpoint
):
    client, session = client_with(FakeResponse(200, b"{}"))
    client._call(endpoint, {"wkt": "POINT(1 2)"})
    (call,) = session.calls
    assert call["method"] == "GET" and call["url"] == VEXCEL_BASE + endpoint
    assert call["allow_redirects"] is False and call["params"]["api_key"] == KEY
    assert [r["endpoint"] for r in ledger_rows(ledger)] == [endpoint]


def test_the_base_client_allowlist_is_unchanged():
    client, session = client_with()
    for endpoint in ("oriented/extract", "dtm/elevation", "dsm/elevation"):
        with pytest.raises(ValueError):
            client._get(endpoint, {})
    assert session.calls == [] and isinstance(client, VexcelClient)


# --- 429 retry -------------------------------------------------------------------------------------------


def test_429_is_retried_with_exponential_backoff_then_succeeds(ledger, sleeps):
    client, session = client_with(
        FakeResponse(429), FakeResponse(429), FakeResponse(200, ELEVATION)
    )
    assert client.elevations([(34.1, -118.3), (34.13, -118.3)]) == [345.7, 464.4]
    assert sleeps == [1, 2] and len(session.calls) == 3
    assert len(ledger_rows(ledger)) == 1, (
        "a retry is the same call and is recorded once"
    )


def test_retries_exhausted_raises_without_echoing_url_key_or_body(ledger, sleeps):
    client, session = client_with(
        *[FakeResponse(429, b'{"secret":"provider body"}') for _ in range(6)]
    )
    with pytest.raises(ProviderError) as error:
        client.oblique(34.05, -118.25, "north")
    assert sleeps == [1, 2, 4, 8, 16] and len(session.calls) == 6
    message = str(error.value)
    assert message == "Vexcel HTTP 429: rate limited, retries exhausted"
    assert not any(
        bad in message
        for bad in (KEY, "http", "api_key", "provider body", "vexcelgroup")
    )
    assert error.value.__cause__ is None and error.value.__suppress_context__
    assert len(ledger_rows(ledger)) == 1


def test_other_errors_are_not_retried(ledger, sleeps):
    client, session = client_with(FakeResponse(500))
    with pytest.raises(ProviderError, match="HTTP 500"):
        client.oblique(34.05, -118.25, "east")
    assert sleeps == [] and len(session.calls) == 1
    client, session = client_with(FakeResponse(403))
    with pytest.raises(ProviderError, match="outside Vexcel coverage"):
        client.oblique(40.0, -74.0, "east")
    assert sleeps == [] and len(session.calls) == 1


def test_network_failures_never_carry_the_key(ledger, sleeps):
    client, _ = client_with(
        requests.ConnectionError(f"https://api.vexcelgroup.com/v2/x?api_key={KEY}")
    )
    with pytest.raises(ProviderError) as error:
        client.oblique(34.05, -118.25, "south")
    assert KEY not in str(error.value) and "api_key" not in str(error.value)


def test_a_missing_embedding_collection_is_an_empty_result_not_a_retry(ledger, sleeps):
    client, session = client_with(FakeResponse(404))
    assert client.search_tiles("brick alley", 34.05, -118.25, 3000) == []
    assert sleeps == [] and len(session.calls) == 1


# --- spend guard -----------------------------------------------------------------------------------------


def test_the_guard_refuses_before_any_request_once_a_cap_is_reached(ledger):
    for _ in range(8):
        budget.check_and_record("embedding/extract", 5)
    client, session = client_with(FakeResponse(200, TILES))
    with pytest.raises(budget.BudgetExceeded):
        client.search_tiles("brick alley", 34.05, -118.25, 3000)
    assert session.calls == [] and sum(r["count"] for r in ledger_rows(ledger)) == 40


def test_search_tiles_is_clamped_to_the_per_search_cap_and_recorded_at_that_size(
    ledger,
):
    client, session = client_with(FakeResponse(200, TILES))
    tiles = client.search_tiles("brick alley", 34.05, -118.25, 3000, k=16)
    assert len(tiles) == 1 and tiles[0]["quadkey"] == "0231"
    params = params_of(session)
    assert params["total-records"] == params["page-size"] == 5
    assert [r["count"] for r in ledger_rows(ledger)] == [5]
    client, session = client_with(FakeResponse(200, TILES))
    client.search_tiles("x", 34.05, -118.25, 3000, k=3)
    assert (
        params_of(session)["total-records"] == 3
        and ledger_rows(ledger)[-1]["count"] == 3
    )


def test_the_ledger_records_nothing_about_the_request(ledger):
    client, _ = client_with(FakeResponse(200, TILES))
    client.search_tiles("a very private brick alley query", 34.0123, -118.4567, 3000)
    text = ledger.read_text()
    assert not any(
        bad in text for bad in (KEY, "private", "34.0123", "-118.4567", "http", "wkt")
    )


# --- request fields match the specs ----------------------------------------------------------------------


def test_embedding_extract_request_fields_match_the_spec(ledger):
    client, session = client_with(FakeResponse(200, TILES))
    client.search_tiles("brick alley " * 40, 34.05, -118.25, 3000.7, k=5)
    params = params_of(session)
    assert set(params) <= EMBEDDING_PARAMS
    assert (
        re.fullmatch(r"POINT\(-118\.25 34\.05\)", params["wkt"])
        and params["buffer-meter"] == 3000
    )
    assert params["source.product-type"] in EMBEDDING_PRODUCT_TYPES
    assert set(params["include"].split(",")) <= EMBEDDING_INCLUDE
    assert len(params["search-text"]) <= 300
    assert 1 <= params["total-records"] <= 2500 and 1 <= params["page-size"] <= 500


@pytest.mark.parametrize("direction", vo.DIRECTIONS)
def test_oriented_extract_request_fields_match_the_spec(ledger, direction):
    client, session = client_with(FakeResponse(200, b"\x89PNG"))
    assert (
        client.oblique(34.05, -118.25, direction, size_m=120, width=1024, height=768)
        == b"\x89PNG"
    )
    params = params_of(session)
    assert set(params) <= ORIENTED_PARAMS
    assert (
        params["product-type"] == f"oblique-{direction}"
        and params["product-type"] in ORIENTED_PRODUCT_TYPES
    )
    assert re.fullmatch(r"POINT\(-118\.25 34\.05\)", params["wkt"])
    assert re.fullmatch(r"\d+,\d+", params["bbox-dimensions"])
    assert re.fullmatch(r"\d+,\d+,(fit|fill)", params["destination-dimensions"])
    assert set(params["order-by"].split(",")) <= ORIENTED_ORDER_BY
    assert set(params["layer"].split(",")) <= ORIENTED_LAYERS
    assert (
        params["image-format"] in ORIENTED_IMAGE_FORMATS
        and params["attribution"] == "true"
    )


def test_oriented_extract_rejects_an_unknown_direction_before_any_call(ledger):
    client, session = client_with()
    with pytest.raises(ValueError):
        client.oblique(34.05, -118.25, "up")
    assert session.calls == [] and not ledger.exists()


@pytest.mark.parametrize(
    ("model", "allowed"), [("dtm", DTM_PARAMS), ("dsm", DSM_PARAMS)]
)
def test_elevation_request_fields_match_the_spec(ledger, model, allowed):
    client, session = client_with(
        FakeResponse(200, ELEVATION),
        FakeResponse(200, json.dumps({"wkt": "POINT Z(-118.3 34.1 12.5)"}).encode()),
    )
    client.elevations([(34.1, -118.3), (34.13, -118.3)], model)
    params = params_of(session, 0)
    assert (
        set(params) <= allowed
        and params["wkt"].startswith("LINESTRING(")
        and params["unit-system"] == "metric"
    )
    assert session.calls[0]["url"] == f"{VEXCEL_BASE}{model}/elevation"
    assert client.elevations([(34.1, -118.3)], model) == [12.5]
    assert params_of(session, 1)["wkt"] == "POINT(-118.3 34.1)"


def test_elevation_rejects_bad_models_and_wrong_vertex_counts(ledger):
    client, session = client_with(FakeResponse(200, ELEVATION))
    for model, points in (("dem", [(1.0, 2.0)]), ("dtm", [])):
        with pytest.raises(ValueError):
            client.elevations(points, model)
    with pytest.raises(ProviderError, match="unexpected number of vertices"):
        client.elevations([(34.1, -118.3)], "dtm")
    assert len(session.calls) == 1
