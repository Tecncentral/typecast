"""Precompute private rent evidence per property from the CoStar kit.

Reads cache/join.parquet and the kit. Writes git-ignored cache/rent/<property_id>.json for
every joined property and cache/rent/market_medians.json. Stdout is aggregate counts only.

Tier A  active lease listing for that one property: per square foot, USD, known basis,
        midpoint of low and high. Multi-property listings are excluded.
Tier B  lease deal rate (per square foot, USD, known basis), newest first. Deals older
        than 3 years are flagged.
Tier C  median of tier A listings of the same city and CoStar type. "no reliable price"
        when that group is empty, and always for Multifamily: commercial-space rents are
        not apartment rent.

Known basis means RateBasis 1 (monthly, x12) or 2 (yearly, x1); 0 (unknown) is never
converted. Service types (net, gross and so on) are mixed and not normalized.

Run: python -m data.rent_precompute [--kit PATH] [--as-of YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

from data.build_join import JOIN_PATH, KIT_ROOT, _key, _listing_properties, _number

ROOT = Path(__file__).resolve().parents[1]
RENT_DIR = ROOT / "cache/rent"
KNOWN_BASIS = {1: 12, 2: 1}
USD = 1
SQUARE_FEET = 1
PER_SQUARE_FOOT = 0
ACTIVE_LISTING = 1
STALE_YEARS = 3
THIN_BELOW = 5
MULTIFAMILY = "Multifamily"
NO_PRICE = "no reliable price"
MIXED_SERVICE_TYPES = (
    "Service types (net, gross and so on) are mixed and not normalized."
)
_PROPERTY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class RentBuildError(RuntimeError):
    """A sanitized failure that cannot contain source records."""


def _parse_date(value) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _first_date(record: dict, fields: tuple[str, ...]) -> date | None:
    return next((d for d in (_parse_date(record.get(f)) for f in fields) if d), None)


def _midpoint(low, high) -> float | None:
    values = [v for v in (_number(low), _number(high)) if v is not None and v > 0]
    return sum(values) / len(values) if values else None


def _listing_rate(listing: dict) -> float | None:
    lease = listing.get("forLeaseSummary") or {}
    basis = lease.get("askingRateBasis")
    if (
        basis not in KNOWN_BASIS
        or lease.get("askingRateMeasurementType") != SQUARE_FEET
        or listing.get("monetaryUnit") != USD
    ):
        return None
    mid = _midpoint(lease.get("askingRateLow"), lease.get("askingRateHigh"))
    return None if mid is None else mid * KNOWN_BASIS[basis]


def _deal_rate(deal: dict) -> tuple[str, float] | None:
    if deal.get("monetaryUnit") != USD:
        return None
    actual = _number(deal.get("rateActual"))
    basis = deal.get("rateBasis")
    if (
        actual
        and actual > 0
        and deal.get("rateAmountType") == PER_SQUARE_FOOT
        and basis in KNOWN_BASIS
    ):
        return "actual", actual * KNOWN_BASIS[basis]
    asking = deal.get("askingRate")
    if isinstance(asking, dict) and asking.get("rateBasis") in KNOWN_BASIS:
        mid = _midpoint(asking.get("rateLow"), asking.get("rateHigh"))
        if mid is not None:
            return "asking", mid * KNOWN_BASIS[asking["rateBasis"]]
    return None


def _records(connection, path: Path):
    cursor = connection.execute(
        "SELECT json FROM read_json_objects(?, format='newline_delimited')", [str(path)]
    )
    while batch := cursor.fetchmany(512):
        for (raw,) in batch:
            yield json.loads(raw)


def _age_years(then: date | None, as_of: date) -> float | None:
    return None if then is None else max(0.0, round((as_of - then).days / 365.25, 1))


def _write_json(path: Path, payload: dict) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        dir=path.parent,
        prefix=".rent-",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        temporary = Path(handle.name)
    temporary.replace(path)


def _tier_a(entries: list[tuple], base: dict, as_of: date) -> dict:
    services = sorted({s for _, _, s in entries if s})
    dated = [d for _, d, _ in entries if d]
    newest = max(dated) if dated else None
    caveats = [
        "Asking rent from active listings, not a closed deal.",
        f"Service type: {', '.join(services) or 'unknown'}. {MIXED_SERVICE_TYPES}",
    ]
    if base["type"] == MULTIFAMILY:
        caveats.append(
            "Rate is for commercial space in a multifamily building, not apartment rent."
        )
    return {
        **base,
        "tier": "A",
        "usd_per_sf_year": round(statistics.median(r for r, _, _ in entries), 2),
        "source": "active lease listing",
        "date": newest.isoformat() if newest else None,
        "age_years": _age_years(newest, as_of),
        "comp_count": len(entries),
        "service_type": services,
        "caveats": caveats,
    }


def _tier_b(entries: list[tuple], base: dict, as_of: date) -> dict:
    dated = sorted((e for e in entries if e[0]), key=lambda e: e[0], reverse=True)
    when, kind, rate, service = dated[0] if dated else entries[0]
    age = _age_years(when, as_of)
    stale = age is not None and age > STALE_YEARS
    caveats = [
        f"Lease deal {kind} rate, not a current listing.",
        f"Service type: {service or 'unknown'}. {MIXED_SERVICE_TYPES}",
    ]
    if when is None:
        caveats.append("Deal date unknown, so its age cannot be checked.")
    if stale:
        caveats.append(f"Deal is {age} years old, older than {STALE_YEARS} years.")
    if base["type"] == MULTIFAMILY:
        caveats.append(
            "Rate is for commercial space in a multifamily building, not apartment rent."
        )
    return {
        **base,
        "tier": "B",
        "usd_per_sf_year": round(rate, 2),
        "source": f"lease deal ({kind} rate)",
        "date": when.isoformat() if when else None,
        "age_years": age,
        "stale": stale,
        "comp_count": len(entries),
        "service_type": [service] if service else [],
        "caveats": caveats,
    }


def _tier_c(group: dict | None, base: dict) -> dict:
    record = {**base, "tier": "C", "date": None, "age_years": None}
    if base["type"] == MULTIFAMILY:
        reason = "Commercial-space rents are not apartment rent."
    elif group is None:
        reason = "No tier A listings for this city and type."
    else:
        record.update(
            usd_per_sf_year=group["median_usd_per_sf_year"],
            source=f"median of {group['listings']} tier A listings, {base['city']} {base['type']}",
            comp_count=group["listings"],
            caveats=[
                "Median of other buildings' asking rents, not this building.",
                MIXED_SERVICE_TYPES,
                *(
                    [
                        f"Thin sample: {group['listings']} listings (fewer than {THIN_BELOW})."
                    ]
                    if group["thin"]
                    else []
                ),
            ],
        )
        return record
    record.update(
        usd_per_sf_year=None,
        source=NO_PRICE,
        comp_count=0,
        caveats=[f"{NO_PRICE.capitalize()}: {reason}", MIXED_SERVICE_TYPES],
    )
    return record


def build_rent(
    kit_root: Path = KIT_ROOT,
    join_path: Path = JOIN_PATH,
    out_dir: Path = RENT_DIR,
    as_of: date | None = None,
) -> dict:
    try:
        import duckdb
    except ImportError:
        raise RentBuildError(
            "Install the agreed duckdb dependency before building rent evidence."
        ) from None
    kit_root, join_path, out_dir = Path(kit_root), Path(join_path), Path(out_dir)
    as_of = as_of or datetime.now(UTC).date()
    listings = kit_root / "data/commercial-listing-summary.jsonl"
    occupancies = kit_root / "data/location-occupancy.jsonl"
    enums = kit_root / "schemas/enums.json"
    if not all(p.is_file() for p in (listings, occupancies, enums, join_path)):
        raise RentBuildError(
            "Rent build needs the kit listings, occupancies, enums and cache/join.parquet."
        )
    try:
        service = json.loads(enums.read_text(encoding="utf-8")).get("ServiceType", {})
        with duckdb.connect(":memory:") as connection:
            joined = connection.execute(
                "SELECT property_id, any_value(city), any_value(type) FROM read_parquet(?)"
                " GROUP BY property_id ORDER BY property_id",
                [str(join_path)],
            ).fetchall()
            meta = {pid: (city, ptype) for pid, city, ptype in joined}
            if not all(_PROPERTY_ID.fullmatch(pid) for pid in meta):
                raise RentBuildError(
                    "Join contains a property id that cannot be a file name."
                )

            listing_rates = defaultdict(list)
            for listing in _records(connection, listings):
                if (
                    listing.get("listingStatus") != ACTIVE_LISTING
                    or listing.get("forLeaseSummary") is None
                ):
                    continue
                members = _listing_properties(listing)
                rate = _listing_rate(listing)
                if len(members) != 1 or rate is None:
                    continue
                (pid,) = members
                if pid in meta:
                    when = _first_date(
                        listing,
                        (
                            "certifiedFreshDate",
                            "listingStatusUpdatedDate",
                            "createdDate",
                        ),
                    )
                    name = service.get(
                        str(listing["forLeaseSummary"].get("serviceType"))
                    )
                    listing_rates[pid].append((rate, when, name))

            deals = defaultdict(list)
            for record in _records(connection, occupancies):
                pid, deal = _key(record.get("propertyId")), record.get("leaseDeal")
                found = (
                    _deal_rate(deal) if pid in meta and isinstance(deal, dict) else None
                )
                if found:
                    when = _first_date(deal, ("signDate", "commencementDate"))
                    deals[pid].append(
                        (when, *found, service.get(str(deal.get("serviceType"))))
                    )
    except RentBuildError:
        raise
    except (duckdb.Error, OSError, ValueError, TypeError, AttributeError, KeyError):
        raise RentBuildError(
            "Rent build failed; verify the private kit schema and cache/join.parquet."
        ) from None

    samples, sample_properties = defaultdict(list), defaultdict(set)
    mix = Counter()
    for pid, entries in listing_rates.items():
        for rate, _, name in entries:
            samples[meta[pid]].append(rate)
            sample_properties[meta[pid]].add(pid)
            mix[name or "unknown"] += 1
    groups = {}
    for (city, ptype), rates in samples.items():
        groups[(city, ptype)] = {
            "city": city,
            "type": ptype,
            "listings": len(rates),
            "properties": len(sample_properties[(city, ptype)]),
            "median_usd_per_sf_year": round(statistics.median(rates), 2),
            "thin": len(rates) < THIN_BELOW,
            "usable_for_tier_c": ptype != MULTIFAMILY,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    tiers, stale_deals, no_price = Counter(), 0, 0
    for pid, (city, ptype) in meta.items():
        base = {
            "property_id": pid,
            "city": city,
            "type": ptype,
            "as_of": as_of.isoformat(),
        }
        if listing_rates.get(pid):
            record = _tier_a(listing_rates[pid], base, as_of)
        elif deals.get(pid):
            record = _tier_b(deals[pid], base, as_of)
        else:
            record = _tier_c(groups.get((city, ptype)), base)
        tiers[(ptype, record["tier"])] += 1
        stale_deals += bool(record.get("stale"))
        no_price += record["source"] == NO_PRICE
        _write_json(out_dir / f"{pid}.json", record)

    removed = 0
    for path in out_dir.glob("*.json"):
        if path.name != "market_medians.json" and path.stem not in meta:
            path.unlink()
            removed += 1
    _write_json(
        out_dir / "market_medians.json",
        {
            "as_of": as_of.isoformat(),
            "method": "Median of tier A listing rates per city and CoStar type; listing-level, "
            "single-property active lease listings, per square foot, USD, known basis.",
            "service_types": MIXED_SERVICE_TYPES,
            "service_type_mix": dict(sorted(mix.items())),
            "thin_below": THIN_BELOW,
            "multifamily_note": "Multifamily medians are commercial space inside apartment buildings"
            " and are never used as apartment rent.",
            "groups": sorted(groups.values(), key=lambda g: (g["city"], g["type"])),
        },
    )
    by_tier = Counter()
    for (_, tier), count in tiers.items():
        by_tier[tier] += count
    return {
        "as_of": as_of.isoformat(),
        "properties": len(meta),
        "tiers": dict(sorted(by_tier.items())),
        "tier_by_type": {f"{t}/{k}": n for (t, k), n in sorted(tiers.items())},
        "tier_b_stale": stale_deals,
        "tier_c_no_reliable_price": no_price,
        "median_groups": len(groups),
        "thin_groups": sum(g["thin"] for g in groups.values()),
        "removed_stale_files": removed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kit", type=Path, default=KIT_ROOT)
    parser.add_argument("--join", type=Path, default=JOIN_PATH)
    parser.add_argument("--out", type=Path, default=RENT_DIR)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    args = parser.parse_args()
    if not args.out.resolve().is_relative_to((ROOT / "cache").resolve()):
        parser.error("Rent output must be inside the private cache directory.")
    try:
        print(
            json.dumps(
                build_rent(args.kit, args.join, args.out, args.as_of),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except RentBuildError as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
