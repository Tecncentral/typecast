"""Owner 3. Fixed-order pipeline: the fallback path, and the reference for the deepagents version.

parse -> filter (CoStar) -> search shots (Matterport) -> shot fit -> logistics (Vexcel) -> skeptic -> rank.
parse_scene here is rule-based so everything runs with no model key; replace it with a structured model call.
"""
import re, uuid
from typing import Optional
from contracts.schemas import Pick, Event, ScoutResponse
from data.costar_tools import search_costar, get_property
from data.vexcel_tools import plan_logistics, enough_parking
from index.search import search_shots, check_shot, get_shot

ERAS = {"1950s": (None, 1962), "1960s": (None, 1972), "1970s": (None, 1982), "1980s": (None, 1992),
        "1990s": (None, 2002), "modern": (2005, None)}
_threads: dict[str, dict] = {}     # thread_id -> cached requirements and candidates


def parse_scene(scene: str) -> dict:
    s = scene.lower()
    req = {"scene": scene, "city": "Houston" if "houston" in s else "Los Angeles",
           "trucks": 0, "cars": 0, "year_min": None, "year_max": None,
           "focal_mm": 24.0, "frame_width_m": 6.0}
    if m := re.search(r"(\d+)\s*trucks?", s):
        req["trucks"] = int(m.group(1))
    if m := re.search(r"(\d+)\s*(?:crew\s*)?cars?", s):
        req["cars"] = int(m.group(1))
    for era, (lo, hi) in ERAS.items():
        if era in s:
            req["year_min"], req["year_max"] = lo, hi
    return req


def _skeptic(prop, fit, logi, req) -> list[str]:
    notes = [f"Noise: {n}." for n in logi.noise_flags]
    if not fit.fits:
        notes.append(f"Shot is tight: {fit.note}")
    if not enough_parking(logi, req["trucks"], req["cars"]):
        notes.append(f"Parking short: {logi.truck_spaces} truck / {logi.car_spaces} car spaces "
                     f"against {req['trucks']} / {req['cars']} needed.")
    if not prop.available:
        notes.append("Space is occupied, not listed as available.")
    return notes or ["No objection."]


def _build(req: dict, shots, events: list[Event]) -> list[Pick]:
    by_prop: dict[str, list] = {}
    for sh in shots:
        by_prop.setdefault(sh.property_id, []).append(sh)
    scored = []
    for pid, ss in by_prop.items():
        prop, best = get_property(pid), ss[0]
        fit = check_shot(best.shot_id, req["focal_mm"], req["frame_width_m"])
        logi = plan_logistics(pid, req["trucks"], req["cars"])
        notes = _skeptic(prop, fit, logi, req)
        for n in notes:
            events.append(Event(type="skeptic", agent="skeptic", text=f"{prop.address}: {n}"))
        penalty = sum(0.15 for n in notes if n != "No objection.")
        reason = (f"CoStar: {prop.type.lower()} built {prop.year_built}, "
                  f"{'available' if prop.available else 'occupied'}; "
                  f"Matterport: {best.room_area_m2:g} m2 room, {best.ceiling_m:g} m ceiling, "
                  f"{'shot fits' if fit.fits else 'shot is tight'}; "
                  f"Vexcel: {logi.truck_spaces} truck and {logi.car_spaces} car spaces, {logi.walk_m:g} m away.")
        scored.append(((best.score or 0) - penalty, prop, ss[:2], fit, logi, reason, notes))
    scored.sort(key=lambda t: -t[0])
    return [Pick(rank=i + 1, property=p, shots=ss, shot_fit=f, logistics=l, reason=r, skeptic_notes=n)
            for i, (_, p, ss, f, l, r, n) in enumerate(scored[:3])]


def scout(scene: Optional[str] = None, example_shot_id: Optional[str] = None,
          thread_id: Optional[str] = None) -> ScoutResponse:
    if not scene and not example_shot_id:
        raise ValueError("give scene or example_shot_id")
    thread_id = thread_id or uuid.uuid4().hex[:8]
    events, gave_up = [], []
    if example_shot_id:
        src = get_shot(example_shot_id)
        req = parse_scene("")
        req["scene"] = f"spaces like shot {example_shot_id}"
        events.append(Event(type="plan", agent="director", text=f"Find vacant spaces that look like {example_shot_id}."))
        props = search_costar(city=req["city"])
        shots = search_shots(query_shot_id=src.shot_id, property_ids=[p.property_id for p in props])
    else:
        req = parse_scene(scene)
        events.append(Event(type="plan", agent="director",
                            text="Parse scene, filter buildings, search shots, check fit, plan crew, challenge, rank."))
        events.append(Event(type="subagent_start", agent="market_scout", text="Filtering CoStar by city, era and availability."))
        props = search_costar(city=req["city"], year_min=req["year_min"], year_max=req["year_max"])
        if len(props) < 3 and (req["year_min"] or req["year_max"]):
            gave_up.append("era")
            events.append(Event(type="relaxed", agent="director", text="Fewer than three buildings fit the era; dropped the era filter."))
            props = search_costar(city=req["city"])
        events.append(Event(type="subagent_result", agent="market_scout", text=f"{len(props)} candidate buildings."))
        events.append(Event(type="subagent_start", agent="interior_scout", text="Searching camera views inside the scans."))
        shots = search_shots(query_text=req["scene"], property_ids=[p.property_id for p in props])
    events.append(Event(type="subagent_result", agent="interior_scout", text=f"{len(shots)} matching views."))
    events.append(Event(type="subagent_start", agent="logistics_scout", text="Checking crew parking and noise from the aerial view."))
    picks = _build(req, shots, events)
    events.append(Event(type="final", agent="director", text=f"{len(picks)} picks."))
    _threads[thread_id] = {"req": req, "shots": shots}
    return ScoutResponse(thread_id=thread_id, picks=picks, gave_up=gave_up, events=events)


def refine(thread_id: str, message: str) -> ScoutResponse:
    """Re-rank cached candidates with updated requirements; no fresh search."""
    state = _threads[thread_id]
    upd = parse_scene(message)
    for k in ("trucks", "cars"):
        if upd[k]:
            state["req"][k] = upd[k]
    events = [Event(type="plan", agent="director", text=f"Re-ranking cached candidates for: {message}")]
    picks = _build(state["req"], state["shots"], events)
    return ScoutResponse(thread_id=thread_id, picks=picks, events=events)
