import base64
import io
import json
import os
import pathlib

import duckdb
import pytest
from PIL import Image

import data.costar_tools as costar
import data.vexcel_tools as vexcel
from contracts.schemas import Logistics, Property, Shot
from data import join

MOCKS = pathlib.Path(__file__).resolve().parents[2] / "mocks"
MOCK_MODE = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"


def test_mocks_match_contracts():
    for name, cls in (("shot", Shot), ("property", Property), ("logistics", Logistics)):
        rows = json.loads((MOCKS / f"{name}.json").read_text())
        assert rows and all(cls(**r) for r in rows)


def test_filters():
    assert all(p.available for p in costar.search_costar())
    assert len(costar.search_costar(available_only=False)) > len(costar.search_costar())
    assert all(
        p.year_built is None or p.year_built <= 1992
        for p in costar.search_costar(year_max=1992)
    )
    assert costar.search_costar(city="Nowhere") == []


@pytest.mark.skipif(not MOCK_MODE, reason="mock ids only exist in mock data")
def test_mock_logistics():
    assert vexcel.plan_logistics("mock-p1").truck_spaces == 4
    with pytest.raises(KeyError):
        vexcel.plan_logistics("nope")


def test_spaces_and_enough_parking():
    assert vexcel.spaces_from_area(900) == 30
    plenty = Logistics(property_id="x", truck_spaces=3, car_spaces=30)
    short = Logistics(property_id="x", truck_spaces=2, car_spaces=30)
    assert vexcel.enough_parking(plenty, 3, 30)
    assert not vexcel.enough_parking(short, 3, 30)


ROWS = [
    (
        "syn-1",
        "1 Synthetic St",
        "Los Angeles",
        34.05,
        -118.25,
        "Office",
        1990,
        True,
        10000.0,
        "Test Broker, Synth Realty",
        "m1",
    ),
    (
        "syn-2",
        "2 Placeholder Blvd",
        "Los Angeles",
        34.06,
        -118.26,
        "Industrial",
        1975,
        False,
        25000.0,
        None,
        "m2",
    ),
    (
        "syn-3",
        "3 Unscanned Ave",
        "Los Angeles",
        34.07,
        -118.27,
        "Office",
        None,
        True,
        None,
        None,
        None,
    ),
]


@pytest.fixture
def synthetic_join(tmp_path, monkeypatch):
    path = tmp_path / "cache" / "join.parquet"
    path.parent.mkdir()
    db = duckdb.connect()
    db.execute(
        "CREATE TABLE t(property_id VARCHAR, address VARCHAR, city VARCHAR, lat DOUBLE, lon DOUBLE,"
        " type VARCHAR, year_built INTEGER, available BOOLEAN, size_sqft DOUBLE, contact VARCHAR,"
        " model_id VARCHAR)"
    )
    db.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?,?,?,?)", ROWS)
    db.execute(f"COPY t TO '{path.as_posix()}' (FORMAT parquet)")
    monkeypatch.setattr(costar, "USE_MOCKS", False)
    monkeypatch.setattr(costar, "_JOIN", path)
    monkeypatch.setattr(vexcel, "USE_MOCKS", False)
    monkeypatch.setattr(vexcel, "_JOIN", path)
    monkeypatch.setattr(vexcel, "ROOT", tmp_path)
    monkeypatch.setattr(vexcel, "_CACHE", tmp_path / "cache" / "vexcel")
    return path


class TestSearchCostar:
    def test_only_scanned_properties_are_returned(self, synthetic_join):
        found = costar.search_costar(available_only=False)
        assert {p.property_id for p in found} == {"syn-1", "syn-2"}
        assert all(isinstance(p, Property) and p.model_id for p in found)

    def test_available_only(self, synthetic_join):
        assert [p.property_id for p in costar.search_costar()] == ["syn-1"]

    def test_type_year_size_filters(self, synthetic_join):
        def ids(**kwargs):
            return [
                p.property_id
                for p in costar.search_costar(available_only=False, **kwargs)
            ]

        assert ids(types=["Industrial"]) == ["syn-2"]
        assert ids(year_max=1980) == ["syn-2"]
        assert ids(year_min=1980) == ["syn-1"]
        assert ids(min_sqft=20000) == ["syn-2"]

    def test_limit_and_unknown_city(self, synthetic_join):
        assert len(costar.search_costar(available_only=False, limit=1)) == 1
        assert costar.search_costar(city="Nowhere") == []

    def test_get_property(self, synthetic_join):
        assert costar.get_property("syn-1").contact == "Test Broker, Synth Realty"
        assert costar.get_property("syn-3").year_built is None
        with pytest.raises(KeyError):
            costar.get_property("missing")

    def test_missing_join_file(self, synthetic_join, monkeypatch):
        monkeypatch.setattr(costar, "_JOIN", synthetic_join.parent / "absent.parquet")
        with pytest.raises(FileNotFoundError):
            costar.search_costar()


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows))


