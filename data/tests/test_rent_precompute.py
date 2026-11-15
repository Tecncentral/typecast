"""Rent precompute behaviours, tested on wholly synthetic kit files and join rows."""

import json
import sys
from datetime import date

import duckdb
import pytest

from data import rent_precompute as rent

AS_OF = date(2026, 11, 15)
ENUMS = {"ServiceType": {"7": "FullService", "13": "TripleNet"}}


def listing(
    pid,
    low,
    high=None,
    basis=2,
    measure=1,
    unit=1,
    status=1,
    service=13,
    others=(),
    fresh="2026-08-01T00:00:00Z",
):
    return {
        "id": f"L{pid}-{low}",
        "propertyId": pid,
        "listingStatus": status,
        "monetaryUnit": unit,
        "certifiedFreshDate": fresh,
        "forLeaseSummary": {
            "askingRateLow": low,
            "askingRateHigh": high,
            "askingRateBasis": basis,
            "askingRateMeasurementType": measure,
            "serviceType": service,
            "properties": [{"id": other} for other in others],
            "spaces": [],
        },
    }


def deal(
    pid,
    signed,
    actual=None,
    amount_type=0,
    basis=2,
    asking=None,
    asking_basis=2,
    unit=1,
):
    body = {
        "signDate": signed,
        "monetaryUnit": unit,
        "serviceType": 7,
        "rateAmountType": amount_type,
    }
    if actual is not None:
        body.update(rateActual=actual, rateBasis=basis)
    if asking is not None:
        body["askingRate"] = {
            "rateLow": asking[0],
            "rateHigh": asking[1],
            "rateBasis": asking_basis,
        }
    return {"propertyId": pid, "leaseDeal": body}


LA, HOU = "Los Angeles", "Houston"
JOIN_ROWS = [
    (1, LA, "Office"),
    (1, LA, "Office"),  # a second scan of the same property
    (2, LA, "Office"),
    (3, LA, "Office"),
    (4, LA, "Office"),
    (5, LA, "Office"),
    (6, LA, "Office"),
    (7, LA, "Office"),
    (8, LA, "Office"),
    (9, LA, "Office"),
    (11, HOU, "Industrial"),
    (12, HOU, "Industrial"),
    (13, HOU, "Industrial"),
    (14, HOU, "Hospitality"),
    (21, LA, "Multifamily"),
    (22, LA, "Multifamily"),
    (23, LA, "Multifamily"),
]
LISTINGS = [
    listing(1, 3.0, 4.0, basis=1),  # monthly midpoint 3.5 x 12 = 42.0
    listing(5, 2.5, basis=1),  # 30.0
    listing(6, 32),
    listing(7, 34),
    listing(8, 38),
    listing(9, 40),
    listing(2, 99, others=(9999,)),  # multi-property: excluded
    listing(4, 99, status=3),  # not active
    listing(4, 99, measure=2),  # per acre
    listing(4, 99, basis=0),  # unknown basis
    listing(4, 99, unit=2),  # not USD
    listing(11, 10),
    listing(12, 12),
    listing(22, 40),  # multifamily: tier A with a caveat
]
DEALS = [
    deal(2, "2025-06-30T00:00:00Z", asking=(28, 32)),  # 30.0, fresh
    deal(3, "2020-01-01T00:00:00Z", actual=2.0, basis=1),  # 24.0, older than 3 years
    deal(3, "2025-01-01T00:00:00Z", actual=5.0, basis=0),  # unknown basis: unusable
    deal(
        3, "2025-02-01T00:00:00Z", actual=900.0, amount_type=1, basis=2
    ),  # not per square foot
]


@pytest.fixture
def kit(tmp_path):
    kit = tmp_path / "kit"
    (kit / "data").mkdir(parents=True)
    (kit / "schemas").mkdir()
    (kit / "schemas/enums.json").write_text(json.dumps(ENUMS))
    for name, rows in (
        ("commercial-listing-summary", LISTINGS),
        ("location-occupancy", DEALS),
    ):
        (kit / "data" / f"{name}.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows)
        )
    join = tmp_path / "join.parquet"
    db = duckdb.connect()
    db.execute("CREATE TABLE j(property_id VARCHAR, city VARCHAR, type VARCHAR)")
    db.executemany(
        "INSERT INTO j VALUES (?,?,?)", [(str(p), c, t) for p, c, t in JOIN_ROWS]
    )
    db.execute("COPY j TO ? (FORMAT PARQUET)", [str(join)])
    return kit, join, tmp_path / "rent"


@pytest.fixture
def built(kit):
    kit_root, join, out = kit
    report = rent.build_rent(kit_root, join, out, AS_OF)
    return report, out


def read(out, pid):
    return json.loads((out / f"{pid}.json").read_text())


def test_one_file_per_joined_property_plus_medians(built):
    report, out = built
    assert report["properties"] == 16, "a property with two scans is one file"
    assert sorted(
        p.stem for p in out.glob("*.json") if p.stem != "market_medians"
    ) == sorted({str(p) for p, _, _ in JOIN_ROWS})
    assert (out / "market_medians.json").is_file()


