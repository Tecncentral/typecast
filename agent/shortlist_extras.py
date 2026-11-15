"""Cost and travel for the shortlist, from Owner 2's pricing and distance code and #43's road routing.

costs(): data/cost_model.cost_compare for each pick (found location vs build a set vs standing set vs
CGI, each low / likely / high) plus the building's own CoStar rent as a reference line. The headline
found-location figure uses a benchmark day rate, so it is the same for every pick; the rent line is
what differs. Rent with no reliable price (always for Multifamily, where the kit's rents are
ground-floor retail, not apartments) is hidden, never shown as the building's rent.

commutes(): one-way driving minutes from a production base with index/commute.route_commutes (OSRM,
no traffic). Where routing gives no answer, the straight-line distance from data/radius is returned
instead, labelled as such and never converted to minutes. For Los Angeles it also says whether the
property is inside the 30-mile studio zone, which is itself defined as a straight-line radius.
"""
from __future__ import annotations

from data.cost_model import LABEL as COST_LABEL, _load_rent, cost_compare
from data.rent_precompute import MULTIFAMILY
from data.radius import LABEL as RADIUS_LABEL, haversine_km

DOLLAR_LINE = "Scenario estimate from public pricing ranges and CoStar rent data, not verified savings."
BASES = {
    "la-studio-zone": {"label": "LA studio zone centre (Beverly Blvd & La Cienega Blvd)", "city": "Los Angeles",
                       "lat": 34.0762, "lon": -118.3767},
    "la-downtown": {"label": "Downtown LA", "city": "Los Angeles", "lat": 34.0522, "lon": -118.2437},
    "hou-downtown": {"label": "Downtown Houston", "city": "Houston", "lat": 29.7604, "lon": -95.3698},
    "hou-energy-corridor": {"label": "Energy Corridor, Houston", "city": "Houston", "lat": 29.7835, "lon": -95.6260},
}
STUDIO_ZONE_KM = 30 * 1.609344
STUDIO_ZONE_CENTRE = (34.0762, -118.3767)


def _rent(property_id: str, found: dict) -> dict:
    """The building's CoStar rent as a reference, labelled for what it is, or hidden.

    Multifamily rates in the kit are for the commercial space in the building (ground-floor
    retail), never apartment rent, so they always say so; tier C is other buildings' median.
    """
    ref = found.get("rent_prorated_floor") or {}
    if ref.get("usd_per_sf_year") is None:
        return {"shown": False, "tier": ref.get("tier"),
                "reason": "No reliable rent for this building" + (": " + ref["caveats"][0] if ref.get("caveats") else ".")}
    record = _load_rent(property_id) or {}
    multifamily = record.get("type") == MULTIFAMILY or any("multifamily building" in c for c in ref.get("caveats", []))
    if multifamily:
        label = "Ground-floor retail rent (commercial space in this apartment building, not apartment rent)"
    elif ref.get("tier") == "C":
        label = "Area median rent (other buildings of this type, not this building)"
    else:
        label = "This building's CoStar rent"
    return {"shown": True, "tier": ref.get("tier"), "label": label, "multifamily": multifamily,
            "usd_per_sf_year": ref["usd_per_sf_year"], "source": ref.get("source"), "date": ref.get("date"),
            "age_years": ref.get("age_years"), "caveats": ref.get("caveats", []),
            "prorated_usd": ref.get("amount_usd"), "note": ref.get("note")}


def costs(picks: list[dict], scene_sqft: float, shoot_days: int, drive_minutes: dict | None = None) -> dict:
    """picks: [{"property_id", "address"}]. drive_minutes: {property_id: minutes} when known."""
    drive_minutes = drive_minutes or {}
    per_pick = []
    scenarios = None
    for pick in picks[:10]:
        pid = str(pick["property_id"])
        minutes = drive_minutes.get(pid)
        result = cost_compare(pid, scene_sqft, shoot_days,
                              drive_minutes=minutes if isinstance(minutes, (int, float)) else None)
        found = result["found_location"]
        if scenarios is None:
            scenarios = {key: {k: result[key][k] for k in ("total_usd", "total_low_usd", "total_high_usd", "lines")}
                         for key in ("build_set", "standing_set", "cgi")}
        per_pick.append({"property_id": pid, "address": pick.get("address"),
                         "found_location": {k: found[k] for k in ("total_usd", "total_low_usd", "total_high_usd", "lines")},
                         "rent": _rent(pid, found)})
    return {"label": COST_LABEL, "dollar_line": DOLLAR_LINE, "scene_sqft": scene_sqft, "shoot_days": shoot_days,
            "alternatives": scenarios or {}, "picks": per_pick,
            "note": "The found-location figure uses a benchmark day rate, the same for every pick; each building's "
                    "own CoStar rent is shown beside it for reference."}


def commutes(base_id: str, picks: list[dict], *, mock: bool = False) -> dict:
    """picks: [{"property_id", "lat", "lon"}]. Road minutes, else a labelled straight-line distance."""
    from index.commute import route_commutes
    base = BASES.get(base_id)
    if base is None:
        raise ValueError("Unknown base")
    properties = {str(p["property_id"]): {"lat": p.get("lat"), "lon": p.get("lon")} for p in picks[:24]}
    routed = route_commutes({"lat": base["lat"], "lon": base["lon"]}, properties, mock=mock)
    rows = {}
    for pid, point in properties.items():
        row = dict(routed.get(pid) or {"status": "unknown"})
        lat, lon = point.get("lat"), point.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            km = haversine_km(base["lat"], base["lon"], lat, lon)
            row["straight_line_km"] = round(km, 1)
            row["straight_line_label"] = RADIUS_LABEL
            if base["city"] == "Los Angeles":
                zone_km = haversine_km(*STUDIO_ZONE_CENTRE, lat, lon)
                row["studio_zone"] = {"inside": zone_km <= STUDIO_ZONE_KM, "km_from_centre": round(zone_km, 1)}
        if isinstance(row.get("minutes"), (int, float)):
            row["minutes"] = round(row["minutes"])
            row["miles"] = round(row["miles"], 1) if isinstance(row.get("miles"), (int, float)) else None
        rows[pid] = row
    return {"base": {"id": base_id, **base}, "rows": rows,
            "note": "One-way driving estimates from OSRM / OpenStreetMap, no live traffic. Where routing gives no "
                    "answer, only the straight-line distance is shown, never converted to minutes.",
            "studio_zone_note": "LA's studio zone is a 30-mile radius from Beverly Blvd & La Cienega Blvd; "
                                "productions use it for crew travel rules."}
