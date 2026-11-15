"""CoStar property filters over the private exact-ID join, or explicit mock mode."""
from __future__ import annotations

import json
import os
import pathlib
import re
from typing import Optional
from contracts.schemas import Property
from data.costar_parking import recorded_parking

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOIN_PATH = ROOT / "cache/join.parquet"
INDEX_ROOT = ROOT / "cache/shot-index"
USE_MOCKS = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"
_COLUMNS = ("property_id", "address", "city", "lat", "lon", "type", "year_built",
            "available", "size_sqft", "contact", "model_id", "availability_status",
            "availability_reason", "parking_flags", "listing_types")


def era_year_range(era: str) -> tuple[int, int]:
    """Return inclusive calendar bounds; visual style does not date a building.

    ``1980s`` means 1980–1989. Two-digit decades are century-ambiguous.
    """
    text = era.strip().lower()
    decade = re.fullmatch(r"(\d{3}0)(?:'s|s)", text)
    if decade:
        start = int(decade[1])
        return start, start + 9
    if re.fullmatch(r"\d{4}", text):
        return int(text), int(text)
    years = re.fullmatch(r"(\d{4})\s*[-–—]\s*(\d{4})", text)
    if years and int(years[1]) <= int(years[2]):
        return int(years[1]), int(years[2])
    raise ValueError("Use a four-digit decade, year or ascending year range.")


def indexed_property_ids() -> set[str]:
    """Read Lane A's published commercial IDs for private agent pool selection.

    No index is a valid provisioning state. A present but corrupt index fails
    explicitly rather than silently dropping the prioritization.
    """
    root = INDEX_ROOT
    pointer = root / "CURRENT"
    try:
        if pointer.is_file():
            generation = pointer.read_text().strip()
            if not re.fullmatch(r"[0-9a-f]{32}", generation):
                raise ValueError("Invalid generation")
            root = root / generation
        path = root / "shots.json"
        if not path.is_file():
            if pointer.is_file():
                raise ValueError("Missing generation shots")
            return set()
        shots = json.loads(path.read_text())
        if not isinstance(shots, list) or any(not isinstance(s, dict) or not s.get("property_id") for s in shots):
            raise ValueError("Invalid shot identifiers")
        return {str(s["property_id"]) for s in shots}
    except Exception:
        raise RuntimeError("Private Matterport index metadata is invalid; rebuild the index.") from None


def _live(where: str = "TRUE", parameters: list | None = None, limit: int | None = None,
          prioritize_index: bool = False) -> list[Property]:
    if not JOIN_PATH.is_file():
        raise RuntimeError("Private CoStar join is missing; run python -m data.build_join. Live mode does not use fixtures.")
    try:
        import duckdb
    except ImportError:
        raise RuntimeError("Live CoStar retrieval requires the agreed duckdb dependency.") from None
    values = [str(JOIN_PATH), *(parameters or [])]
    query = ("SELECT " + ",".join(_COLUMNS) + " FROM read_parquet(?) WHERE " + where
             + " QUALIFY row_number() OVER (PARTITION BY property_id ORDER BY model_id)=1")
    indexed = sorted(indexed_property_ids()) if prioritize_index else []
    if indexed:
        query += " ORDER BY CASE WHEN property_id IN (" + ",".join("?" for _ in indexed) + ") THEN 0 ELSE 1 END,property_id,model_id"
        values.extend(indexed)
    else:
        query += " ORDER BY property_id,model_id"
    if limit is not None:
        query += " LIMIT ?"
        values.append(limit)
    try:
        with duckdb.connect(":memory:") as connection:
            columns = {row[0] for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(JOIN_PATH)]).fetchall()}
            if "listing_types" not in columns:
                query = query.replace(",listing_types FROM", ",[]::VARCHAR[] AS listing_types FROM", 1)
            rows = connection.execute(query, values).fetchall()
        recorded = recorded_parking()
        return [Property(**dict(zip(_COLUMNS, row)), parking_spaces=recorded.get(str(row[0]), {}))
                for row in rows]
    except Exception:
        # Database errors may contain source values; expose only a repair hint.
        raise RuntimeError("Private CoStar join is invalid; rebuild with python -m data.build_join.") from None


def _all() -> list[Property]:
    if USE_MOCKS:
        return [Property(**p) for p in json.loads((ROOT / "mocks/property.json").read_text())]
    return _live()


def get_property(property_id: str) -> Property:
    if not USE_MOCKS:
        rows = _live("property_id=?", [property_id], limit=1)
        if rows:
            return rows[0]
    else:
        for p in _all():
            if p.property_id == property_id:
                return p
    raise KeyError(property_id)


def search_costar(city: str = "Los Angeles", types: Optional[list[str]] = None,
                  year_min: Optional[int] = None, year_max: Optional[int] = None,
                  min_sqft: Optional[float] = None, available_only: bool = True,
                  limit: int = 500) -> list[Property]:
    if limit < 0:
        raise ValueError("limit must be nonnegative")
    if not USE_MOCKS:
        clauses, values = ["lower(city)=lower(?)", "model_id IS NOT NULL"], [city]
        if types:
            clauses.append("type IN (" + ",".join("?" for _ in types) + ")")
            values.extend(types)
        for column, operator, value in (("year_built", ">=", year_min), ("year_built", "<=", year_max),
                                         ("size_sqft", ">=", min_sqft)):
            if value is not None:
                clauses.append(f"{column} IS NOT NULL AND {column}{operator}?")
                values.append(value)
        if available_only:
            clauses.append("available=TRUE AND availability_status='available'")
        return _live(" AND ".join(clauses), values, limit, prioritize_index=True)
    out = [p for p in _all() if p.city == city and p.model_id]
    if types:
        out = [p for p in out if p.type in types]
    if year_min is not None:
        out = [p for p in out if p.year_built is not None and p.year_built >= year_min]
    if year_max is not None:
        out = [p for p in out if p.year_built is not None and p.year_built <= year_max]
    if min_sqft is not None:
        out = [p for p in out if p.size_sqft is not None and p.size_sqft >= min_sqft]
    if available_only:
        out = [p for p in out if p.available]
    return out[:limit]
