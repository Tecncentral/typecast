"""FastAPI router for Typecast production planning, Director UI assets, and structured brainstorms."""

from __future__ import annotations

import math
import json
from pathlib import Path
from typing import Annotated, Any, Literal
from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from index.production_solver import solve_plans
from index.production_join import load_property_model_pairs
from index.search import ROOT, get_active_index, search_shots
from data import costar_tools, vexcel_tools
from data.costar_tools import get_property
from data.vexcel_tools import plan_logistics, enough_parking

class _ProductionRoute(APIRoute):
    """Keep invalid nonfinite inputs out of JSON validation-error responses."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validated(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # FastAPI's default error includes raw inputs, whose NaN/Infinity
                # values cannot be serialized by JSONResponse and become a 500.
                detail = [{key: error[key] for key in ("type", "loc", "msg")}
                          for error in exc.errors()]
                raise HTTPException(status_code=422, detail=detail) from None

        return validated


router = APIRouter(route_class=_ProductionRoute)
_STATIC_DIR = Path(__file__).resolve().parent


def _reject_bool(v: Any) -> Any:
    if isinstance(v, bool):
        raise ValueError("Boolean is not a valid numeric value")
    return v


def _finite_float(v: Any) -> float:
    _reject_bool(v)
    f = float(v)
    if not math.isfinite(f):
        raise ValueError("Value must be finite")
    return f


def _strict_int(v: Any) -> int:
    _reject_bool(v)
    if not isinstance(v, int):
        raise ValueError("Value must be an integer")
    return v


def _nonblank_str(v: Any, max_len: int) -> str:
    if not isinstance(v, str):
        raise ValueError("Value must be a string")
    s = v.strip()
    if not s or len(s) > max_len:
        raise ValueError(f"String must be 1..{max_len} non-whitespace characters")
    return s


StrictInt = Annotated[int, Field(strict=True)]
StrictFloat = Annotated[float, Field(strict=True)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SceneInput(_StrictModel):
    id: str
    heading: str
    description: str

    @field_validator("id")
    @classmethod
    def _v_id(cls, v: Any) -> str:
        return _nonblank_str(v, 60)

    @field_validator("heading")
    @classmethod
    def _v_heading(cls, v: Any) -> str:
        return _nonblank_str(v, 120)

    @field_validator("description")
    @classmethod
    def _v_desc(cls, v: Any) -> str:
        return _nonblank_str(v, 1000)


class PlanRequest(_StrictModel):
    scenes: list[SceneInput]
    max_locations: StrictInt = 3
    forbidden_property_ids: list[str] = Field(default_factory=list)
    require_available: bool = False
    trucks: StrictInt = 0
    cars: StrictInt = 0

    @field_validator("scenes")
    @classmethod
    def _v_scenes(cls, v: list[SceneInput]) -> list[SceneInput]:
        if not (1 <= len(v) <= 8):
            raise ValueError("scenes must contain 1..8 items")
        if len({s.id for s in v}) != len(v):
            raise ValueError("Duplicate scene IDs are not allowed")
        return v

    @field_validator("max_locations")
    @classmethod
    def _v_max_loc(cls, v: Any) -> int:
        iv = _strict_int(v)
        if not (1 <= iv <= 4):
            raise ValueError("max_locations must be 1..4")
        return iv

    @field_validator("forbidden_property_ids")
    @classmethod
    def _v_forb(cls, v: list[str]) -> list[str]:
        if len(v) > 24:
            raise ValueError("forbidden_property_ids max length is 24")
        return [_nonblank_str(pid, 64) for pid in v]

    @field_validator("trucks")
    @classmethod
    def _v_trucks(cls, v: Any) -> int:
        iv = _strict_int(v)
        if not (0 <= iv <= 20):
            raise ValueError("trucks must be 0..20")
        return iv

    @field_validator("cars")
    @classmethod
    def _v_cars(cls, v: Any) -> int:
        iv = _strict_int(v)
        if not (0 <= iv <= 200):
            raise ValueError("cars must be 0..200")
        return iv


class ActorBlock(_StrictModel):
    id: str
    name: str
    pose: Literal["stand", "sit", "walk"]
    x0: float
    y0: float
    x1: float
    y1: float
    scale: float

    @field_validator("id")
    @classmethod
    def _v_id(cls, v: Any) -> str:
        return _nonblank_str(v, 30)

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: Any) -> str:
        return _nonblank_str(v, 40)

    @field_validator("x0", "y0", "x1", "y1")
    @classmethod
    def _v_coord(cls, v: Any) -> float:
        f = _finite_float(v)
        if not (0.0 <= f <= 1.0):
            raise ValueError("Normalized coordinate must be within 0..1")
        return f

    @field_validator("scale")
    @classmethod
    def _v_scale(cls, v: Any) -> float:
        f = _finite_float(v)
        if not (0.3 <= f <= 2.0):
            raise ValueError("scale must be within 0.3..2.0")
        return f


class RehearsalShot(_StrictModel):
    duration_sec: float
    dialogue: str = ""
    actors: list[ActorBlock] = Field(default_factory=list)

    @field_validator("duration_sec")
    @classmethod
    def _v_dur(cls, v: Any) -> float:
        f = _finite_float(v)
        if not (1.0 <= f <= 30.0):
            raise ValueError("duration_sec must be within 1..30")
        return f

    @field_validator("dialogue")
    @classmethod
    def _v_dial(cls, v: Any) -> str:
        if not isinstance(v, str) or len(v) > 800:
            raise ValueError("dialogue must be a string <= 800 chars")
        return v

    @field_validator("actors")
    @classmethod
    def _v_actors(cls, v: list[ActorBlock]) -> list[ActorBlock]:
        if len(v) > 3:
            raise ValueError("At most 3 actors allowed")
        if len({a.id for a in v}) != len(v):
            raise ValueError("Duplicate actor IDs are not allowed")
        return v


class BrainstormRequest(_StrictModel):
    instruction: str
    heading: str
    description: str
    shot: RehearsalShot

    @field_validator("instruction")
    @classmethod
    def _v_inst(cls, v: Any) -> str:
        return _nonblank_str(v, 2000)

    @field_validator("heading")
    @classmethod
    def _v_head(cls, v: Any) -> str:
        return _nonblank_str(v, 120)

    @field_validator("description")
    @classmethod
    def _v_desc(cls, v: Any) -> str:
        return _nonblank_str(v, 1000)


class BrainstormProposal(_StrictModel):
    summary: str
    creative_note: str
    shot: RehearsalShot

    @field_validator("summary")
    @classmethod
    def _v_sum(cls, v: Any) -> str:
        return _nonblank_str(v, 400)

    @field_validator("creative_note")
    @classmethod
    def _v_note(cls, v: Any) -> str:
        return _nonblank_str(v, 800)


def _as_dict(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return dict(obj)
    return None


def _lookup_property(property_id: str) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        prop = _as_dict(get_property(property_id))
    except Exception:  # noqa: BLE001
        prop = None
    if prop is None:
        return None, [{"source": "costar", "field": "property", "status": "unknown", "message": "Property metadata unavailable"}]
    warnings: list[dict[str, str]] = []
    if prop.get("availability_status") not in {"available", "not_available"}:
        warnings.append({"source": "costar", "field": "availability", "status": "unknown", "message": "Availability status unverified"})
    elif prop.get("availability_status") == "not_available" or prop.get("available") is not True:
        warnings.append({"source": "costar", "field": "availability", "status": "unavailable", "message": "Property is not confirmed available"})
    return prop, warnings


def _lookup_logistics(property_id: str, trucks: int, cars: int) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        evidence = plan_logistics(property_id, trucks, cars)
        logi = _as_dict(evidence)
        if logi is not None:
            # The shared Logistics contract has counts and a status, not a feasibility flag.
            for field in ("truck_spaces", "car_spaces"):
                if (not isinstance(logi.get(field), int) or isinstance(logi[field], bool)
                        or logi[field] < 0):
                    logi[field] = None
            known = (logi.get("parking_status") in {"measured", "estimated"}
                     and all(isinstance(logi.get(field), int)
                             and not isinstance(logi[field], bool) and logi[field] >= 0
                             for field in ("truck_spaces", "car_spaces")))
            logi["enough_parking"] = enough_parking(evidence, trucks, cars) if known else None
    except Exception:  # noqa: BLE001
        logi = None
    if logi is None:
        return None, [{"source": "vexcel", "field": "parking_capacity", "status": "unknown", "message": "Aerial parking logistics unavailable"}]
    warnings: list[dict[str, str]] = []
    parking = logi.get("enough_parking")
    if parking is None:
        warnings.append({"source": "vexcel", "field": "parking_capacity", "status": "unknown", "message": "Parking capacity unknown for requested vehicles"})
    elif parking is False:
        warnings.append({"source": "vexcel", "field": "parking_capacity", "status": "insufficient", "message": "Insufficient estimated parking for requested vehicles"})
    elif logi.get("estimated") or logi.get("parking_status") == "estimated":
        warnings.append({"source": "vexcel", "field": "parking_capacity", "status": "estimated", "message": "Parking capacity is an estimate; verify before production"})
    return logi, warnings


def _valid_retrieval_hit(shot: Any) -> bool:
    """Reject malformed source identities instead of changing join/rejection keys."""
    for field, limit in (("property_id", 64), ("model_id", 120), ("shot_id", 120)):
        value = getattr(shot, field, None)
        if not isinstance(value, str) or not value or value != value.strip() or len(value) > limit:
            return False
    score = getattr(shot, "score", None)
    return (isinstance(score, (int, float)) and not isinstance(score, bool)
            and math.isfinite(score) and -1.0 <= score <= 1.0)


@router.get("/director")
def get_director_html() -> FileResponse:
    return FileResponse(_STATIC_DIR / "director.html", media_type="text/html")


@router.get("/director.js")
def get_director_js() -> FileResponse:
    return FileResponse(_STATIC_DIR / "director.js", media_type="application/javascript")


@router.get("/director-reel.js")
def get_director_reel_js() -> FileResponse:
    return FileResponse(_STATIC_DIR / "director-reel.js", media_type="application/javascript")


@router.get("/director-project.js")
def get_director_project_js() -> FileResponse:
    return FileResponse(_STATIC_DIR / "director-project.js", media_type="application/javascript")


@router.get("/director-checks.js")
def get_director_checks_js() -> FileResponse:
    return FileResponse(_STATIC_DIR / "director-checks.js", media_type="application/javascript")


@router.get("/director-ui.js")
def get_director_ui_js() -> FileResponse:
    return FileResponse(_STATIC_DIR / "director-ui.js", media_type="application/javascript")


@router.get("/director.css")
def get_director_css() -> FileResponse:
    return FileResponse(_STATIC_DIR / "director.css", media_type="text/css")


@router.post("/api/production/plan")
def post_production_plan(req: PlanRequest) -> dict[str, Any]:
    try:
        active_idx = get_active_index()
        mode = "mock" if getattr(active_idx, "is_mock", False) else "live"
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Shot retrieval index unavailable") from exc
    if any(bool(source.USE_MOCKS) != (mode == "mock") for source in (costar_tools, vexcel_tools)):
        raise HTTPException(status_code=503, detail="Retrieval and property/logistics source modes do not match")

    forbidden_set = set(req.forbidden_property_ids)
    verified_pairs = (load_property_model_pairs(ROOT / 'cache/property_models.parquet')
                      if mode == 'live' else None)
    mapped_properties = {p for p, _ in verified_pairs} if verified_pairs is not None else set()
    mapped_models = {m for _, m in verified_pairs} if verified_pairs is not None else set()
    raw_by_scene: dict[str, list[Any]] = {}
    ranked_props_by_scene: dict[str, list[str]] = {}

    for scene in req.scenes:
        try:
            hits = search_shots(query_text=scene.description, k=120)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail="Shot search failed") from exc
        valid_hits = [shot for shot in hits if _valid_retrieval_hit(shot)]
        raw_by_scene[scene.id] = valid_hits
        seen_p: list[str] = []
        for s in valid_hits:
            if s.property_id not in forbidden_set and s.property_id not in seen_p:
                seen_p.append(s.property_id)
        ranked_props_by_scene[scene.id] = seen_p

    # Deterministic union round-robin up to top-3 properties per scene, capped at 24.
    pool: list[str] = []
    pool_set: set[str] = set()
    for rank in range(3):
        for scene in req.scenes:
            plist = ranked_props_by_scene[scene.id]
            if rank < len(plist) and plist[rank] not in pool_set and len(pool) < 24:
                pool.append(plist[rank])
                pool_set.add(plist[rank])

    prop_cache: dict[str, tuple[dict[str, Any] | None, list[dict[str, str]]]] = {}
    logi_cache: dict[str, tuple[dict[str, Any] | None, list[dict[str, str]]]] = {}

    scenes_out: list[dict[str, Any]] = []
    solver_candidates: list[dict[str, Any]] = []

    for scene in req.scenes:
        scene_cands: list[dict[str, Any]] = []
        for shot in raw_by_scene[scene.id]:
            pid = shot.property_id
            if pid not in pool_set:
                continue
            if pid not in prop_cache:
                prop_cache[pid] = _lookup_property(pid)
            if pid not in logi_cache:
                logi_cache[pid] = _lookup_logistics(pid, req.trucks, req.cars)
            prop_data, prop_warn = prop_cache[pid]
            logi_data, logi_warn = logi_cache[pid]

            warnings = [*prop_warn, *logi_warn]
            if shot.measure_on_site or shot.room_area_m2 is None or shot.ceiling_m is None or shot.depth_m is None:
                warnings.append({"source": "matterport", "field": "geometry", "status": "unknown", "message": "Room dimensions unverified; measure on site"})

            # Eligibility means no explicit requested constraint is contradicted.
            # Unknown evidence remains visible for creative scouting, never certified.
            eligible = True
            pair = (pid, shot.model_id)
            if mode == 'live':
                if verified_pairs is None:
                    join_status, join_message = 'unknown', 'Private CoStar property-model mapping unavailable; association unconfirmed'
                elif pair in verified_pairs:
                    join_status, join_message = 'matched', 'Exact CoStar property_id/model_id join confirmed; location grouping uses this property identity'
                elif pid in mapped_properties or shot.model_id in mapped_models:
                    join_status, join_message = 'conflict', 'Property/model IDs conflict with the supplied CoStar mapping; candidate excluded'
                    eligible = False
                else:
                    join_status, join_message = 'unknown', 'Property/model pair is absent from the supplied mapping; association unconfirmed'
                warnings.append({'source': 'costar', 'field': 'property_id/model_id',
                                 'status': join_status, 'message': join_message})
            if req.require_available:
                avail_ok = (
                    prop_data is not None
                    and prop_data.get("available") is True
                    and str(prop_data.get("availability_status", "")).lower() == "available"
                )
                if not avail_ok:
                    eligible = False
            if (req.trucks + req.cars > 0 and logi_data is not None
                    and logi_data.get("enough_parking") is False):
                eligible = False

            scene_cands.append({
                "shot": shot.model_dump(),
                "property": prop_data,
                "logistics": logi_data,
                "warnings": warnings,
                "eligible": eligible,
            })
            if eligible:
                solver_candidates.append({
                    "scene_id": scene.id,
                    "property_id": pid,
                    "shot_id": shot.shot_id,
                    "score": float(shot.score),
                })
        scenes_out.append({
            "id": scene.id,
            "heading": scene.heading,
            "description": scene.description,
            "candidates": scene_cands,
        })

    solved = solve_plans(
        scene_ids=[s.id for s in req.scenes],
        candidates=solver_candidates,
        max_locations=req.max_locations,
        forbidden_property_ids=req.forbidden_property_ids,
    )
    return {
        "mode": mode,
        "scenes": scenes_out,
        "plans": solved["plans"],
        "evaluated_subsets": solved["evaluated_subsets"],
        "optimal_within_pool": solved["optimal_within_pool"],
        "pool_properties": pool,
        "pool_note": "Plans consider at most the first three retrieved properties per scene, up to 24 total; excluded evidence may leave scenes uncovered. Company moves assumes one visit per selected property.",
    }


@router.post("/api/production/brainstorm")
def post_production_brainstorm(req: BrainstormRequest) -> dict[str, Any]:
    try:
        from agent.models import get_provider  # type: ignore

        provider = get_provider()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Configured model provider unavailable") from exc
    if provider is None or not provider.configured():
        raise HTTPException(status_code=503, detail="Configured model provider unavailable")

    instructions = (
        "You are a film director assistant proposing an alternative 2D screen-space blocking rehearsal. "
        "Respect the user's instruction and scene context while offering a genuinely different, plausible "
        "staging and camera-blocking alternative (different actor trajectories, poses, pacing, or dialogue). "
        "Keep coordinates normalized in [0, 1], actors <= 3, and preserve actor IDs when modifying existing actors."
    )
    user_payload = {
        "instruction": req.instruction,
        "heading": req.heading,
        "description": req.description,
        "current_shot": req.shot.model_dump(),
    }
    try:
        raw_out = provider.structured(instructions, json.dumps(user_payload), BrainstormProposal)
        # Provider objects can be mutated or model_construct'ed. Revalidate a
        # plain nested payload even when the provider returns our own model type.
        proposal = BrainstormProposal.model_validate(
            raw_out.model_dump() if hasattr(raw_out, "model_dump") else raw_out)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Model provider returned invalid brainstorm proposal") from exc

    return proposal.model_dump()
