"""Owner 1. Shot search. Returns mock data until the real index exists.

Real version: embed the query (text, or the example shot's vector), take the top-k
by cosine similarity over cache/embeddings.npy, then apply the filters below.
"""
import json, os, pathlib
from typing import Optional
from contracts.schemas import Shot, ShotFit
from index.geometry import check_fit

ROOT = pathlib.Path(__file__).resolve().parents[1]
USE_MOCKS = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"


def _all_shots() -> list[Shot]:
    if USE_MOCKS:
        return [Shot(**s) for s in json.loads((ROOT / "mocks/shot.json").read_text())]
    raise NotImplementedError("Owner 1: load the real index here")


def get_shot(shot_id: str) -> Shot:
    for s in _all_shots():
        if s.shot_id == shot_id:
            return s
    raise KeyError(shot_id)


def search_shots(query_text: Optional[str] = None, query_shot_id: Optional[str] = None,
                 property_ids: Optional[list[str]] = None, min_area_m2: Optional[float] = None,
                 min_ceiling_m: Optional[float] = None, min_depth_m: Optional[float] = None,
                 k: int = 200) -> list[Shot]:
    if not query_text and not query_shot_id:
        raise ValueError("give query_text or query_shot_id")
    shots = _all_shots()
    if query_shot_id:                       # LookAlike: never return the same building
        src = get_shot(query_shot_id)
        shots = [s for s in shots if s.property_id != src.property_id]
    if property_ids is not None:
        shots = [s for s in shots if s.property_id in set(property_ids)]
    if min_area_m2 is not None:
        shots = [s for s in shots if s.room_area_m2 is None or s.room_area_m2 >= min_area_m2]
    if min_ceiling_m is not None:
        shots = [s for s in shots if s.ceiling_m is None or s.ceiling_m >= min_ceiling_m]
    if min_depth_m is not None:
        shots = [s for s in shots if s.depth_m is None or s.depth_m >= min_depth_m]
    return sorted(shots, key=lambda s: -(s.score or 0))[:k]


def check_shot(shot_id: str, focal_mm: float = 24.0, frame_width_m: float = 6.0) -> ShotFit:
    s = get_shot(shot_id)
    return check_fit(s.depth_m, s.ceiling_m, focal_mm, frame_width_m, s.measure_on_site)
