"""Private-data behaviors tested with wholly synthetic property records."""
import csv
import json

import pytest

pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")

from data import build_join as builder, costar_tools as costar

ENUMS = {
    "PropertyType": {"0": "Unknown", "2": "Industrial", "5": "Office", "6": "GeneralRetail"},
    "ListingStatus": {"0": "Unknown", "1": "Active", "3": "OffMarket"},
    "AvailabilityType": {"0": "Unknown", "1": "ThirtyDays", "5": "ToBeDetermined", "7": "Negotiable"},
    "ConstructionEventType": {"2": "ConstructionComplete", "4": "RenovationFinished"},
    "ContactRole": {"0": "Unknown", "4": "PropertyManager", "11": "ListingBroker"},
    "ListingType": {"0": "Unknown", "9": "PropertyForSale", "14": "PropertyDirectSpaceForLease", "22": "PropertyForAuction"},
}


def property_record(pid, city="Los Angeles", year=1984, size=10000, kind=5):
    return {"id": pid, "propertyType": kind, "grossBuildingAreaSquareFeet": size,
            "primaryAddress": {"city": city, "streetNumber": "123", "streetName": "Synthetic",
                               "streetType": "St", "latitude": 34, "longitude": -118},
            "constructionEvents": [] if year is None else [{"eventType": 2, "year": year}],
            "contacts": [{"contactRole": 4, "name": "PERSONAL VALUE MUST NOT LEAK",
                          "email": "private@example.invalid", "phone": "555-000-1234"}],
            "propertyApartment": {"residentialProfile": {"hasNoParkingAvailable": False,
                                                          "hasVisitorParkingAvailable": None}}}


def listing(pid=1, status=1, **space_changes):
    space = {"propertyId": pid, "squareFeetMax": 1000, "isLeasePending": False,
             "availabilityType": 0, "availableOnDate": "2027-01-01T00:00:00Z"}
    space.update(space_changes)
    return {"propertyId": pid, "listingStatus": status, "listingType": 14,
            "listingContacts": [{"contactRole": 11, "name": "ANOTHER PRIVATE PERSON"}],
            "forLeaseSummary": {"totalAvailableSquareFeet": 1000, "spaces": [space], "properties": []}}


