# Private CoStar schema and exact-ID join

Verified against the supplied kit on 2026-11-14. Schema and aggregate counts only;
source records, contacts and the derived join stay in ignored `cache/`. Do not
publish that directory or send it to a model. Kit docs are reference material.

## Inputs

All eight JSONL datasets are read through DuckDB in memory. Unneeded fields are
not copied into the join. Residential ListingIds are a separate namespace.

| Private file under `cache/costar-hackathon-kit/` | Records | Keys / purpose |
| --- | ---: | --- |
| `commercial-properties.csv` | 13,147 | `PropertyId`, `MatterportModelId`; supplied pair mapping, including 51 blank-model rows |
| `residential-listings.csv` | 2,224 | `ListingId`, `ResidentialListingId`, `MatterportModelId`; counted, not joined |
| `data/commercial-property.jsonl` | 3,339 | `id`; physical property facts |
| `data/commercial-listing-summary.jsonl` | 1,022 | `id`, `propertyId`, `forLeaseSummary.properties[].id`, `forLeaseSummary.spaces[].propertyId`; marketed space |
| `data/location-occupancy.jsonl` | 74,093 | `id`, `propertyId`, `tenantLocationId`; tenancies, not availability |
| `data/company-detail.jsonl` | 49,575 | `id` = occupancy `tenantLocationId`; counted, not copied |
| `data/commercial-sale-comp.jsonl` | 6,120 | `id`, `entities[].propertyId`; completed sales |
| `data/apartment-listing.jsonl` | 1,747 | `id`, `propertyId`; apartment rental marketing, not commercial lease-space proof |
| `data/residential-listings.jsonl` | 2,120 | `id` = MLS ListingId; counted, not joined |
| `data/residential-listing-features.jsonl` | 1,899 | `id` = MLS ListingId; counted, not joined |
| `schemas/enums.json` | lookup definitions | Decode `PropertyType`, `ConstructionEventType`, `ListingStatus`, `AvailabilityType`, `ContactRole` |

## Exact fields and semantics

Meanings come from kit `index.md`, `models/commercial-property.md`,
`models/commercial-listing-summary.md`, `models/location-occupancy.md` and
`concepts/data-quality-and-confidence.md`.

| Output | Input | Treatment |
| --- | --- | --- |
| `property_id` | CSV `PropertyId` = commercial property `id` | Stable commercial asset key, string at API boundary |
| `model_id` | CSV `MatterportModelId` for the same `PropertyId` | Supplied association; no address/nearest-coordinate inference |
| `address` | `primaryAddress.streetNumber`, `streetDirection`, `streetName`, `streetType`, `streetSuffix` | Assemble primary street address; missing address excludes row |
| `city` | `primaryAddress.city` | Los Angeles / Houston, normalizing case only; research market is not substituted for city |
| `lat`, `lon` | `primaryAddress.latitude`, `longitude` | Primary address geocode; missing/nonfinite/invalid excludes row, never becomes zero |
| `type` | `propertyType` via `PropertyType` enum | Exact declared label, including `GeneralRetail`, `Multifamily` |
| `year_built` | `constructionEvents[].year`, `eventType=2` (`ConstructionComplete`) | May be approximate in source research. Missing/conflicting completion years stay null; renovations do not replace completion |
| `size_sqft` | `grossBuildingAreaSquareFeet` | Whole exterior building envelope (GBA), not rentable area or room area. Missing/nonpositive is null; no mixed-measure fallback |
| `available`, `availability_status`, `availability_reason` | Rules below | Marketed lease-space availability with reason; no claim of vacancy or filming permission |
| `contact` | `contacts[].contactRole`, `listingContacts[].contactRole`, `propertyContacts[].contactRole` via `ContactRole` | Enum role labels only; names, free text, phones, emails and company/person details never copied |
| `parking_flags` | `propertyApartment.residentialProfile.hasNoParkingAvailable`, `hasVisitorParkingAvailable` | Exact supplied booleans; missing/null omitted. Amenities, not truck counts or parking permission |
| `size_source`, `year_source`, `year_status`, `join_method` | Static provenance labels | Private measure, year uncertainty and exact-ID method metadata |

The kit says `hasVisitorParkingAvailable` can default false when the original
source value was missing. Reported false is not independent proof of no visitor
parking. Other parking counts/policies and imagery capacity need separate evidence.

## Availability policy

Only `listingStatus=1` (`Active`) can produce true. Require positive
`forLeaseSummary.totalAvailableSquareFeet` for a single-property listing, or
`forLeaseSummary.properties[].totalAvailableSquareFeet` for an explicit member,
plus a matching `forLeaseSummary.spaces[]` entry with positive `squareFeetMax`,
explicitly false `isLeasePending`, no supplied `dateOffMarket`, no true
`isInventoryOffMarket`, and a valid `availableOnDate` or `availabilityType` 1–4
(30/60/90/120-day notice). Never assign a park-wide rollup to each member building.

