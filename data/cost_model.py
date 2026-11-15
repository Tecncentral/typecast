"""Scenario cost comparison for one property: found location, build set, standing set, CGI.

Pure functions: no network and no kit access. The only file read is the precomputed
cache/rent/<property_id>.json written by data.rent_precompute, and only for the
rent_prorated_floor reference line.

Every number lives in DEFAULT_ASSUMPTIONS or REIMAGINING_TABLE with a source, a date and a
note, and any of them can be overridden per call. Entries tagged "ASSUMPTION, needs a real
quote" are editable placeholders, not market data. Each assumption has low, value and high;
value is the midpoint of a supplied range, or the single figure when there is no range.

Results are scenario estimates, not verified savings.
"""

from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENT_DIR = ROOT / "cache/rent"
LABEL = "scenario estimate, not verified savings"

BENCHMARK = "benchmark (supplied, unverified)"
PLACEHOLDER = "ASSUMPTION, needs a real quote"
PUBLIC_ESTIMATE = "PUBLIC ESTIMATE, not a quote"
USER_INPUT = "user input"
OVERRIDE = "user override"

_SUPPLIED = "unknown; supplied 2026-11-15"
_CREATED = "2026-11-15"
_EDITABLE = f"{PLACEHOLDER}. Editable placeholder, not a market figure."
_LEVELS = ("low", "value", "high")
_PROPERTY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def _entry(value, unit, source, date, note, quality, low=None, high=None):
    return {
        "value": value,
        "low": value if low is None else low,
        "high": value if high is None else high,
        "unit": unit,
        "source": source,
        "date": date,
        "note": note,
        "quality": quality,
    }


DEFAULT_ASSUMPTIONS = {
    "location_day_rate": _entry(
        1835.0,
        "USD per day",
        "Giggster LA average about $222/hr; Peerspace Hollywood film production about $145/hr",
        _SUPPLIED,
        "10-hour day: low $145 x 10, high $222 x 10, value is the midpoint. Booking price for a found "
        "location before agency fee and insurance.",
        BENCHMARK,
        low=1450.0,
        high=2220.0,
    ),
    "hours_per_day": _entry(
        10,
        "hours",
        "Same benchmarks (10-hour day)",
        _SUPPLIED,
        "Also converts the crew day rate to an hourly rate for travel time.",
        BENCHMARK,
    ),
    "agency_fee_rate": _entry(
        0.225,
        "fraction of location fee",
        "Supplied range 15 to 30 percent",
        _SUPPLIED,
        "Value is the midpoint. Applied to the found-location fee only (a modelling choice, not sourced).",
        BENCHMARK,
        low=0.15,
        high=0.30,
    ),
    "studio_day_rate": _entry(
        1600.0,
        "USD per day",
        "LA mid-range studio, supplied $1,200 to $2,000/day",
        _SUPPLIED,
        "Value is the midpoint. Used as the stage for the build-set and CGI scenarios.",
        BENCHMARK,
        low=1200.0,
        high=2000.0,
    ),
    "standing_set_day_rate": _entry(
        1999.0,
        "USD per day",
        "Standing office set, supplied 'from about $1,999/day'",
        _SUPPLIED,
        "A 'from' price is a floor, so low, value and high are all the floor. The real price may be higher.",
        BENCHMARK,
    ),
    "insurance_per_shoot_day": _entry(
        650.0,
        "USD per shoot day",
        "Supplied $300 to $1,000 per shoot day",
        _SUPPLIED,
        "Value is the midpoint. Charged once per shoot day in every scenario.",
        BENCHMARK,
        low=300.0,
        high=1000.0,
    ),
    "set_construction_per_sqft": _entry(
        25.0,
        "USD per sq ft",
        "One public production-blog estimate for a simple 20x30 ft interior; high end is a team assumption",
        "2026-11-15",
        "Derived from one public production-blog estimate for a simple 20x30 ft interior: materials "
        "$1,500-4,000 plus build crew $4,500-8,100. Excludes design fees. High end is a team "
        "assumption. Still needs a real studio quote.",
        PUBLIC_ESTIMATE,
        low=10.0,
        high=40.0,
    ),
    "cgi_per_shot": _entry(
        5000.0,
        "USD per shot",
        "Public 2026 VFX pricing guide (Vitrina)",
        "2026-11-15",
        "Public 2026 VFX pricing guide (Vitrina), mid-complexity set replacement or environment "
        "extension, $5,000-25,000 per shot. Value set to the low end so the headline savings claim "
        "is conservative.",
        PUBLIC_ESTIMATE,
        low=5000.0,
        high=25000.0,
    ),
    "cgi_shots_per_scene": _entry(
        8,
        "shots",
        "Placeholder",
        _CREATED,
        _EDITABLE + " The number of CGI shots in the scene.",
        PLACEHOLDER,
    ),
    "scouting_trip_cost": _entry(
        400.0,
        "USD per trip",
        "Placeholder",
        _CREATED,
        _EDITABLE,
        PLACEHOLDER,
    ),
    "crew_day_rate": _entry(
        600.0,
        "USD per person per day",
        "Placeholder",
        _CREATED,
        _EDITABLE,
        PLACEHOLDER,
    ),
    "crew_size": _entry(
        10,
        "people",
        "Placeholder",
        _CREATED,
        _EDITABLE + " Default crew head count for travel time.",
        PLACEHOLDER,
    ),
}


