"""Build the private join tables under cache/ from the CoStar kit in cache/costar/.

cache/join.parquet            one row per Los Angeles property, in the Property shape
cache/property_models.parquet every (property_id, model_id) pair; a property can have several scans

Method: shared id. commercial-properties.csv maps PropertyId to MatterportModelId.
Property.model_id is the lowest model id, so it is deterministic.

Run: python data/join.py
"""

import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]
KIT = ROOT / "cache" / "costar"
PROPERTIES = (KIT / "data" / "commercial-property.jsonl").as_posix()
LISTINGS = (KIT / "data" / "commercial-listing-summary.jsonl").as_posix()
MODELS_CSV = (KIT / "commercial-properties.csv").as_posix()

LA_RESEARCH_MARKET = 20
CONSTRUCTION_COMPLETE = 2
ACTIVE_LISTING = 1

PROPERTY_TYPES = {
    1: "Hospitality",
    2: "Industrial",
    3: "Land",
    5: "Office",
    6: "GeneralRetail",
    7: "Flex",
    8: "SportsAndEntertainment",
    9: "MixedUse",
    10: "Specialty",
    11: "Multifamily",
    13: "Healthcare",
    15: "Residential",
    16: "Homes",
}


def build() -> None:
    db = duckdb.connect()
    db.execute(
        f"""
        CREATE TABLE la AS
        SELECT
            CAST(id AS VARCHAR) AS property_id,
            primaryAddress AS addr,
            propertyType AS type_id,
            list_filter(constructionEvents,
                        lambda e: e.eventType = {CONSTRUCTION_COMPLETE}) AS built,
            coalesce(rentableBuildingAreaSquareFeet, grossBuildingAreaSquareFeet) AS size_sqft
        FROM read_json_auto('{PROPERTIES}')
        WHERE primaryAddress.researchMarketId = {LA_RESEARCH_MARKET}
          AND primaryAddress.latitude IS NOT NULL
          AND primaryAddress.longitude IS NOT NULL
        """
    )
    db.execute(
        f"""
        CREATE TABLE models AS
        SELECT CAST(PropertyId AS VARCHAR) AS property_id, MatterportModelId AS model_id
        FROM read_csv_auto('{MODELS_CSV}', all_varchar = true)
        WHERE MatterportModelId IS NOT NULL AND MatterportModelId <> ''
        GROUP BY ALL
        """
    )
    db.execute(
        f"""
        CREATE TABLE listings AS
        SELECT CAST(propertyId AS VARCHAR) AS property_id,
               arg_min(listingContacts[1], id) FILTER (WHERE len(listingContacts) > 0) AS broker
        FROM read_json_auto('{LISTINGS}')
        WHERE listingStatus = {ACTIVE_LISTING}
        GROUP BY propertyId
        """
    )
    names = ", ".join(f"({k}, '{v}')" for k, v in PROPERTY_TYPES.items())
    db.execute(f"CREATE TABLE type_names AS SELECT * FROM (VALUES {names}) t(id, name)")
    db.execute(
        """
        CREATE TABLE joined AS
        SELECT
            la.property_id,
            concat_ws(', ',
                nullif(trim(concat_ws(' ', addr.streetNumber, addr.streetDirection,
                                      addr.streetName, addr.streetType, addr.streetSuffix)), ''),
                addr.city, addr.state, addr.postcode) AS address,
            array_to_string(list_transform(string_split(lower(addr.city), ' '),
                                           lambda w: upper(w[1]) || w[2:]), ' ') AS city,
            CAST(addr.latitude AS DOUBLE) AS lat,
            CAST(addr.longitude AS DOUBLE) AS lon,
            coalesce(t.name, 'Unknown') AS type,
            CAST(built[1].year AS INTEGER) AS year_built,
            listings.property_id IS NOT NULL AS available,
            CAST(size_sqft AS DOUBLE) AS size_sqft,
            nullif(trim(concat_ws(', ',
                nullif(trim(concat_ws(' ', listings.broker.firstName,
                                      listings.broker.lastName)), ''),
                listings.broker.locationName)), '') AS contact,
            (SELECT min(model_id) FROM models m WHERE m.property_id = la.property_id) AS model_id
        FROM la
        LEFT JOIN type_names t ON t.id = la.type_id
        LEFT JOIN listings ON listings.property_id = la.property_id
        ORDER BY la.property_id
        """
    )
    cache = ROOT / "cache"
    cache.mkdir(exist_ok=True)
    db.execute(
        f"COPY joined TO '{(cache / 'join.parquet').as_posix()}' (FORMAT parquet)"
    )
    db.execute(
        f"""COPY (SELECT m.* FROM models m JOIN la USING (property_id) ORDER BY 1, 2)
            TO '{(cache / "property_models.parquet").as_posix()}' (FORMAT parquet)"""
    )
    print_summary(db)


def print_summary(db: duckdb.DuckDBPyConnection) -> None:
    total, scanned, available, both = db.execute(
        """SELECT count(*), count(model_id), sum(available::int),
                  sum((available AND model_id IS NOT NULL)::int) FROM joined"""
    ).fetchone()
    pairs, multi = db.execute(
        """SELECT count(*), count(DISTINCT property_id) FILTER (WHERE n > 1)
           FROM (SELECT property_id, count(*) OVER (PARTITION BY property_id) AS n
                 FROM models WHERE property_id IN (SELECT property_id FROM la))"""
    ).fetchone()
    print(
        f"LA properties {total}; with a scan {scanned}; available {available}; both {both}"
    )
    print(f"scan pairs {pairs}; properties with more than one scan {multi}")
    print(
        "method: shared id (commercial-properties.csv PropertyId -> MatterportModelId)"
    )
    for row in db.execute(
        """SELECT type, count(*), count(model_id), sum(available::int),
                  sum((available AND model_id IS NOT NULL)::int)
           FROM joined GROUP BY type ORDER BY 2 DESC"""
    ).fetchall():
        kind, props, scan, avail, both = row
        print(
            f"  {kind:<14} props {props:4d}  scan {scan:4d}  available {avail:3d}  both {both:3d}"
        )


if __name__ == "__main__":
    build()
