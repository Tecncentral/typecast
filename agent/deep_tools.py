"""Run-scoped Deep Agents tools over the fixed engine's source adapters."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from threading import RLock
from time import monotonic
from typing import Any, Callable

from langchain_core.tools import StructuredTool

from agent import pipeline
from agent.interfaces import Requirements, RunContext, timed
from contracts.schemas import Event, Pick, Property, Shot


@dataclass
class ToolSession:
    ctx: RunContext
    req: Requirements
    example_shot_id: str | None = None
    properties: dict[str, Property] = field(default_factory=dict)
    shots: list[Shot] = field(default_factory=list)
    picks: list[Pick] = field(default_factory=list)
    gave_up: list[str] = field(default_factory=list)
    calls: set[str] = field(default_factory=set)
    failures: list[str] = field(default_factory=list)
    deadline: float = field(default_factory=lambda: monotonic() + 90.0)
    lock: RLock = field(default_factory=RLock)

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
        records = session.call("search_costar", pipeline.search_costar,
                               city=session.req.city, available_only=False)
        with session.lock:
            session.properties = {p.property_id: p for p in records}
        return json.dumps([p.model_dump(mode="json") for p in records])

    def get_property(property_id: str) -> dict[str, Any]:
        """Fetch a CoStar property already present in search_costar; never invent property records."""
        def get():
            if property_id not in session.properties:
                raise ValueError("Property is absent from the retrieved city pool")
            prop = pipeline.get_property(property_id)
            with session.lock:
                session.properties[property_id] = prop
            return prop.model_dump(mode="json")
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
            return json.dumps([s.model_dump(mode="json") for s in shots])
        return session.call("search_shots", search)

    def rerank_shots() -> str:
        """Rerank retrieved Matterport views with the same permission-gated visual reranker as the fixed engine."""
        def rank():
            if "search_shots" not in session.calls:
                raise ValueError("Search views before reranking")
            session.shots = pipeline._rerank(session.ctx, session.req, session.shots)
            return json.dumps([s.model_dump(mode="json") for s in session.shots])
        return session.call("deep.rerank_shots", rank)

    def check_shot(shot_id: str) -> dict[str, Any]:
        """Check a retrieved view's lens/depth/ceiling fit, preserving unknown and estimated geometry."""
        def check():
            shot = next((s for s in session.shots if s.shot_id == shot_id), None)
            if shot is None:
                raise ValueError("View is absent from retrieved candidates")
            return pipeline._fit(session.ctx, session.req, shot).model_dump(mode="json")
        return session.call("deep.check_shot", check)

    def plan_logistics(property_id: str) -> dict[str, Any]:
        """Read Vexcel parking, walk distance and noise for a retrieved candidate using requested truck/car counts."""
        def plan():
            if property_id not in {s.property_id for s in session.shots}:
                raise ValueError("Property has no retrieved Matterport view")
            return pipeline.plan_logistics(property_id, session.req.trucks, session.req.cars).model_dump(mode="json")
        return session.call("plan_logistics", plan)

    def build_shortlist() -> dict[str, Any]:
        """Build the authoritative shortlist with fixed-engine geometry, objections, evidence, relaxation and ranking rules."""
        def build():
            required = {"search_costar", "search_shots", "deep.rerank_shots"}
            if not required.issubset(session.calls):
                raise ValueError("Complete market and interior retrieval before building the shortlist")
            if session.properties and "get_property" not in session.calls:
                raise ValueError("Inspect a source property before building the shortlist")
            if session.shots and "deep.check_shot" not in session.calls:
                raise ValueError("Inspect a representative shot before building the shortlist")
            if session.shots and "plan_logistics" not in session.calls:
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
            candidates = pipeline._evaluate(ctx, session.req, session.shots, session.properties)
            if errors:
                raise RuntimeError("A required candidate source record is unavailable")
            session.picks, session.gave_up = pipeline._rank(ctx, session.req, candidates)
            return {"picks": [p.model_dump(mode="json") for p in session.picks], "gave_up": session.gave_up}
        return session.call("build_shortlist", build)

    def get_shortlist() -> dict[str, Any]:
        """Read the authoritative shortlist and evidence without changing records, rankings or constraints."""
        def read():
            if "build_shortlist" not in session.calls:
                raise ValueError("Build the shortlist before asking the skeptic")
            return {"picks": [p.model_dump(mode="json") for p in session.picks], "gave_up": session.gave_up}
        return session.call("get_shortlist", read)

    functions = [search_costar, get_property, search_shots, rerank_shots, check_shot,
                 plan_logistics, build_shortlist, get_shortlist]
    return {fn.__name__: StructuredTool.from_function(fn) for fn in functions}