def _method(unit, unit_cost, per_shoot_day=False):
    return {
        "unit": unit,
        "unit_cost": unit_cost,
        "per_shoot_day": per_shoot_day,
        "source": "Placeholder",
        "date": _CREATED,
        "note": _EDITABLE,
        "quality": PLACEHOLDER,
    }


REIMAGINING_TABLE = {
    "paint": _method("sq ft", 2.5),
    "flooring": _method("sq ft", 6.0),
    "fixtures": _method("item", 250.0),
    "furniture_rental": _method("item", 75.0, per_shoot_day=True),
    "framing": _method("sq ft", 12.0),
    "foam_plaster_piece": _method("piece", 400.0),
    "printed_prop_3d": _method("prop", 150.0),
}


def _finite(value, name, *, positive=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 or (positive and value == 0):
        raise ValueError(
            f"{name} must be {'greater than' if positive else 'at least'} zero"
        )
    return value


def _count(value, name, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be a whole number of at least {minimum}")
    return value


def resolve_assumptions(overrides: dict | None = None) -> tuple[dict, dict]:
    """Return copies of the assumptions and the reimagining table with overrides applied."""
    assumptions, table = (
        copy.deepcopy(DEFAULT_ASSUMPTIONS),
        copy.deepcopy(REIMAGINING_TABLE),
    )
    for key, value in (overrides or {}).items():
        if key == "reimagining":
            for method, unit_cost in value.items():
                if method not in table:
                    raise ValueError(
                        f"Unknown reimagining method {method!r}; use one of {sorted(table)}"
                    )
                table[method].update(
                    unit_cost=_finite(unit_cost, f"reimagining.{method}"),
                    quality=OVERRIDE,
                )
        elif key in assumptions:
            number = _finite(value, key)
            assumptions[key].update(
                value=number, low=number, high=number, quality=OVERRIDE
            )
        else:
            raise ValueError(
                f"Unknown assumption {key!r}; use one of {sorted(assumptions)}"
            )
    return assumptions, table


def _changes(change_list, table) -> list[dict]:
    changes = []
    for change in change_list or []:
        method = change.get("method") if isinstance(change, dict) else None
        if method not in table:
            raise ValueError(
                f"Unknown change method {method!r}; use one of {sorted(table)}"
            )
        quantity = _finite(change.get("quantity"), f"{method} quantity")
        changes.append(
            {
                "method": method,
                "quantity": quantity,
                "label": str(change.get("label") or ""),
            }
        )
    return changes


def _usd(amount):
    return f"${amount:,.2f}"


def _insurance(ctx, level):
    rate = ctx["assumptions"]["insurance_per_shoot_day"][level]
    return (
        "Insurance",
        rate * ctx["days"],
        f"{_usd(rate)}/shoot day x {ctx['days']} day(s)",
        ["insurance_per_shoot_day", "shoot_days"],
    )


def _stage(ctx, level, label):
    rate = ctx["assumptions"]["studio_day_rate"][level]
    return (
        label,
        rate * ctx["days"],
        f"{_usd(rate)}/day x {ctx['days']} day(s)",
        ["studio_day_rate", "shoot_days"],
    )


def _found_location(ctx, level):
    a, days = ctx["assumptions"], ctx["days"]
    day_rate, fee_rate = a["location_day_rate"][level], a["agency_fee_rate"][level]
    fee = day_rate * days
    lines = [
        (
            "Location fee (benchmark day rate x shoot days)",
            fee,
            f"{_usd(day_rate)}/day x {days} day(s)",
            ["location_day_rate", "shoot_days"],
        ),
        (
            "Agency fee",
            fee * fee_rate,
            f"{fee_rate:.1%} of the location fee",
            ["agency_fee_rate", "location_day_rate", "shoot_days"],
        ),
        _insurance(ctx, level),
    ]
    if ctx["trips"]:
        cost = a["scouting_trip_cost"][level]
        lines.append(
            (
                "Scouting trips",
                cost * ctx["trips"],
                f"{ctx['trips']} trip(s) x {_usd(cost)}",
                ["scouting_trips", "scouting_trip_cost"],
            )
        )
    for change in ctx["changes"]:
        entry, quantity = ctx["table"][change["method"]], change["quantity"]
        multiplier = days if entry["per_shoot_day"] else 1
        suffix = f" x {days} day(s)" if entry["per_shoot_day"] else ""
        label = change["label"] or change["method"].replace("_", " ")
        lines.append(
            (
                f"Change: {label}",
                quantity * entry["unit_cost"] * multiplier,
                f"{quantity:g} {entry['unit']} x {_usd(entry['unit_cost'])}/{entry['unit']}{suffix}",
                [
                    f"reimagining.{change['method']}",
                    *(["shoot_days"] if entry["per_shoot_day"] else []),
                ],
            )
        )
    if ctx["drive_minutes"] is not None:
        hourly = a["crew_day_rate"][level] / a["hours_per_day"][level]
        hours = 2 * ctx["drive_minutes"] / 60
        lines.append(
            (
                "Crew travel time (round trip, paid at the crew rate)",
                ctx["crew"] * hours * hourly * days,
                f"{ctx['crew']} crew x {hours:.2f} h x {_usd(hourly)}/h x {days} day(s)",
                [
                    "crew",
                    "drive_minutes",
                    "crew_day_rate",
                    "hours_per_day",
                    "shoot_days",
                ],
            )
        )
    return lines


def _build_set(ctx, level):
    per_sqft = ctx["assumptions"]["set_construction_per_sqft"][level]
    return [
        _stage(ctx, level, "Stage rental (mid-range studio)"),
        (
            "Set construction",
            per_sqft * ctx["sqft"],
            f"{ctx['sqft']:g} sq ft x {_usd(per_sqft)}/sq ft",
            ["scene_sqft", "set_construction_per_sqft"],
        ),
        _insurance(ctx, level),
    ]


def _standing_set(ctx, level):
    rate = ctx["assumptions"]["standing_set_day_rate"][level]
    return [
        (
            "Standing set rental (floor price)",
            rate * ctx["days"],
            f"{_usd(rate)}/day x {ctx['days']} day(s)",
            ["standing_set_day_rate", "shoot_days"],
        ),
        _insurance(ctx, level),
    ]


def _cgi(ctx, level):
    a = ctx["assumptions"]
    per_shot, shots = a["cgi_per_shot"][level], a["cgi_shots_per_scene"][level]
    return [
        _stage(ctx, level, "Plate shoot stage (mid-range studio)"),
        (
            "CGI environment",
            per_shot * shots,
            f"{shots:g} shot(s) x {_usd(per_shot)}/shot",
            ["cgi_shots_per_scene", "cgi_per_shot"],
        ),
        _insurance(ctx, level),
    ]


def _describe(key, ctx):
    if key in ctx["inputs"]:
        return ctx["inputs"][key]
    if key.startswith("reimagining."):
        entry = ctx["table"][key.split(".", 1)[1]]
        return {
            "value": entry["unit_cost"],
            "unit": f"USD per {entry['unit']}",
            **{k: entry[k] for k in ("source", "date", "note", "quality")},
        }
    return dict(ctx["assumptions"][key])


def _scenario(builder, ctx):
    runs = {level: builder(ctx, level) for level in _LEVELS}
    lines = [
        {
            "label": mid[0],
            "amount_usd": round(mid[1], 2),
            "low_usd": round(low[1], 2),
            "high_usd": round(high[1], 2),
            "formula": mid[2],
            "inputs": mid[3],
        }
        for low, mid, high in zip(runs["low"], runs["value"], runs["high"], strict=True)
    ]
    keys = sorted({key for line in lines for key in line["inputs"]})
    return {
        "label": LABEL,
        "total_usd": round(sum(line["amount_usd"] for line in lines), 2),
        "total_low_usd": round(sum(line["low_usd"] for line in lines), 2),
        "total_high_usd": round(sum(line["high_usd"] for line in lines), 2),
        "lines": lines,
        "inputs_used": {key: _describe(key, ctx) for key in keys},
    }


def _load_rent(property_id: str) -> dict | None:
    path = RENT_DIR / f"{property_id}.json"
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["property_id"] != property_id or record["tier"] not in {
            "A",
            "B",
            "C",
        }:
            raise ValueError
        rate = record["usd_per_sf_year"]
        if rate is not None:
            _finite(rate, "rate")
    except (ValueError, KeyError, TypeError):
        raise RuntimeError(
            "Private rent cache is invalid; rerun python -m data.rent_precompute."
        ) from None
    return record


def _rent_floor(property_id: str, sqft, days: int) -> dict:
    reference = {
        "included_in_total": False,
        "note": "Reference only. A prorated rent floor is not a location price; the headline uses the benchmark day rate.",
    }
    rent = _load_rent(property_id)
    if rent is None:
        return {
            **reference,
            "amount_usd": None,
            "quality": "unknown",
            "reason": "No rent cache for this property; run python -m data.rent_precompute.",
        }
    detail = {
        **reference,
        "tier": rent["tier"],
        "quality": f"kit-derived, tier {rent['tier']}",
        "usd_per_sf_year": rent["usd_per_sf_year"],
        "source": rent.get("source"),
        "date": rent.get("date"),
        "age_years": rent.get("age_years"),
        "caveats": rent.get("caveats", []),
    }
    if rent["usd_per_sf_year"] is None:
        return {
            **detail,
            "amount_usd": None,
            "reason": f"Rent is unknown: {rent.get('source')}.",
        }
    amount = sqft * rent["usd_per_sf_year"] / 365 * days
    return {
        **detail,
        "amount_usd": round(amount, 2),
        "formula": f"{sqft:g} sq ft x {_usd(rent['usd_per_sf_year'])}/sq ft/year / 365 x {days} day(s)",
    }


def cost_compare(
    property_id: str,
    scene_sqft: float,
    shoot_days: int,
    change_list: list[dict] | None = None,
    scouting_trips: int = 1,
    crew: int | None = None,
    drive_minutes: float | None = None,
    assumptions: dict | None = None,
) -> dict:
    """Compare four ways to get the scene: found location, build set, standing set, CGI.

    change_list: [{"method": <key of REIMAGINING_TABLE>, "quantity": n, "label": optional}]
    priced onto the found location only. crew and drive_minutes drive crew travel time to the
    found location; leave drive_minutes as None to omit it. assumptions overrides any key of
    DEFAULT_ASSUMPTIONS, or {"reimagining": {method: unit_cost}}.
    """
    if not isinstance(property_id, str) or not _PROPERTY_ID.fullmatch(property_id):
        raise ValueError("Invalid property identifier")
    sqft = _finite(scene_sqft, "scene_sqft", positive=True)
    days = _count(shoot_days, "shoot_days", 1)
    trips = _count(scouting_trips, "scouting_trips", 0)
    if crew is not None:
        _count(crew, "crew", 0)
    if drive_minutes is not None:
        _finite(drive_minutes, "drive_minutes")
    resolved, table = resolve_assumptions(assumptions)

    inputs = {
        "scene_sqft": {"value": sqft, "unit": "sq ft", "quality": USER_INPUT},
        "shoot_days": {"value": days, "unit": "days", "quality": USER_INPUT},
        "scouting_trips": {"value": trips, "unit": "trips", "quality": USER_INPUT},
        "crew": {"value": crew, "unit": "people", "quality": USER_INPUT}
        if crew is not None
        else {
            **resolved["crew_size"],
            "note": "Default crew size. " + resolved["crew_size"]["note"],
        },
        "drive_minutes": {
            "value": drive_minutes,
            "unit": "minutes one way",
            "quality": USER_INPUT,
        },
    }
    ctx = {
        "assumptions": resolved,
        "table": table,
        "inputs": inputs,
        "sqft": sqft,
        "days": days,
        "trips": trips,
        "crew": inputs["crew"]["value"],
        "drive_minutes": drive_minutes,
        "changes": _changes(change_list, table),
    }
    found = _scenario(_found_location, ctx)
    found["rent_prorated_floor"] = _rent_floor(property_id, sqft, days)
    return {
        "label": LABEL,
        "property_id": property_id,
        "inputs": inputs,
        "found_location": found,
        "build_set": _scenario(_build_set, ctx),
        "standing_set": _scenario(_standing_set, ctx),
        "cgi": _scenario(_cgi, ctx),
    }
