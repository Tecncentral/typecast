"""Deterministic scouting: retrieve, check evidence, challenge, relax and rank."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional
import uuid

from agent import parse, rerank, state as working_memory
from agent.interfaces import Requirements, RunContext, timed
from contracts.schemas import Evidence, Event, Logistics, Pick, Property, ScoutResponse, Shot, ShotFit
from data.costar_tools import get_property, search_costar
from data.vexcel_tools import enough_parking, plan_logistics
from index.search import check_shot, get_shot, search_shots
from index.geometry import needed_depth_m

MAX_PARKING_WALK_M = 150.0
# Compatibility for scripts that previously kept their state in this module.
_threads: dict[str, dict] = {}


def parse_scene(scene: str, *, emit=None) -> Requirements:
    """Compatibility entry point; the parser owns extraction and fallback."""
    return parse.parse_scene(scene, emit=emit) if emit is not None else parse.parse_scene(scene)


def _recording_context(ctx: RunContext, events: list[Event]) -> RunContext:
    ctx.engine = "fixed"

    def emit(event: Event) -> None:
        events.append(event)
        ctx.emit(event)

    return replace(ctx, emit=emit)


def _call(ctx: RunContext, name: str, function, *args, **kwargs):
    with timed(ctx, name):
        return function(*args, **kwargs)


def _event(ctx: RunContext, kind: str, text: str, agent: str = "director") -> None:
    ctx.event(Event(type=kind, agent=agent, text=text))


def _parsed(ctx: RunContext, scene: str) -> Requirements:
    req = _call(ctx, "parse_scene", parse_scene, scene, emit=ctx.event)
    return req if isinstance(req, Requirements) else Requirements.model_validate(req)


def _parse_note(ctx: RunContext, req: Requirements) -> None:
    if req.parse_note or not req.parsed_with_model:
        _event(ctx, "fallback", req.parse_note or "Scene parsed without a model.")


def _number(value, unit: str = "") -> str:
    return "unknown" if value is None else f"{value:g}{unit}"


def _availability(prop: Property) -> str:
    if prop.availability_status is not None:
        return {"available": "available", "not_available": "not listed as available",
                "unknown": "unknown"}[prop.availability_status]
    return "available" if prop.available else "occupied"


def _noise(logi: Logistics) -> str:
    if logi.noise_flags:
        return "; ".join(logi.noise_flags)
    return "unknown; nearby sources not verified" if logi.noise_status == "unknown" else "no noise flags reported"


def _fit(ctx: RunContext, req: Requirements, shot: Shot) -> ShotFit:
    raw = _call(ctx, "check_shot", check_shot, shot.shot_id, req.focal_mm, req.frame_width_m)
    data = raw.model_dump()
    # Missing geometry is never upgraded by an adapter's optimistic result.
    if shot.depth_m is None or shot.ceiling_m is None or raw.have_depth_m is None or raw.ceiling_m is None:
        data.update(fits=False, status="unknown", have_depth_m=shot.depth_m,
                    ceiling_m=shot.ceiling_m, note="Room depth or ceiling is unknown; measure on site.")
    elif shot.measure_on_site:
        data.update(fits=False, status="tight", note=f"{raw.note} Geometry estimated; measure on site.")
    elif req.min_ceiling_m is not None and shot.ceiling_m < req.min_ceiling_m:
        data.update(fits=False, status="tight",
                    note=f"Ceiling {shot.ceiling_m:g} m is below the required {req.min_ceiling_m:g} m.")
    return ShotFit.model_validate(data)


def _failed_fit(req: Requirements, fit: ShotFit) -> bool:
    # Unlike provisional/unknown fits, these views are known to fail the shot.
    return ((fit.have_depth_m is not None and fit.have_depth_m < needed_depth_m(req.focal_mm, req.frame_width_m))
            or (req.min_ceiling_m is not None and fit.ceiling_m is not None
                and fit.ceiling_m < req.min_ceiling_m))


def _evidence(prop: Property, shot: Shot, fit: ShotFit, logi: Logistics) -> list[Evidence]:
    geometry = "estimated" if shot.measure_on_site else "measured"
    aerial = "estimated" if logi.estimated else "measured"

    def item(source, claim, value, status="measured"):
        return Evidence(source=source, claim=claim, status="unknown" if value is None else status)

    evidence = [
        item("costar", f"Property type: {prop.type}.", prop.type or None),
        item("costar", f"Year built: {_number(prop.year_built)}.", prop.year_built),
        item("costar", f"Availability: {_availability(prop)}. {prop.availability_reason or ''}".strip(),
             None if prop.availability_status == "unknown" else prop.available),
        item("matterport", f"Room area: {_number(shot.room_area_m2, ' m2')}.", shot.room_area_m2, geometry),
        item("matterport", f"Ceiling: {_number(shot.ceiling_m, ' m')}.", shot.ceiling_m, geometry),
        item("matterport", f"Room depth: {_number(shot.depth_m, ' m')}.", shot.depth_m, geometry),
        item("matterport", f"Shot fit: {fit.status}; {fit.note}",
             None if fit.status == "unknown" else fit.status, geometry),
        item("vexcel", f"Truck spaces: {_number(logi.truck_spaces)}.", logi.truck_spaces, logi.parking_status or aerial),
        item("vexcel", f"Car spaces: {_number(logi.car_spaces)}.", logi.car_spaces, logi.parking_status or aerial),
        item("vexcel", f"Parking walk: {_number(logi.walk_m, ' m')}.", logi.walk_m, logi.walk_status or aerial),
        item("vexcel", f"Noise: {_noise(logi)}.", logi.noise_flags, logi.noise_status or aerial),
    ]
    evidence.extend(item("costar", f"Recorded parking flag {name}: {str(value).lower()}.", value)
                    for name, value in sorted(prop.parking_flags.items()))
    evidence.extend(logi.source_evidence)
    return list({(e.source, e.claim, e.status): e for e in evidence}.values())


@dataclass
class _Candidate:
    prop: Property
    shots: list[Shot]
    fit: ShotFit
    logi: Logistics
    notes: list[str]
    blockers: int
    failed: bool


def _skeptic(prop: Property, fit: ShotFit, logi: Logistics, req: Requirements) -> tuple[list[str], int]:
    notes, blockers = [], 0
    if fit.status == "unknown":
        notes.append("Shot fit unknown: measure on site before booking.")
        blockers += 1
    elif not fit.fits:
        notes.append(f"Shot is tight: {fit.note}")
        blockers += 1
    parking_unknown = (logi.parking_status == "unknown" or
                       (req.trucks > 0 and logi.truck_spaces is None) or
                       (req.cars > 0 and logi.car_spaces is None))
    if parking_unknown and (req.trucks or req.cars):
        notes.append("Parking capacity unknown; verify usable spaces and permission on site.")
        blockers += 1
    elif (req.trucks or req.cars) and not enough_parking(logi, req.trucks, req.cars):
        notes.append(f"Parking short: {_number(logi.truck_spaces)} truck / {_number(logi.car_spaces)} car spaces "
                     f"against {req.trucks} / {req.cars} needed.")
        blockers += 1
    if not prop.available:
        notes.append("Availability is unknown; confirm listing status before booking."
                     if prop.availability_status == "unknown" else
                     "Space is not listed as available." if prop.availability_status == "not_available" else
                     "Space is occupied, not listed as available.")
        blockers += 1
    if logi.walk_m is None:
        notes.append("Parking walk distance is unknown; measure on site.")
        if req.trucks or req.cars:
            blockers += 1
    notes.extend(f"Noise: {noise}." for noise in logi.noise_flags)
    if logi.noise_status == "unknown":
        notes.append("Nearby noise sources are unverified; no sound-level claim is possible.")
    notes.extend(logi.source_notes)
    return notes, blockers


def _evaluate(ctx: RunContext, req: Requirements, shots: list[Shot],
              properties: Optional[dict[str, Property]] = None, *,
              logistics: Optional[dict[str, Logistics]] = None) -> list[_Candidate]:
    by_property: dict[str, list[Shot]] = {}
    for shot in shots:
        by_property.setdefault(shot.property_id, []).append(shot)
    candidates = []
    for pid, views in by_property.items():
        try:
            prop = properties.get(pid) if properties is not None else None
            if prop is None:
                prop = _call(ctx, "get_property", get_property, pid)
            checked = []
            for order, view in enumerate(views):
                fit = _fit(ctx, req, view)
                failed = _failed_fit(req, fit)
                if failed:
                    _event(ctx, "skeptic", f"{prop.address}, view {view.shot_id}: rejected shot fit: {fit.note}", "skeptic")
                quality = 3 if failed else (0 if fit.fits else 2 if fit.status == "unknown" else 1)
                size_quality = (0 if req.min_area_m2 is None or
                                (view.room_area_m2 is not None and view.room_area_m2 >= req.min_area_m2)
                                else 1 if view.room_area_m2 is None else 2)
                checked.append((quality, size_quality, order, view, fit))
            checked.sort(key=lambda entry: entry[:3])
            _, _, _, best, fit = checked[0]
            selected = [best] + [v for _, _, _, v, f in checked[1:] if not _failed_fit(req, f)][:1]
            # Deep scouts collect logistics alongside interior retrieval. Reuse
            # those exact source records when joining their results; an absent
            # cache entry must not quietly trigger another source request.
            logi = (logistics[pid] if logistics is not None else
                    _call(ctx, "plan_logistics", plan_logistics, pid, req.trucks, req.cars))
            if logi.property_id != pid:
                raise ValueError("Logistics record belongs to a different property")
        except (KeyError, FileNotFoundError) as exc:
            # Required Pick fields cannot honestly represent a missing source record.
            _event(ctx, "error", f"Missing source record for {pid}; omitted candidate ({type(exc).__name__}).")
            continue
        notes, blockers = _skeptic(prop, fit, logi, req)
        for note in notes or ["No objection."]:
            _event(ctx, "skeptic", f"{prop.address}: {note}", "skeptic")
        candidates.append(_Candidate(prop, selected, fit, logi, notes, blockers, _failed_fit(req, fit)))
    return candidates


def _reason(candidate: _Candidate, blocked: bool, relaxed_distance: bool) -> str:
    prop, shot, fit, logi = candidate.prop, candidate.shots[0], candidate.fit, candidate.logi
    fit_text = "shot fits" if fit.fits else ("shot fit unknown; measure on site" if fit.status == "unknown"
                                            else "shot is tight; measure on site")
    prefix = "Blocked alternative; " if blocked else ""
    walk = _number(logi.walk_m, " m")
    if relaxed_distance and logi.walk_m is not None and logi.walk_m > MAX_PARKING_WALK_M:
        walk += " (parking distance relaxed)"
    return (f"{prefix}CoStar: {prop.type.lower() or 'type unknown'}, year built {_number(prop.year_built)}, "
            f"{_availability(prop)}; Matterport: {_number(shot.room_area_m2, ' m2')} room, "
            f"{_number(shot.ceiling_m, ' m')} ceiling, {_number(shot.depth_m, ' m')} depth, {fit_text}; "
            f"Vexcel: {_number(logi.truck_spaces)} truck and {_number(logi.car_spaces)} car spaces, walk {walk}, "
            f"noise: {_noise(logi)}.")


def _select(req: Requirements, candidates: list[_Candidate], gave_up: list[str]) -> tuple[list[Pick], int]:
    ranked = []
    for candidate in candidates:
        prop, shot, logi = candidate.prop, candidate.shots[0], candidate.logi
        if candidate.failed or prop.city.lower() != req.city.lower():
            continue
        notes, blockers = list(candidate.notes), candidate.blockers
        if "era" not in gave_up and (req.year_min is not None or req.year_max is not None):
            if prop.year_built is None:
                notes.append("Year built is unknown; the requested era is unverified.")
                blockers += 1
            elif ((req.year_min is not None and prop.year_built < req.year_min)
                  or (req.year_max is not None and prop.year_built > req.year_max)):
                continue
        if "minimum size" not in gave_up and req.min_area_m2 is not None:
            if shot.room_area_m2 is None:
                notes.append("Room area is unknown; the minimum size is unverified.")
                blockers += 1
            elif shot.room_area_m2 < req.min_area_m2:
                continue
        if logi.walk_m is not None and logi.walk_m > MAX_PARKING_WALK_M:
            if "parking distance" not in gave_up:
                continue
            notes.append(f"Parking is {logi.walk_m:g} m away; the {MAX_PARKING_WALK_M:g} m preference was relaxed.")
        notes = notes or ["No objection."]
        soft_penalty = 0.05 * len(logi.noise_flags)
        # A visual score of any magnitude cannot outrank a candidate with fewer blockers.
        ranked.append((blockers, -(shot.score or 0) + soft_penalty, candidate, notes))
    ranked.sort(key=lambda entry: entry[:2])
    viable = sum(blockers == 0 for blockers, *_ in ranked)
    picks = [Pick(rank=index + 1, property=c.prop, shots=c.shots, shot_fit=c.fit,
                  logistics=c.logi, reason=_reason(c, blockers > 0, "parking distance" in gave_up),
                  skeptic_notes=notes, evidence=_evidence(c.prop, c.shots[0], c.fit, c.logi))
             for index, (blockers, _, c, notes) in enumerate(ranked[:3])]
    return picks, viable


def _rank(ctx: RunContext, req: Requirements, candidates: list[_Candidate]) -> tuple[list[Pick], list[str]]:
    gave_up: list[str] = []
    picks, viable = _select(req, candidates, gave_up)
    relaxations = [("parking distance", True, f"Dropped the {MAX_PARKING_WALK_M:g} m parking distance preference"),
                   ("era", req.year_min is not None or req.year_max is not None, "Dropped the requested era filter"),
                   ("minimum size", req.min_area_m2 is not None, "Dropped the minimum room size filter")]
    for name, active, text in relaxations:
        if viable >= 3:
            break
        if not active:
            continue
        gave_up.append(name)
        _event(ctx, "relaxed", f"Fewer than three viable picks: {text}; shot-fit and parking-capacity failures remain visible.")
        picks, viable = _select(req, candidates, gave_up)
    # Stage-specific objections are emitted for the actual returned shortlist, too.
    for pick in picks:
        for note in pick.skeptic_notes:
            _event(ctx, "skeptic", f"Rank {pick.rank}, {pick.property.address}: {note}", "skeptic")
    blocked = sum(p.reason.startswith("Blocked alternative;") for p in picks)
    _event(ctx, "final", f"{len(picks)} picks: {len(picks) - blocked} viable and {blocked} explicitly blocked alternatives.")
    return picks, gave_up


def _persist(ctx: RunContext, req: Requirements, shots: list[Shot], state: Optional[dict] = None) -> None:
    snapshot = state if state is not None else {}
    snapshot.update(requirements=req, candidates=shots, req=req, shots=shots)
    _threads[ctx.thread_id] = snapshot
    _call(ctx, "state.save.requirements", working_memory.save, ctx.thread_id, "requirements", req)
    _call(ctx, "state.save.candidates", working_memory.save, ctx.thread_id, "candidates", shots)


def _response(ctx: RunContext, picks: list[Pick], gave_up: list[str], events: list[Event]) -> ScoutResponse:
    return ScoutResponse(thread_id=ctx.thread_id, picks=picks, gave_up=gave_up, events=events,
                         engine="fixed", source_mode=ctx.source_mode, timings=dict(ctx.timings))


def _rerank(ctx: RunContext, req: Requirements, shots: list[Shot]) -> list[Shot]:
    ranked = list(_call(ctx, "rerank_shots", rerank.rerank_shots, ctx, req, shots, k=20))
    seen = {shot.shot_id for shot in ranked}
    return ranked + [shot for shot in shots if shot.shot_id not in seen]


def scout(ctx=None, req_or_example=None, thread_id=None, **kwargs) -> ScoutResponse:
    """Run the fixed engine; retain scout(scene=...) for local scripts."""
    if not isinstance(ctx, RunContext):
        scene = kwargs.get("scene", ctx)
        example = kwargs.get("example_shot_id", req_or_example)
        ctx = RunContext(thread_id=thread_id or uuid.uuid4().hex[:8])
        req_or_example = {"example_shot_id": example} if example else scene
    elif req_or_example is None:
        req_or_example = ({"example_shot_id": kwargs["example_shot_id"]}
                          if kwargs.get("example_shot_id") else kwargs.get("scene"))
    events: list[Event] = []
    ctx = _recording_context(ctx, events)
    _event(ctx, "plan", "Fixed engine: parse requirements, retrieve views, check geometry and logistics, challenge and rank.")
    example = req_or_example.get("example_shot_id") if isinstance(req_or_example, dict) else None
    if example:
        source = _call(ctx, "get_shot", get_shot, example)
        req = Requirements(scene=f"spaces like shot {example}")
    elif isinstance(req_or_example, Requirements):
        req = req_or_example
    elif isinstance(req_or_example, dict):
        req = Requirements.model_validate(req_or_example)
    elif req_or_example:
        req = _parsed(ctx, str(req_or_example))
    else:
        raise ValueError("give scene or example_shot_id")
    if not example:
        _parse_note(ctx, req)
    _event(ctx, "subagent_start", "Loading the CoStar city pool; era, availability and size are checked before ranking.", "market_scout")
    # Keep a broad pool for transparent relaxation and later cached-only refinement.
    properties = _call(ctx, "search_costar", search_costar, city=req.city, available_only=False)
    _event(ctx, "subagent_result", f"{len(properties)} candidate buildings.", "market_scout")
    _event(ctx, "subagent_start", "Searching Matterport camera views.", "interior_scout")
    search = {"property_ids": [p.property_id for p in properties]}
    search.update({"query_shot_id": source.shot_id} if example else {"query_text": req.scene})
    shots = _call(ctx, "search_shots", search_shots, **search)
    _event(ctx, "subagent_result", f"{len(shots)} retrieved views.", "interior_scout")
    shots = _rerank(ctx, req, shots)
    _event(ctx, "subagent_start", "Checking shot geometry, Vexcel parking and noise.", "logistics_scout")
    candidates = _evaluate(ctx, req, shots, {p.property_id: p for p in properties})
    _persist(ctx, req, shots)
    picks, gave_up = _rank(ctx, req, candidates)
    return _response(ctx, picks, gave_up, events)


def refine(ctx, state, message=None) -> ScoutResponse:
    """Apply only explicit updates and rank cached views without a fresh search."""
    if not isinstance(ctx, RunContext):
        thread_id, message = ctx, state
        ctx = RunContext(thread_id=thread_id)
        state = _threads[thread_id]
    events: list[Event] = []
    ctx = _recording_context(ctx, events)
    _event(ctx, "plan", f"Fixed engine: re-rank cached candidates for: {message}")
    original = state.get("requirements", state.get("req"))
    req = original.model_copy(deep=True) if isinstance(original, Requirements) else Requirements.model_validate(original)
    update = _parsed(ctx, message)
    _parse_note(ctx, update)
    changes = {name: getattr(update, name) for name in update.explicit_fields
               if name in Requirements.model_fields and name not in {"scene", "explicit_fields", "parsed_with_model", "parse_note"}}
    changes.update(scene=f"{req.scene}\nFollow-up: {message}",
                   explicit_fields=req.explicit_fields | update.explicit_fields)
    req = Requirements.model_validate({**req.model_dump(), **changes})
    cached = state.get("candidates", state.get("shots", []))
    shots = [shot if isinstance(shot, Shot) else Shot.model_validate(shot) for shot in cached]
    shots = _rerank(ctx, req, shots)
    candidates = _evaluate(ctx, req, shots)
    _persist(ctx, req, shots, state)
    picks, gave_up = _rank(ctx, req, candidates)
    return _response(ctx, picks, gave_up, events)
