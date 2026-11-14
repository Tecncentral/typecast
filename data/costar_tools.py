"""Owner 2. CoStar filter. Returns mock data until data/join.parquet exists.

Real version: a DuckDB query over cache/ files joined to Matterport ids.
CoStar files stay in cache/ on Owner 2's laptop only. Never commit them.
"""
import json, os, pathlib
from typing import Optional
from contracts.schemas import Property

ROOT = pathlib.Path(__file__).resolve().parents[1]
USE_MOCKS = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"


def _all() -> list[Property]:
    if USE_MOCKS:
        return [Property(**p) for p in json.loads((ROOT / "mocks/property.json").read_text())]
    raise NotImplementedError("Owner 2: query the joined table here")


def get_property(property_id: str) -> Property:
    for p in _all():
        if p.property_id == property_id:
            return p
    raise KeyError(property_id)


def search_costar(city: str = "Los Angeles", types: Optional[list[str]] = None,
                  year_min: Optional[int] = None, year_max: Optional[int] = None,
                  min_sqft: Optional[float] = None, available_only: bool = True,
                  limit: int = 500) -> list[Property]:
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