def test_tier_a_midpoint_monthly_basis_and_date(built):
    _, out = built
    record = read(out, 1)
    assert (record["tier"], record["usd_per_sf_year"], record["source"]) == (
        "A",
        42.0,
        "active lease listing",
    )
    assert record["date"] == "2026-08-01" and record["age_years"] == 0.3
    assert record["comp_count"] == 1 and record["service_type"] == ["TripleNet"]
    assert any("not normalized" in c for c in record["caveats"])
    assert read(out, 5)["usd_per_sf_year"] == 30.0  # single monthly value x 12
    assert read(out, 6)["usd_per_sf_year"] == 32.0  # yearly x 1


def test_multi_property_inactive_and_unknown_basis_listings_never_make_tier_a(built):
    _, out = built
    assert read(out, 2)["tier"] == "B", (
        "a multi-property listing is excluded, so the deal is used"
    )
    assert read(out, 4)["tier"] == "C", (
        "inactive, per-acre, unknown-basis and non-USD listings are all rejected"
    )


def test_tier_b_uses_known_basis_date_and_flags_old_deals(built):
    _, out = built
    fresh, old = read(out, 2), read(out, 3)
    assert (fresh["usd_per_sf_year"], fresh["date"], fresh["stale"]) == (
        30.0,
        "2025-06-30",
        False,
    )
    assert "asking" in fresh["source"]
    assert (old["usd_per_sf_year"], old["date"], old["stale"]) == (
        24.0,
        "2020-01-01",
        True,
    )
    assert old["age_years"] > rent.STALE_YEARS and any(
        "older than 3 years" in c for c in old["caveats"]
    )
    assert old["comp_count"] == 1, (
        "the unknown-basis and per-month-amount deals are not counted"
    )


def test_tier_c_is_the_group_median_and_thin_groups_are_marked(built):
    _, out = built
    office = read(out, 4)
    assert (office["tier"], office["usd_per_sf_year"], office["comp_count"]) == (
        "C",
        36.0,
        6,
    )
    assert not any("Thin" in c for c in office["caveats"])
    thin = read(out, 13)
    assert (thin["tier"], thin["usd_per_sf_year"], thin["comp_count"]) == ("C", 11.0, 2)
    assert any("Thin sample" in c for c in thin["caveats"])


def test_no_group_means_no_reliable_price(built):
    _, out = built
    record = read(out, 14)
    assert (record["tier"], record["usd_per_sf_year"], record["source"]) == (
        "C",
        None,
        "no reliable price",
    )


def test_multifamily_never_borrows_commercial_medians(built):
    _, out = built
    for pid in (21, 23):
        record = read(out, pid)
        assert (record["tier"], record["usd_per_sf_year"], record["source"]) == (
            "C",
            None,
            "no reliable price",
        )
    own = read(out, 22)
    assert (own["tier"], own["usd_per_sf_year"]) == ("A", 40.0)
    assert any("not apartment rent" in c for c in own["caveats"])


def test_market_medians_have_sample_sizes_thin_flags_and_the_service_note(built):
    _, out = built
    medians = json.loads((out / "market_medians.json").read_text())
    groups = {(g["city"], g["type"]): g for g in medians["groups"]}
    office = groups[(LA, "Office")]
    assert (
        office["listings"],
        office["properties"],
        office["median_usd_per_sf_year"],
        office["thin"],
    ) == (6, 6, 36.0, False)
    industrial = groups[(HOU, "Industrial")]
    assert (
        industrial["listings"],
        industrial["median_usd_per_sf_year"],
        industrial["thin"],
    ) == (2, 11.0, True)
    multifamily = groups[(LA, "Multifamily")]
    assert multifamily["usable_for_tier_c"] is False and multifamily["thin"] is True
    assert "not normalized" in medians["service_types"]
    assert medians["service_type_mix"] == {"TripleNet": 9}, (
        "every usable listing is counted once"
    )
    assert medians["thin_below"] == 5


def test_report_is_aggregate_only(built):
    report, _ = built
    assert report["tiers"] == {"A": 9, "B": 2, "C": 5}
    assert report["tier_b_stale"] == 1 and report["tier_c_no_reliable_price"] == 3
    assert "Los Angeles" not in json.dumps(report)


def test_rerun_removes_files_for_properties_no_longer_joined(kit):
    kit_root, join, out = kit
    out.mkdir()
    (out / "55555.json").write_text("{}")
    report = rent.build_rent(kit_root, join, out, AS_OF)
    assert report["removed_stale_files"] == 1 and not (out / "55555.json").exists()


def test_missing_inputs_and_corrupt_kit_fail_without_echoing_source(kit):
    kit_root, join, out = kit
    with pytest.raises(rent.RentBuildError):
        rent.build_rent(kit_root, join.parent / "absent.parquet", out, AS_OF)
    (kit_root / "data/commercial-listing-summary.jsonl").write_text(
        "SECRET-FRAGMENT not json\n"
    )
    with pytest.raises(rent.RentBuildError) as error:
        rent.build_rent(kit_root, join, out, AS_OF)
    assert "SECRET" not in str(error.value)


def test_cli_refuses_output_outside_the_private_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["rent_precompute", "--out", str(tmp_path)])
    with pytest.raises(SystemExit) as stop:
        rent.main()
    assert stop.value.code == 2
