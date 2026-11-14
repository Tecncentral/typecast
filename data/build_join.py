"""Build private cache/join.parquet; stdout contains aggregate diagnostics only."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import tempfile
from typing import Any

from contracts.schemas import Property

ROOT = Path(__file__).resolve().parents[1]
KIT_ROOT = ROOT / "cache/costar-hackathon-kit"
JOIN_PATH = ROOT / "cache/join.parquet"
DATASETS = ("apartment-listing", "commercial-listing-summary", "commercial-property",
            "commercial-sale-comp", "company-detail", "location-occupancy",
            "residential-listing-features", "residential-listings")
CITIES = {"los angeles": "Los Angeles", "houston": "Houston"}


class JoinBuildError(RuntimeError):
    """A sanitized failure that cannot contain source records."""


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _positive(value: Any) -> bool:
    result = _number(value)
    return result is not None and result > 0


def _key(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


def _timing_known(space: dict, enums: dict) -> bool:
    # Future dates describe marketed space, not immediate occupancy/permission.
    value = space.get("availableOnDate")
    if isinstance(value, str):
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            pass
    return enums["AvailabilityType"].get(str(space.get("availabilityType"))) in {
        "ThirtyDays", "SixtyDays", "NinetyDays", "OneHundredTwentyDays"}


def _listing_properties(listing: dict) -> set[str]:
    lease = listing.get("forLeaseSummary") or {}
    ids = {_key(listing.get("propertyId"))}
    ids.update(_key(p.get("id")) for p in lease.get("properties", []))
    for field in ("spaces", "lands"):
        ids.update(_key(p.get("propertyId")) for p in lease.get(field, []))
    return ids - {None}


def _lease_availability(listing: dict, property_id: str, enums: dict) -> tuple[str, str]:
    lease = listing.get("forLeaseSummary") or {}
    members = _listing_properties(listing)
    # Never assign an entire shopping-center rollup to every member building.
    rollups = [p.get("totalAvailableSquareFeet") for p in lease.get("properties", [])
               if _key(p.get("id")) == property_id]
    if _key(listing.get("propertyId")) == property_id and members == {property_id}:
        rollups.append(lease.get("totalAvailableSquareFeet"))
    spaces = [s for s in lease.get("spaces", []) if _key(s.get("propertyId")) == property_id
              or (s.get("propertyId") is None and members == {property_id})]
    ready = [s for s in spaces if _positive(s.get("squareFeetMax"))
             and s.get("isLeasePending") is False and not s.get("dateOffMarket")
             and s.get("isInventoryOffMarket") is not True and _timing_known(s, enums)]
    if any(_positive(area) for area in rollups) and ready:
        return "available", (
            "Active lease listing: positive property-attributable totalAvailableSquareFeet "
            "and squareFeetMax, nonpending space, no supplied off-market flag, and known "
            "availableOnDate or 30/60/90/120-day notice. Marketed availability may be "
            "future-dated; occupancy and filming permission are unverified.")
    if rollups and all(_number(area) == 0 for area in rollups):
        return "not_available", "Active lease listing reports zero property-attributable available square feet."
    return "unknown", ("Active listing does not verify property-attributable positive space, "
                       "nonpending status and a known availability date/notice together.")


def availability(property_id: str, listings: list[dict], enums: dict) -> tuple[str, str]:
    """Conservative marketed availability; vacancy/occupancy are not substitutes."""
    if not listings:
        return "unknown", "No linked commercial listing in the supplied snapshot; occupancy is unknown."
    states = []
    for listing in listings:
        status = enums["ListingStatus"].get(str(listing.get("listingStatus")), "Unknown")
        if status == "Unknown":
            states.append(("unknown", "Linked listing status is unknown."))
        elif status != "Active":
            states.append(("not_available", "Linked listing is not Active in the supplied snapshot; this does not establish occupancy."))
        elif listing.get("forLeaseSummary") is not None:
            states.append(_lease_availability(listing, property_id, enums))
        else:
            states.append(("unknown", "Active sale/auction listing does not verify usable lease-space availability."))
    for wanted in ("available", "unknown", "not_available"):
        for state, reason in states:
            if state == wanted:
                return state, reason
    raise AssertionError("Listing states must not be empty")


def active_listing_types(listings: list[dict], enums: dict) -> list[str]:
    """Active marketing categories, independent of verified lease availability."""
    categories = {"lease": {"PropertyDirectSpaceForLease", "BuildingParkDirectSpaceLease",
                            "ShoppingCenterDirectSpaceForLease", "LandDirectForLease",
                            "CommercialSublease", "CommercialLeaseAssignment", "PropertyCoworking",
                            "DisconnectedSpaceForLease"},
                  "sale": {"PropertyForSale", "ResidentialPropertyForSale", "CondoForSale",
                           "LandForSale", "CommercialPortfolioForSale", "ConsolidatedCondoForSaleListing",
                           "DisconnectedForSale", "DisconnectedCondoForSale"},
                  "auction": {"PropertyForAuction", "LandForAuction", "CondoForAuction",
                              "LoanForAuction", "CommercialPortfolioForAuction"}}
    labels = {enums.get("ListingType", {}).get(str(listing.get("listingType")))
              for listing in listings
              if enums["ListingStatus"].get(str(listing.get("listingStatus"))) == "Active"}
    return sorted(category for category, members in categories.items() if labels & members)


def _role_labels(record: dict, listings: list[dict], enums: dict) -> str | None:
    # Only enum labels enter this field. Never forward contact names or free text.
    contacts = list(record.get("contacts") or [])
    for listing in listings:
        contacts.extend(listing.get("listingContacts") or [])
        contacts.extend(listing.get("propertyContacts") or [])
    roles = {enums["ContactRole"].get(str(c.get("contactRole"))) for c in contacts}
    return "; ".join(sorted(roles - {None, "Unknown"})) or None


def _normalize(record: dict, listings: list[dict], enums: dict) -> dict | None:
    address = record.get("primaryAddress") or {}
    city = CITIES.get(str(address.get("city") or "").strip().casefold())
    lat, lon = _number(address.get("latitude")), _number(address.get("longitude"))
    if city is None or lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    property_id = _key(record.get("id"))
    if property_id is None:
        raise JoinBuildError("Commercial property record has no id.")
    years = {_number(e.get("year")) for e in record.get("constructionEvents", [])
             if enums["ConstructionEventType"].get(str(e.get("eventType"))) == "ConstructionComplete"}
    years = {int(y) for y in years if y is not None and y.is_integer() and 1 <= y <= 9999}
    year = next(iter(years)) if len(years) == 1 else None
    size = _number(record.get("grossBuildingAreaSquareFeet"))
    size = size if size is not None and size > 0 else None
    state, reason = availability(property_id, listings, enums)
    profile = ((record.get("propertyApartment") or {}).get("residentialProfile") or {})
    flags = {key: profile[key] for key in ("hasNoParkingAvailable", "hasVisitorParkingAvailable")
             if type(profile.get(key)) is bool}
    parts = (address.get(k) for k in ("streetNumber", "streetDirection", "streetName", "streetType", "streetSuffix"))
    street = " ".join(str(p).strip() for p in parts if p is not None and str(p).strip())
    if not street:
        return None
    row = {"property_id": property_id, "address": street, "city": city, "lat": lat, "lon": lon,
           "type": enums["PropertyType"].get(str(record.get("propertyType")), "Unknown"),
           "year_built": year, "size_sqft": size, "available": state == "available",
           "contact": _role_labels(record, listings, enums), "availability_status": state,
           "availability_reason": reason, "parking_flags": flags,
           "listing_types": active_listing_types(listings, enums),
           "size_source": "grossBuildingAreaSquareFeet",
           "year_source": "constructionEvents[eventType=ConstructionComplete].year",
           "year_status": "reported" if year is not None else "unknown_or_ambiguous",
           "join_method": "sponsor_csv_property_id_and_model_id"}
    try:
        Property(**row)
    except Exception:
        raise JoinBuildError("A normalized property does not satisfy the shared contract.") from None
    return row


def _dependencies():
    try:
        import duckdb
        import pyarrow as pa
        return duckdb, pa
    except ImportError:
        raise JoinBuildError("Install the agreed duckdb and pyarrow dependencies before building the join.") from None


def _records(connection, name: str):
    cursor = connection.execute(f'SELECT json FROM "raw_{name.replace("-", "_")}"')
    while batch := cursor.fetchmany(256):
        for (raw,) in batch:
            yield json.loads(raw)


def build_join(kit_root: Path = KIT_ROOT, output: Path = JOIN_PATH) -> dict:
    """Import all datasets in memory, join exact IDs and publish atomically."""
    duckdb, pa = _dependencies()
    kit_root, output = Path(kit_root), Path(output)
    expected = [kit_root / "commercial-properties.csv", kit_root / "residential-listings.csv",
                kit_root / "schemas/enums.json"]
    expected.extend(kit_root / "data" / f"{name}.jsonl" for name in DATASETS)
    if any(not p.is_file() for p in expected):
        raise JoinBuildError("Sponsor kit is incomplete; mapping CSV, enums and all eight JSONL datasets are required.")
    enums = json.loads((kit_root / "schemas/enums.json").read_text())
    for name in ("PropertyType", "ListingStatus", "AvailabilityType", "ConstructionEventType", "ContactRole"):
        if not isinstance(enums.get(name), dict):
            raise JoinBuildError("Sponsor enum definitions are incomplete.")
    connection = duckdb.connect(":memory:")
    temporary = None
    try:
        counts = {}
        for name in DATASETS:
            path = str(kit_root / "data" / f"{name}.jsonl").replace("'", "''")
            table = "raw_" + name.replace("-", "_")
            connection.execute(f'CREATE VIEW "{table}" AS SELECT json FROM read_json_objects(\'{path}\', format=\'newline_delimited\')')
            counts[f"data/{name}.jsonl"] = connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        by_property = defaultdict(list)
        for listing in _records(connection, "commercial-listing-summary"):
            for property_id in _listing_properties(listing):
                by_property[property_id].append(listing)
        rows, seen, excluded, size_conflicts = [], set(), 0, 0
        for record in _records(connection, "commercial-property"):
            property_id = _key(record.get("id"))
            if property_id in seen:
                raise JoinBuildError("Duplicate commercial property ids; join publication refused.")
            seen.add(property_id)
            row = _normalize(record, by_property[property_id], enums)
            if row is None:
                excluded += 1
            else:
                rows.append(row)
            gba, rba = _number(record.get("grossBuildingAreaSquareFeet")), _number(record.get("rentableBuildingAreaSquareFeet"))
            size_conflicts += int(gba is not None and rba is not None and rba > gba)
        schema = pa.schema([
            ("property_id", pa.string()), ("address", pa.string()), ("city", pa.string()),
            ("lat", pa.float64()), ("lon", pa.float64()), ("type", pa.string()),
            ("year_built", pa.int32()), ("size_sqft", pa.float64()), ("available", pa.bool_()),
            ("contact", pa.string()), ("availability_status", pa.string()),
            ("availability_reason", pa.string()), ("parking_flags", pa.map_(pa.string(), pa.bool_())),
            ("listing_types", pa.list_(pa.string())),
            ("size_source", pa.string()), ("year_source", pa.string()),
            ("year_status", pa.string()), ("join_method", pa.string())])
        connection.register("normalized_properties", pa.Table.from_pylist(rows, schema=schema))
        connection.execute("CREATE TABLE mapping AS SELECT trim(PropertyId) AS property_id, "
                           "nullif(trim(MatterportModelId), '') AS model_id FROM read_csv(?, header=true, all_varchar=true)",
                           [str(kit_root / "commercial-properties.csv")])
        counts["commercial-properties.csv"] = connection.execute("SELECT count(*) FROM mapping").fetchone()[0]
        counts["residential-listings.csv"] = connection.execute(
            "SELECT count(*) FROM read_csv(?, header=true, all_varchar=true)",
            [str(kit_root / "residential-listings.csv")]).fetchone()[0]
        connection.execute("CREATE VIEW shared_models AS SELECT model_id FROM mapping WHERE model_id IS NOT NULL "
                           "GROUP BY model_id HAVING count(DISTINCT property_id) > 1")
        # The sponsor defines the pair as the key. Shared models remain valid for
        # each explicitly supplied property; they are not nearest-address guesses.
        connection.execute("CREATE TABLE joined AS SELECT DISTINCT p.*, m.model_id "
                           "FROM normalized_properties p JOIN mapping m USING(property_id) "
                           "WHERE m.model_id IS NOT NULL")
        if not connection.execute("SELECT count(*) FROM joined").fetchone()[0]:
            raise JoinBuildError("No unambiguous property/model pairs could be built.")
        report = {"files": counts, "properties": len(rows), "excluded_missing_geography_or_address": excluded,
                  "rba_above_gba": size_conflicts}
        for label, query in {
            "mapping_properties_without_model": "SELECT count(DISTINCT property_id) FROM mapping WHERE model_id IS NULL",
            "unmatched_mapping_properties": "SELECT count(DISTINCT m.property_id) FROM mapping m LEFT JOIN normalized_properties p USING(property_id) WHERE p.property_id IS NULL",
            "model_ids_shared_by_properties": "SELECT count(*) FROM shared_models",
            "joined_pairs": "SELECT count(*) FROM joined",
            "joined_properties": "SELECT count(DISTINCT property_id) FROM joined",
            "unknown_year_properties": "SELECT count(DISTINCT property_id) FROM joined WHERE year_built IS NULL",
            "unknown_size_properties": "SELECT count(DISTINCT property_id) FROM joined WHERE size_sqft IS NULL",
        }.items():
            report[label] = connection.execute(query).fetchone()[0]
        report["by_city_and_type"] = [dict(zip(("city", "type", "properties", "properties_with_scans", "available", "unknown_availability"), group))
            for group in connection.execute("SELECT p.city,p.type,count(DISTINCT p.property_id),count(DISTINCT j.property_id),"
                "count(DISTINCT CASE WHEN j.available THEN j.property_id END),"
                "count(DISTINCT CASE WHEN j.availability_status='unknown' THEN j.property_id END) "
                "FROM normalized_properties p LEFT JOIN joined j USING(property_id) GROUP BY p.city,p.type ORDER BY p.city,p.type").fetchall()]
        report["availability"] = dict(connection.execute("SELECT availability_status,count(DISTINCT property_id) FROM joined GROUP BY availability_status").fetchall())
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".join-", suffix=".parquet", delete=False) as handle:
            temporary = Path(handle.name)
        connection.execute("COPY (SELECT * FROM joined ORDER BY property_id,model_id) TO ? (FORMAT PARQUET)", [str(temporary)])
        temporary.replace(output)
        return report
    except JoinBuildError:
        raise
    except Exception:
        # Database/parser errors can include source fragments, so suppress them.
        raise JoinBuildError("CoStar join build failed; verify the private kit schema and local dependencies.") from None
    finally:
        connection.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def cross_check_index(index_root: Path, join_path: Path = JOIN_PATH) -> dict:
    """Count property-ID and model-pair overlap without disclosing identifiers."""
    duckdb, _ = _dependencies()
    index_root = Path(index_root)
    if (index_root / "CURRENT").is_file():
        selected = (index_root / (index_root / "CURRENT").read_text().strip()).resolve()
        if not selected.is_relative_to(index_root.resolve()):
            raise JoinBuildError("Index generation escapes its cache directory.")
        index_root = selected
    shots_path = index_root / "shots.json"
    if not shots_path.is_file():
        return {"status": "blocked", "reason": "Lane A shots.json is not present in the selected index generation."}
    try:
        shots = json.loads(shots_path.read_text())
        pairs = {(_key(s.get("property_id")), _key(s.get("model_id"))) for s in shots}
        ids = {p for p, _ in pairs}
        with duckdb.connect(":memory:") as connection:
            joined = set(connection.execute("SELECT property_id,model_id FROM read_parquet(?)", [str(join_path)]).fetchall())
        joined_ids = {p for p, _ in joined}
        return {"status": "checked", "index_shots": len(shots), "index_properties": len(ids),
                "index_property_model_pairs": len(pairs), "overlapping_properties": len(ids & joined_ids),
                "overlapping_pairs": len(pairs & joined), "unmatched_properties": len(ids - joined_ids),
                "unmatched_pairs": len(pairs - joined), "identifier_namespace": "commercial PropertyId (not residential ListingId)"}
    except Exception:
        raise JoinBuildError("Unable to cross-check the private index; verify its manifest and join schema.") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=KIT_ROOT)
    parser.add_argument("--output", type=Path, default=JOIN_PATH)
    parser.add_argument("--index", type=Path, default=ROOT / "cache/shot-index")
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((ROOT / "cache").resolve()):
        parser.error("Join output must be inside the private cache directory.")
    try:
        report = build_join(args.kit, args.output)
        report["index_overlap"] = cross_check_index(args.index, args.output)
        report["built_at_utc"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except JoinBuildError as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