Type 0 is unknown; types 5–7 (TBD/arranged/negotiable) alone do not establish
timing. Future dates describe marketed availability, not immediate occupancy.
Many supplied spaces omit off-market fields, so the positive attributable rollup
also guards against historical detail. Listing/detail disagreements and changes
after the research snapshot remain limitations.

Known nonactive listings or a property-attributable zero rollup yield
`not_available` unless a positive/unresolved listing supersedes them. Missing
listings, unknown status/timing and sale/auction offers without verified lease
space yield `unknown`. Both have `available=false` with an explicit reason;
neither is labelled occupied. Vacancy percent, tenancies, apartment rentals and
assets for sale are not substitutes for commercial lease availability.

## Verified coverage

The private parquet has **13,096 distinct property/model pairs / 3,288 properties**.
Los Angeles: 5,957 pairs / 1,554 properties; Houston: 7,139 pairs / 1,734 properties.
All 3,339 inputs have usable primary geography/address; 51 lack a model. No mapping
PropertyId is missing from commercial property input. Fifty-five model IDs have
multiple supplied PropertyIds: retain the explicit pairs rather than reassigning
them. The tour must use the Shot's own property/model pair.

Joined availability is **443 available / 109 not_available / 2,736 unknown**.
Seven joined properties have unknown completion year; two have unknown GBA.
Two raw records have RBA above GBA; report the inconsistency without changing GBA.
Counts below are distinct properties; availability counts refer to those with scans.

| City | Type | Properties | With scans | Available | Unknown availability |
| --- | --- | ---: | ---: | ---: | ---: |
| Houston | Flex | 21 | 20 | 9 | 4 |
| Houston | GeneralRetail | 41 | 36 | 20 | 12 |
| Houston | Healthcare | 1 | 1 | 0 | 1 |
| Houston | Hospitality | 54 | 54 | 0 | 54 |
| Houston | Industrial | 98 | 93 | 50 | 25 |
| Houston | Land | 2 | 0 | 0 | 0 |
| Houston | Multifamily | 1,348 | 1,344 | 21 | 1,313 |
| Houston | Office | 191 | 184 | 127 | 47 |
| Houston | Specialty | 2 | 2 | 0 | 1 |
| Los Angeles | Flex | 10 | 9 | 3 | 5 |
| Los Angeles | GeneralRetail | 24 | 23 | 15 | 7 |
| Los Angeles | Healthcare | 1 | 1 | 0 | 1 |
| Los Angeles | Hospitality | 1 | 1 | 1 | 0 |
| Los Angeles | Industrial | 24 | 24 | 8 | 11 |
| Los Angeles | Land | 3 | 1 | 0 | 1 |
| Los Angeles | Multifamily | 1,417 | 1,402 | 114 | 1,242 |
| Los Angeles | Office | 98 | 90 | 75 | 10 |
| Los Angeles | Specialty | 3 | 3 | 0 | 2 |

Lane A's published `cache/shot-index/CURRENT` generation: 608 shots / 19 properties
/ 19 pairs. **All 19 IDs and all 19 pairs overlap**, with zero unmatched IDs/pairs.
Indexed availability: 3 available / 2 not_available / 14 unknown. These are
Matterport-capture samples, not a representative survey of either city's market.

## Reproduce and provision privately

Baseline environment plus `duckdb==2.0.0`, `pyarrow==26.0.1`; the integration
captain maintains dependency pins:

```sh
python -m data.build_join
python -m pytest -q data/tests/test_costar_live.py
TYPECAST_USE_MOCKS=0 python -c 'from data.costar_tools import search_costar; print(len(search_costar(available_only=False)))'
```

The builder reads all datasets through DuckDB, joins exact IDs there, reports
aggregates only and publishes parquet atomically. Failure preserves the old join;
parser/database failures are sanitized to avoid source fragments. Its CLI rejects
output outside `cache/`. No raw records or source contacts are persisted elsewhere.

Live `search_costar`/`get_property` preserve signatures and never fall back to mocks
when the join is missing/corrupt. One deterministic representative model per
property is returned; parquet keeps every pair. Exact enum types, known year bounds,
known GBA minimum and known availability filters apply before the limit. Unknowns
cannot pass hard filters. `era_year_range("1980s")` returns `(1980, 1989)`; years
and ascending ranges work, ambiguous two-digit decades fail. This is a calendar
helper, not a visual-style estimate.

Published indexed IDs are prioritized before the search limit; remaining CoStar
candidates stay searchable. The default LA pool contains 500 properties and all
19 indexed IDs (previous property-ID order included 5). `indexed_property_ids()`
exposes the set for agent pool selection. Missing index returns an empty set;
corrupt published metadata fails explicitly.

Each teammate provisions kit/index privately or uses a sponsor-permitted private
authenticated team service: a local path is not shared storage. Apply sponsor
expiration/deletion rules to source and derived caches. No public cache serving.
Vexcel uses property geocodes; this kit has no Vexcel imagery ID or verified extract
join. Aerial/logistics evidence is a separate step.