def synthetic_property(
    pid, city, market, ptype, events, lat=34.0, lon=-118.0, rba=None, gba=None
):
    address = {
        "streetNumber": "1",
        "streetDirection": None,
        "streetName": "Main",
        "streetType": "St",
        "streetSuffix": None,
        "city": city,
        "state": "CA",
        "postcode": "90001",
        "latitude": lat,
        "longitude": lon,
        "researchMarketId": market,
    }
    return {
        "id": pid,
        "primaryAddress": address,
        "propertyType": ptype,
        "constructionEvents": events,
        "rentableBuildingAreaSquareFeet": rba,
        "grossBuildingAreaSquareFeet": gba,
    }


def test_join_builds_property_and_model_tables(tmp_path, monkeypatch):
    kit = tmp_path / "cache" / "costar"
    (kit / "data").mkdir(parents=True)
    properties = kit / "data" / "commercial-property.jsonl"
    listings = kit / "data" / "commercial-listing-summary.jsonl"
    models = kit / "commercial-properties.csv"
    write_jsonl(
        properties,
        [
            synthetic_property(
                1,
                "Los Angeles",
                20,
                5,
                [{"eventType": 4, "year": 2020}, {"eventType": 2, "year": 1985}],
                rba=5000.0,
            ),
            synthetic_property(
                2, "LOS ANGELES", 20, 2, [{"eventType": 4, "year": 2020}], gba=9000.0
            ),
            synthetic_property(3, "Houston", 14, 5, [{"eventType": 2, "year": 1990}]),
            synthetic_property(4, "Los Angeles", 20, 5, [], lat=None, lon=None),
        ],
    )
    write_jsonl(
        listings,
        [
            {
                "id": 10,
                "propertyId": 1,
                "listingStatus": 1,
                "listingContacts": [
                    {
                        "firstName": "Ann",
                        "lastName": "Test",
                        "locationName": "Synth Realty",
                    }
                ],
            },
            {"id": 11, "propertyId": 2, "listingStatus": 3, "listingContacts": []},
        ],
    )
    models.write_text(
        "PropertyId,MatterportModelId,City\n1,zzz,Los Angeles\n1,aaa,Los Angeles\n"
        "2,,Los Angeles\n3,hhh,Houston\n"
    )
    monkeypatch.setattr(join, "ROOT", tmp_path)
    monkeypatch.setattr(join, "PROPERTIES", properties.as_posix())
    monkeypatch.setattr(join, "LISTINGS", listings.as_posix())
    monkeypatch.setattr(join, "MODELS_CSV", models.as_posix())

    join.build()

    db = duckdb.connect()
    rows = {
        r[0]: r
        for r in db.execute(
            "SELECT property_id, city, type, year_built, available, size_sqft, contact, model_id, address"
            f" FROM read_parquet('{(tmp_path / 'cache' / 'join.parquet').as_posix()}')"
        ).fetchall()
    }
    assert set(rows) == {"1", "2"}, (
        "Houston and the property without coordinates are excluded"
    )
    assert rows["1"] == (
        "1",
        "Los Angeles",
        "Office",
        1985,
        True,
        5000.0,
        "Ann Test, Synth Realty",
        "aaa",
        "1 Main St, Los Angeles, CA, 90001",
    )
    assert rows["2"][1:8] == (
        "Los Angeles",
        "Industrial",
        None,
        False,
        9000.0,
        None,
        None,
    )
    pairs = db.execute(
        f"SELECT * FROM read_parquet('{(tmp_path / 'cache' / 'property_models.parquet').as_posix()}')"
    ).fetchall()
    assert pairs == [("1", "aaa"), ("1", "zzz")]


