"""Run-scoped Deep Agents tools over the fixed engine's source adapters."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import json
from threading import RLock
from time import monotonic
from typing import Any, Callable

from langchain_core.tools import StructuredTool

from agent import pipeline
from agent.interfaces import Requirements, RunContext, timed
from contracts.schemas import Event, Logistics, Pick, Property, Shot

SUMMARY_BYTES = 2048


def _brief(value: str, limit: int = 140) -> str:
    return value if len(value) <= limit else value[:limit - 1] + "…"


def _summary(name: str, rows: list[dict[str, Any]], **metadata) -> str:
    """Bound model-visible records; authoritative source objects stay in ToolSession."""
    result = {name: [], "count": len(rows), "omitted": len(rows), **metadata}
    for row in rows:
        result[name].append(row)
        result["omitted"] -= 1
        if len(json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode()) > SUMMARY_BYTES:
            result[name].pop()
            result["omitted"] += 1
            break
    return json.dumps(result, separators=(",", ":"), ensure_ascii=False)


def _property_summary(prop: Property) -> dict[str, Any]:
    result = {"property_id": prop.property_id, "city": _brief(prop.city, 70), "type": _brief(prop.type),
            "year_built": prop.year_built, "available": prop.available}
    if prop.availability_status is not None:
        result["availability_status"] = prop.availability_status
    return result


def _shot_summary(shot: Shot) -> dict[str, Any]:
    return {"shot_id": shot.shot_id, "property_id": shot.property_id,
            "area_m2": shot.room_area_m2, "ceiling_m": shot.ceiling_m,
            "depth_m": shot.depth_m, "estimated": shot.measure_on_site, "score": shot.score}


def _logistics_summary(logi: Logistics) -> dict[str, Any]:
    result = {"property_id": logi.property_id, "truck_spaces": logi.truck_spaces,
            "car_spaces": logi.car_spaces, "walk_m": logi.walk_m,
            "noise_flags": [_brief(flag) for flag in logi.noise_flags[:4]],
            "noise_count": len(logi.noise_flags),
            "estimated": logi.estimated}
    result.update({key: getattr(logi, key) for key in ("parking_status", "walk_status", "noise_status")
                   if getattr(logi, key) is not None})
    return result


@dataclass
class ToolSession:
    ctx: RunContext
    req: Requirements
    example_shot_id: str | None = None
    properties: dict[str, Property] = field(default_factory=dict)
    shots: list[Shot] = field(default_factory=list)
    logistics: dict[str, Logistics] = field(default_factory=dict)
    missing_logistics: set[str] = field(default_factory=set)
    picks: list[Pick] = field(default_factory=list)
    gave_up: list[str] = field(default_factory=list)
    calls: set[str] = field(default_factory=set)
    failures: list[str] = field(default_factory=list)
    deadline: float = field(default_factory=lambda: monotonic() + 90.0)
    lock: RLock = field(default_factory=RLock)
    production_plan: dict[str, Any] | None = None

    def check_deadline(self) -> None:
        cancelled = getattr(self.ctx, "cancelled", None)
        if (cancelled is not None and cancelled.is_set()) or monotonic() > self.deadline:
            raise TimeoutError("Deep engine exceeded 90 seconds")

    def call(self, name: str, fn: Callable, *args, **kwargs):
        self.check_deadline()
        try:
            with timed(self.ctx, name):
                result = fn(*args, **kwargs)
            self.check_deadline()
            with self.lock:
                self.calls.add(name)
            return result
        except Exception as exc:
            with self.lock:
                self.failures.append(name)
            self.ctx.event(Event(type="error", agent=name,
                                 text=f"{name} failed ({type(exc).__name__}); deep scouting cannot continue."))
            raise


def make_tools(session: ToolSession) -> dict[str, StructuredTool]:
    """Build typed tools whose records always come from the shared adapters."""
    def search_costar() -> str:
        """Load the requested city's broad CoStar pool, including occupied buildings for labelled alternatives."""
        records = session.call("search_costar", pipeline.market_properties, session.ctx, session.req.city)
        with session.lock:
            session.properties = {p.property_id: p for p in records}
        return _summary("properties", [_property_summary(p) for p in records])

    def get_property(property_id: str) -> str:
        """Fetch a CoStar property already present in search_costar; never invent property records."""
        def get():
            if property_id not in session.properties:
                raise ValueError("Property is absent from the retrieved city pool")
            prop = pipeline.get_property(property_id)
            with session.lock:
                session.properties[property_id] = prop
            return _summary("properties", [_property_summary(prop)])
        return session.call("get_property", get)

    def search_shots() -> str:
        """Search Matterport views inside the retrieved CoStar pool using this request or its example view."""
        def search():
            if "search_costar" not in session.calls:
                raise ValueError("Run market_scout before interior_scout")
            query = ({"query_shot_id": session.example_shot_id} if session.example_shot_id
                     else {"query_text": session.req.scene})
            shots = pipeline.search_shots(property_ids=list(session.properties), **query)
            with session.lock:
                session.shots = list(shots)
            return _summary("shots", [_shot_summary(s) for s in shots])
        return session.call("search_shots", search)

    def rerank_shots() -> str:
        """Rerank retrieved Matterport views with the same permission-gated visual reranker as the fixed engine."""
        def rank():
            if "search_shots" not in session.calls:
                raise ValueError("Search views before reranking")
            session.shots = pipeline._rerank(session.ctx, session.req, session.shots)
            return _summary("shots", [_shot_summary(s) for s in session.shots])
        return session.call("deep.rerank_shots", rank)

    def check_shot(shot_id: str) -> str:
        """Check a retrieved view's lens/depth/ceiling fit, preserving unknown and estimated geometry."""
        def check():
            shot = next((s for s in session.shots if s.shot_id == shot_id), None)
            if shot is None:
                raise ValueError("View is absent from retrieved candidates")
            fit = pipeline._fit(session.ctx, session.req, shot)
            return _summary("fits", [{"shot_id": shot_id, **fit.model_dump(mode="json"),
                                       "note": _brief(fit.note, 400)}])
        return session.call("deep.check_shot", check)

    def plan_logistics(property_id: str | None = None) -> str:
        """Cache Vexcel logistics for market candidates, independently of interiors. Omit id to check the complete pool."""
        def plan():
            if "search_costar" not in session.calls:
                raise ValueError("Run market_scout before logistics_scout")
            ids = [property_id] if property_id is not None else list(session.properties)
            if any(pid not in session.properties for pid in ids):
                raise ValueError("Property is absent from the retrieved city pool")

            def load(pid):
                session.check_deadline()
                with session.lock:
                    if pid in session.logistics or pid in session.missing_logistics:
                        return
                try:
                    logi = pipeline.plan_logistics(pid, session.req.trucks, session.req.cars)
                except (KeyError, FileNotFoundError):
                    with session.lock:
                        session.missing_logistics.add(pid)
                    return
                if logi.property_id != pid:
                    raise ValueError("Logistics do not match the requested source property")
                with session.lock:
                    session.logistics[pid] = logi

            # Bound source fan-out, inherit safe runtime tracing, and avoid another
            # model turn when the compact market summary omits a large source pool.
            if ids:
                with ThreadPoolExecutor(max_workers=min(8, len(ids))) as executor:
                    futures = [executor.submit(copy_context().run, load, pid) for pid in ids]
                    for future in futures:
                        future.result()
            return _summary("logistics", [_logistics_summary(session.logistics[pid])
                            for pid in ids if pid in session.logistics],
                            missing_count=sum(pid in session.missing_logistics for pid in ids),
                            required_trucks=session.req.trucks, required_cars=session.req.cars)
        return session.call("plan_logistics", plan)

    def shortlist_summary() -> str:
        # Three compact rows retain every pick's key CoStar/Matterport/Vexcel facts.
        # Full evidence and objections remain authoritative in session.picks/files.
        rows = []
        for pick in session.picks:
            logistics = _logistics_summary(pick.logistics)
            logistics.pop("property_id")
            logistics["noise_flags"] = [_brief(flag, 50) for flag in pick.logistics.noise_flags[:1]]
            prop = _property_summary(pick.property)
            prop.pop("city")
            prop["type"] = _brief(prop["type"], 40)
            rows.append({"property": prop,
                         "shot_fit": {key: value for key, value in pick.shot_fit.model_dump(mode="json").items()
                                      if key != "note"},
                         "geometry_estimated": pick.shots[0].measure_on_site,
                         "logistics": logistics,
                         "skeptic_notes": [_brief(note, 100) for note in pick.skeptic_notes[:1]],
                         "objection_count": len(pick.skeptic_notes)})
        result = _summary("picks", rows, gave_up=session.gave_up)
        if json.loads(result)["omitted"]:
            # Never hide a shortlisted id from the director or read-only skeptic.
            for row in rows:
                row.pop("skeptic_notes")
                row["property"].pop("type")
                row["logistics"]["noise_flags"] = []
            result = _summary("picks", rows, gave_up=session.gave_up)
            if json.loads(result)["omitted"]:
                # Keep live uncertainty and every source id when richer records
                # exceed the budget; full evidence remains in private sources.
                for row in rows:
                    row["property"].pop("year_built", None)
                    for key in ("estimated", "noise_count", "noise_flags"):
                        row["logistics"].pop(key, None)
                result = _summary("picks", rows, gave_up=session.gave_up)
                if json.loads(result)["omitted"]:
                    raise ValueError("Shortlist source ids exceed the model summary budget")
        return result

    def build_shortlist() -> str:
        """Build the authoritative shortlist with fixed-engine geometry, objections, evidence, relaxation and ranking rules."""
        def build():
            required = {"search_costar", "search_shots", "deep.rerank_shots"}
            if not required.issubset(session.calls):
                raise ValueError("Complete market and interior retrieval before building the shortlist")
            if session.properties and "get_property" not in session.calls:
                raise ValueError("Inspect a source property before building the shortlist")
            if session.shots and "deep.check_shot" not in session.calls:
                raise ValueError("Inspect a representative shot before building the shortlist")
            if session.shots and not {shot.property_id for shot in session.shots}.issubset(session.logistics):
                raise ValueError("Complete logistics_scout before building the shortlist")
            # Shared evaluation deliberately rechecks all retrieved views: a model cannot
            # hide failed geometry or omit logistics by only checking attractive views.
            errors = []

            def forward(event):
                if event.type == "error":
                    errors.append(event)
                if event.type != "final":
                    session.ctx.emit(event)

            ctx = replace(session.ctx, emit=forward)
            candidates = pipeline._evaluate(ctx, session.req, session.shots, session.properties,
                                            logistics=session.logistics)
            if errors:
                raise RuntimeError("A required candidate source record is unavailable")
            session.picks, session.gave_up = pipeline._rank(ctx, session.req, candidates)
            return shortlist_summary()
        return session.call("build_shortlist", build)

    def get_shortlist() -> str:
        """Read the authoritative shortlist and evidence without changing records, rankings or constraints."""
        def read():
            if "build_shortlist" not in session.calls:
                raise ValueError("Build the shortlist before asking the skeptic")
            return shortlist_summary()
        return session.call("get_shortlist", read)

    def plan_production_shoot(**kwargs) -> str:
        """Plan 1..8 scenes with the shared bounded production solver and source evidence."""
        from index.production_integration import run_production_plan

        def plan():
            result = run_production_plan(kwargs)
            if result["mode"] != session.ctx.source_mode:
                raise ValueError("Production source mode differs from the scouting run")
            with session.lock:
                session.production_plan = result
            # Preserve every selected id and assignment; detailed candidate evidence
            # stays in the run's authoritative result rather than bloating context.
            selected = {pid for row in result["plans"] for pid in row["property_ids"]}
            warnings = [
                {"scene_id": scene["id"], "shot_id": candidate["shot"]["shot_id"],
                 "warnings": candidate["warnings"]}
                for scene in result["scenes"] for candidate in scene["candidates"]
                if candidate["shot"]["property_id"] in selected
            ]
            return json.dumps({key: result[key] for key in (
                "mode", "plans", "pool_properties", "pool_note", "evaluated_subsets",
                "optimal_within_pool") } | {
                    "evidence_note": "Candidate evidence is retained in the run; unknown and estimated facts require verification.",
                    "warning_count": sum(len(row["warnings"]) for row in warnings),
                    "warnings": warnings[:8],
                    "omitted_warning_candidates": max(0, len(warnings) - 8),
                }, separators=(",", ":"))
        return session.call("plan_production_shoot", plan)

    functions = [search_costar, get_property, search_shots, rerank_shots, check_shot,
                 plan_logistics, build_shortlist, get_shortlist]
    tools = {fn.__name__: StructuredTool.from_function(fn) for fn in functions}
    from index.production import PlanRequest
    tools["plan_production_shoot"] = StructuredTool.from_function(
        plan_production_shoot, args_schema=PlanRequest)
    return tools