@pytest.fixture
def private_join(tmp_path, monkeypatch):
    kit = tmp_path / "kit"
    (kit / "data").mkdir(parents=True)
    (kit / "schemas").mkdir()
    (kit / "schemas/enums.json").write_text(json.dumps(ENUMS))
    properties = [property_record(1), property_record(2, year=None, size=None),
                  property_record(3, city="houston", year=1990, kind=2), property_record(4, year=1988),
                  property_record(5, year=1980, kind=6), property_record(6)]
    properties[4]["constructionEvents"].append({"eventType": 2, "year": 1990})
    properties[5]["primaryAddress"]["latitude"] = None
    datasets = {"commercial-property": properties,
                "commercial-listing-summary": [listing(), listing(3, availabilityType=5, availableOnDate=None), listing(4, status=3)]}
    for name in builder.DATASETS:
        (kit / "data" / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in datasets.get(name, [])))
    with (kit / "commercial-properties.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["PropertyId", "MatterportModelId", "Address", "City", "State"])
        writer.writerows((pid, model, "Synthetic St", "Los Angeles", "CA")
                         for pid, model in [(1, "model-b"), (1, "model-a"), (1, "model-a"), (2, "model-2"),
                                            (3, "model-3"), (4, "shared-model"), (5, "shared-model"), (6, "missing-geo")])
    (kit / "residential-listings.csv").write_text("ListingId,MatterportModelId\n")
    output = tmp_path / "join.parquet"
    report = builder.build_join(kit, output)
    monkeypatch.setattr(costar, "JOIN_PATH", output)
    monkeypatch.setattr(costar, "INDEX_ROOT", tmp_path / "unprovisioned-index")
    monkeypatch.setattr(costar, "USE_MOCKS", False)
    return kit, output, report


def test_exact_pair_join_and_no_personal_contacts(private_join):
    _, path, report = private_join
    assert report["joined_pairs"] == 6  # duplicate pair is removed; shared pair is retained.
    assert report["joined_properties"] == 5
    assert report["model_ids_shared_by_properties"] == 1
    assert report["excluded_missing_geography_or_address"] == 1
    prop = costar.get_property("1")
    assert prop.model_id == "model-a"  # stable representative; all pairs remain in parquet.
    assert prop.contact == "ListingBroker; PropertyManager"
    assert prop.parking_flags == {"hasNoParkingAvailable": False}
    assert prop.availability_status == "available" and prop.available
    assert prop.listing_types == ["lease"]
    assert "future-dated" in prop.availability_reason
    assert costar.get_property("3").type == "Industrial"
    import duckdb
    with duckdb.connect() as connection:
        exported = str(connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchall())
    for secret in ("PERSONAL VALUE", "private@example.invalid", "555-000-1234", "ANOTHER PRIVATE PERSON"):
        assert secret not in exported


def test_unknown_values_do_not_pass_hard_filters(private_join):
    assert len(costar.search_costar(available_only=False)) == 4  # unique LA properties, not scan count.
    assert {p.property_id for p in costar.search_costar()} == {"1"}
    assert {p.property_id for p in costar.search_costar(available_only=False, year_min=1980, year_max=1989)} == {"1", "4"}
    assert {p.property_id for p in costar.search_costar(available_only=False, min_sqft=9000)} == {"1", "4", "5"}
    assert costar.get_property("2").year_built is None
    assert costar.get_property("5").year_built is None  # conflicting construction-complete years.
    assert costar.get_property("2").availability_status == "unknown"
    assert costar.get_property("4").availability_status == "not_available"
    assert costar.search_costar(city="HOUSTON", available_only=False)[0].city == "Houston"
    assert costar.search_costar(city="Houston") == []
    assert costar.search_costar(types=["Office' OR TRUE --"], available_only=False) == []
    assert costar.search_costar(limit=0) == []
    with pytest.raises(ValueError):
        costar.search_costar(limit=-1)
    with pytest.raises(KeyError):
        costar.get_property("absent")


@pytest.mark.parametrize("changes", [
    {"availableOnDate": None}, {"availableOnDate": "invalid"},
    {"availableOnDate": None, "availabilityType": 5},
    {"availableOnDate": None, "availabilityType": 7},
    {"isLeasePending": True}, {"isLeasePending": None},
    {"dateOffMarket": "2026-01-01"}, {"isInventoryOffMarket": True},
    {"squareFeetMax": None}, {"squareFeetMax": 0},
])
def test_uncertain_pending_or_offmarket_space_is_not_available(changes):
    state, _ = builder.availability("1", [listing(**changes)], ENUMS)
    assert state != "available"


def test_notice_and_rollups_are_property_specific():
    assert builder.availability("1", [listing(availableOnDate=None, availabilityType=1)], ENUMS)[0] == "available"
    group = listing()
    group["forLeaseSummary"]["spaces"].append(listing(2)["forLeaseSummary"]["spaces"][0])
    assert builder.availability("1", [group], ENUMS)[0] == "unknown"
    group["forLeaseSummary"]["properties"] = [{"id": 1, "totalAvailableSquareFeet": 1000}]
    assert builder.availability("1", [group], ENUMS)[0] == "available"
    assert builder.availability("2", [group], ENUMS)[0] == "unknown"
    zero = listing()
    zero["forLeaseSummary"]["totalAvailableSquareFeet"] = 0
    assert builder.availability("1", [zero], ENUMS)[0] == "not_available"
    sale = {"propertyId": 1, "listingStatus": 1, "forSaleSummary": {"totalAvailableSquareFeet": 1000}}
    assert builder.availability("1", [sale], ENUMS)[0] == "unknown"


def test_atomic_build_failure_preserves_previous_join(private_join):
    kit, output, _ = private_join
    before = output.read_bytes()
    source = kit / "data/commercial-property.jsonl"
    source.write_text(source.read_text() + json.dumps(property_record(1)) + "\n")
    with pytest.raises(builder.JoinBuildError, match="Duplicate"):
        builder.build_join(kit, output)
    assert output.read_bytes() == before


def test_bad_source_error_does_not_echo_source(private_join):
    kit, output, _ = private_join
    (kit / "data/commercial-property.jsonl").write_text('{"private": "PRIVATE STRING", bad json}\n')
    with pytest.raises(builder.JoinBuildError) as caught:
        builder.build_join(kit, output)
    assert "PRIVATE STRING" not in str(caught.value)


def test_index_generation_overlap(private_join, tmp_path):
    _, output, _ = private_join
    index = tmp_path / "index"
    generation = index / ("a" * 32)
    generation.mkdir(parents=True)
    (index / "CURRENT").write_text(generation.name)
    (generation / "shots.json").write_text(json.dumps([
        {"property_id": "1", "model_id": "model-b"}, {"property_id": "1", "model_id": "model-b"},
        {"property_id": "missing", "model_id": "not-in-kit"}]))
    report = builder.cross_check_index(index, output)
    assert report["index_shots"] == 3
    assert report["overlapping_properties"] == report["overlapping_pairs"] == 1
    assert report["unmatched_properties"] == report["unmatched_pairs"] == 1
    assert "model-b" not in json.dumps(report)
    (index / "CURRENT").write_text("../outside")
    with pytest.raises(builder.JoinBuildError, match="escapes"):
        builder.cross_check_index(index, output)


def test_missing_join_never_uses_fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(costar, "JOIN_PATH", tmp_path / "missing.parquet")
    monkeypatch.setattr(costar, "USE_MOCKS", False)
    with pytest.raises(RuntimeError, match="missing"):
        costar.search_costar()


def test_indexed_properties_are_prioritized_before_limit_and_after_filters(private_join, tmp_path, monkeypatch):
    root = tmp_path / "index-priority"
    root.mkdir()
    (root / "shots.json").write_text(json.dumps([{"property_id": "5", "model_id": "shared-model"}]))
    monkeypatch.setattr(costar, "INDEX_ROOT", root)
    assert costar.indexed_property_ids() == {"5"}
    assert costar.search_costar(available_only=False, limit=1)[0].property_id == "5"
    assert costar.search_costar(available_only=True, limit=1)[0].property_id == "1"
    assert len(costar.search_costar(available_only=False)) == 4
    (root / "shots.json").write_text("malformed private metadata")
    with pytest.raises(RuntimeError, match="metadata is invalid"):
        costar.search_costar()


@pytest.mark.parametrize("label,bounds", [("1980s", (1980, 1989)), ("1990's", (1990, 1999)),
                                         ("2000s", (2000, 2009)), ("1984", (1984, 1984)),
                                         ("1978–1992", (1978, 1992))])
def test_era_ranges(label, bounds):
    assert costar.era_year_range(label) == bounds


@pytest.mark.parametrize("label", ["80s", "1984s", "1999-1980", "unknown"])
def test_ambiguous_eras_are_rejected(label):
    with pytest.raises(ValueError):
        costar.era_year_range(label)


def test_active_listing_categories_do_not_infer_lease_availability():
    sale = {"propertyId": 1, "listingStatus": 1, "listingType": 9, "forSaleSummary": {}}
    auction = {"propertyId": 1, "listingStatus": 1, "listingType": 22, "auctionForSaleSummary": {}}
    unknown = {"propertyId": 1, "listingStatus": 1, "listingType": 0}
    assert builder.active_listing_types([sale, auction, sale, unknown, listing()], ENUMS) == ["auction", "lease", "sale"]
    assert builder.availability("1", [sale, auction], ENUMS)[0] == "unknown"
    assert builder.active_listing_types([{**sale, "listingStatus": 3}, unknown], ENUMS) == []
    assert builder.active_listing_types([sale], {k: v for k, v in ENUMS.items() if k != "ListingType"}) == []


def test_older_join_without_listing_types_is_compatible(private_join):
    import duckdb
    _, path, _ = private_join
    older = path.with_name("older.parquet")
    with duckdb.connect() as connection:
        connection.execute("COPY (SELECT * EXCLUDE(listing_types) FROM read_parquet(?)) TO ? (FORMAT PARQUET)", [str(path), str(older)])
    older.replace(path)
    prop = costar.get_property("1")
    assert prop.available and prop.listing_types == []


def test_join_built_before_availability_evidence_reads_as_unknown(private_join):
    import duckdb
    _, path, _ = private_join
    older = path.with_name("oldest.parquet")
    with duckdb.connect() as connection:
        connection.execute(
            "COPY (SELECT * EXCLUDE(listing_types, availability_status, availability_reason, parking_flags) "
            "FROM read_parquet(?)) TO ? (FORMAT PARQUET)", [str(path), str(older)])
    older.replace(path)
    prop = costar.get_property("1")
    # The old boolean is not promoted to verified availability.
    assert prop.available is False and prop.availability_status == "unknown"
    assert "rebuild" in prop.availability_reason
    assert prop.parking_flags == {} and prop.listing_types == []
    assert isinstance(prop.lat, float) and isinstance(prop.lon, float)