def fake_detection(min_lat, min_lon, max_lat, max_lon, white_fraction=0.5):
    mask = Image.new("L", (10, 10), 0)
    mask.paste(255, (0, 0, 10, int(10 * white_fraction)))
    buffer = io.BytesIO()
    mask.save(buffer, "PNG")
    ring = [
        (min_lon, min_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
        (min_lon, max_lat),
        (min_lon, min_lat),
    ]
    bbox = "POLYGON((" + ", ".join(f"{x} {y}" for x, y in ring) + "))"
    return {
        "bbox": bbox,
        "confidence": 0.9,
        "pixel-mask": base64.b64encode(buffer.getvalue()).decode(),
    }


class FakeVexcel:
    def __init__(self):
        self.calls = []
        self.parking, self.freeway, self.rail = [], 0, 0

    def __call__(self, method, path, key, *, missing_ok=False, **kwargs):
        self.calls.append(path)
        assert key == "test-key"
        if path == "property/extract":
            return None
        if path == "ortho/extract":
            return type("Response", (), {"content": b"jpeg-bytes"})()
        labels = [e["label"] for e in kwargs["json"]["model-input"]["elements"]]
        if labels == ["parking lot"]:
            detections = [("parking lot", d) for d in self.parking]
        else:
            detections = [("freeway", fake_detection(0, 0, 1, 1))] * self.freeway
            detections += [("railroad tracks", fake_detection(0, 0, 1, 1))] * self.rail
        features = [
            {"properties": {"label": label, "detections": [d]}}
            for label, d in detections
        ]
        return type("Response", (), {"json": lambda self: {"features": features}})()


@pytest.fixture
def vexcel_live(synthetic_join, monkeypatch):
    monkeypatch.setenv("VEXCEL_API_KEY", "test-key")
    fake = FakeVexcel()
    monkeypatch.setattr(vexcel, "_request", fake)
    return fake


class TestPlanLogistics:
    def test_parking_estimate_polygon_image_and_cache(self, vexcel_live):
        vexcel_live.parking = [fake_detection(34.0501, -118.2501, 34.0509, -118.2491)]
        result = vexcel.plan_logistics("syn-1")

        box_m2 = (0.0010 * 111_320 * 0.82903) * (0.0008 * 111_320)
        assert result.car_spaces == pytest.approx(
            box_m2 * 0.5 / vexcel.M2_PER_CAR, abs=2
        )
        assert result.truck_spaces == result.car_spaces // vexcel.CARS_PER_TRUCK
        assert result.estimated is True
        assert result.parking_polygon[0] == [34.0501, -118.2501], "[lat, lon] order"
        assert result.parking_polygon[0] == result.parking_polygon[-1]
        assert result.walk_m is not None and result.noise_flags == []
        assert (vexcel.ROOT / result.aerial_image_path).read_bytes() == b"jpeg-bytes"

        calls_before = len(vexcel_live.calls)
        assert vexcel.plan_logistics("syn-1") == result
        assert len(vexcel_live.calls) == calls_before, (
            "second call is served from cache"
        )
        assert vexcel.aerial_image("syn-1") == result.aerial_image_path

    def test_no_detection_is_unknown_not_a_confirmed_zero(self, vexcel_live):
        result = vexcel.plan_logistics("syn-1")
        assert (result.car_spaces, result.truck_spaces) == (0, 0)
        assert (result.parking_polygon, result.walk_m) == ([], None)
        assert any("no surface parking detected" in flag for flag in result.noise_flags)
        assert result.estimated is True

    def test_noise_flags_need_enough_detections(self, vexcel_live):
        vexcel_live.freeway = vexcel._MIN_FREEWAY_DETECTIONS - 1
        vexcel_live.rail = vexcel._MIN_RAIL_DETECTIONS
        flags = vexcel.plan_logistics("syn-1").noise_flags
        assert not any("freeway" in f for f in flags)
        assert any("rail line" in f for f in flags)

    def test_unknown_property(self, vexcel_live):
        with pytest.raises(KeyError):
            vexcel.plan_logistics("missing")
        assert vexcel_live.calls == []

    def test_missing_join_file(self, vexcel_live, monkeypatch):
        monkeypatch.setattr(vexcel, "_JOIN", vexcel.ROOT / "absent.parquet")
        with pytest.raises(FileNotFoundError):
            vexcel.plan_logistics("syn-1")

    def test_missing_key(self, vexcel_live, monkeypatch):
        monkeypatch.delenv("VEXCEL_API_KEY")
        with pytest.raises(OSError, match="VEXCEL_API_KEY"):
            vexcel.plan_logistics("syn-1")

    def test_geofencing_is_a_clean_skip_and_is_not_cached(
        self, vexcel_live, monkeypatch
    ):
        def geofenced(*args, **kwargs):
            raise vexcel.VexcelUnavailable("geofencing")

        monkeypatch.setattr(vexcel, "_request", geofenced)
        with pytest.raises(FileNotFoundError):
            vexcel.plan_logistics("syn-1")
        assert not (vexcel._CACHE / "logistics_syn-1.json").exists()


class TestRequest:
    @staticmethod
    def respond(monkeypatch, *statuses):
        import requests

        queue = list(statuses)

        def fake(method, url, **kwargs):
            status = queue.pop(0)
            return type("Response", (), {"status_code": status, "ok": status < 400})()

        monkeypatch.setattr(requests, "request", fake)
        monkeypatch.setattr(vexcel.time, "sleep", lambda seconds: None)

    def test_403_is_geofencing(self, monkeypatch):
        self.respond(monkeypatch, 403)
        with pytest.raises(vexcel.VexcelUnavailable, match="geofencing"):
            vexcel._request("GET", "property/extract", "k")

    def test_404_is_missing_only_when_allowed(self, monkeypatch):
        self.respond(monkeypatch, 404)
        assert vexcel._request("GET", "property/extract", "k", missing_ok=True) is None
        self.respond(monkeypatch, 404)
        with pytest.raises(vexcel.VexcelUnavailable):
            vexcel._request("POST", "ortho/extract", "k")

    def test_rate_limit_is_retried(self, monkeypatch):
        self.respond(monkeypatch, 429, 429, 200)
        assert vexcel._request("GET", "x", "k").status_code == 200

    def test_server_error_is_loud(self, monkeypatch):
        self.respond(monkeypatch, 500)
        with pytest.raises(RuntimeError, match="HTTP 500"):
            vexcel._request("GET", "x", "k")
