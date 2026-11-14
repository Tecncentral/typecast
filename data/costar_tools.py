"""Owner 2. CoStar filter over cache/join.parquet (built by data/join.py).

TYPECAST_USE_MOCKS=1 reads mocks/property.json instead.
Unknown year_built or size_sqft passes the year and size filters and stays None on
the Property, so callers can show the gap. CoStar files stay in cache/; never commit them.
"""

import json
import os
import pathlib

from contracts.schemas import Property

ROOT = pathlib.Path(__file__).resolve().parents[1]
USE_MOCKS = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"

_JOIN = ROOT / "cache" / "join.parquet"


def _all() -> list[Property]:
    if USE_MOCKS:
        return [
            Property(**p)
            for p in json.loads((ROOT / "mocks/property.json").read_text())
        ]
    return _load_live()


def _load_live() -> list[Property]:
    if not _JOIN.exists():
        raise FileNotFoundError(
            f"join.parquet not found at {_JOIN}; run data/join.py first"
        )
    import duckdb

    result = duckdb.connect().execute(
        f"SELECT * FROM read_parquet('{_JOIN.as_posix()}')"
    )
    columns = [c[0] for c in result.description]
    return [Property(**dict(zip(columns, row))) for row in result.fetchall()]


def get_property(property_id: str) -> Property:
    for p in _all():
        if p.property_id == property_id:
            return p
    raise KeyError(property_id)


def search_costar(
    city: str = "Los Angeles",
    types: list[str] | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    min_sqft: float | None = None,
    available_only: bool = True,
    limit: int = 500,
) -> list[Property]:
    out = [p for p in _all() if p.city == city and p.model_id]
    if types:
        out = [p for p in out if p.type in types]
    if year_min is not None:
        out = [p for p in out if p.year_built is None or p.year_built >= year_min]
    if year_max is not None:
        out = [p for p in out if p.year_built is None or p.year_built <= year_max]
    if min_sqft is not None:
        out = [p for p in out if p.size_sqft is None or p.size_sqft >= min_sqft]
    if available_only:
        out = [p for p in out if p.available]
    return out[:limit]
