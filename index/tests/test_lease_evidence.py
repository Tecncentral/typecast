"""Lease evidence endpoint: cache-only, never estimated, never a filming price."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from contracts.schemas import Property
from data import cost_model
from index import production


def _property(pid: str, size):
    return Property(property_id=pid, address="1 Test St", city="Los Angeles", lat=34.0, lon=-118.2,
                    type="Office", size_sqft=size, availability_status="unknown")


@pytest.fixture
def lease(tmp_path, monkeypatch):
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", False)
    monkeypatch.setattr(cost_model, "RENT_DIR", tmp_path)
    sizes = {"p1": 2000.0, "p_nosize": None, "p_none": 5000.0, "p_bad": 1000.0, "p_noprice": 900.0}
    monkeypatch.setattr(production, "get_property", lambda pid: _property(pid, sizes[pid]))

    def write(pid, **fields):
        record = {"property_id": pid, "tier": "A", "usd_per_sf_year": 36.5, "source": "active lease listing",
                  "date": "2026-10-01", "caveats": ["Service types are mixed."], **fields}
        (tmp_path / f"{pid}.json").write_text(json.dumps(record), encoding="utf-8")

    write("p1")
    write("p_nosize")
    write("p_noprice", usd_per_sf_year=None, tier="C", source="no reliable price")
    (tmp_path / "p_bad.json").write_text("{not json", encoding="utf-8")
    app = FastAPI()
    app.include_router(production.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_cached_lease_rate_is_prorated_from_real_size_and_labelled_a_floor(lease):
    body = lease.get("/api/production/lease/p1").json()
    assert body["status"] == "kit" and body["tier"] == "A"
    assert body["usd_per_sf_year"] == 36.5 and body["size_sqft"] == 2000.0
    assert body["daily_floor_usd"] == 200.0          # 2000 x 36.5 / 365
    assert "not a filming fee" in body["note"]
    assert body["caveats"] == ["Service types are mixed."]


def test_missing_cache_is_unknown_and_never_estimated(lease):
    body = lease.get("/api/production/lease/p_none").json()
    assert body["status"] == "unknown" and body["usd_per_sf_year"] is None
    assert body["daily_floor_usd"] is None and "rent_precompute" in body["reason"]


def test_unknown_size_or_price_gives_no_daily_figure(lease):
    nosize = lease.get("/api/production/lease/p_nosize").json()
    assert nosize["status"] == "kit" and nosize["daily_floor_usd"] is None and "size" in nosize["reason"]
    noprice = lease.get("/api/production/lease/p_noprice").json()
    assert noprice["status"] == "unknown" and noprice["daily_floor_usd"] is None


def test_corrupt_cache_is_sanitized_not_a_500(lease):
    response = lease.get("/api/production/lease/p_bad")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unknown" and "not json" not in json.dumps(body)


def test_mock_mode_and_bad_ids_never_read_the_cache(lease, monkeypatch):
    assert lease.get("/api/production/lease/..%2Fsecret").status_code in (404, 422)
    assert lease.get("/api/production/lease/bad id").status_code == 422
    monkeypatch.setattr(production.costar_tools, "USE_MOCKS", True)
    body = lease.get("/api/production/lease/p1").json()
    assert body["status"] == "unknown" and "Mock" in body["reason"]
