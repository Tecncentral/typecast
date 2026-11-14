"""One execution path for regular requests, streaming requests, and refinements."""
from __future__ import annotations

import importlib
import os
from queue import Empty, Queue
from threading import Event as ThreadEvent, Thread
from time import perf_counter
from uuid import uuid4

from contracts.schemas import Event, ScoutResponse
from agent import deep, parse, pipeline, state
from agent.interfaces import RunContext, timed

DEEP_TIMEOUT_SECONDS = 90.0
_ADAPTERS = {"costar": "data.costar_tools", "matterport": "index.search", "vexcel": "data.vexcel_tools"}


class SourceModeError(RuntimeError):
    pass


def source_modes() -> dict[str, str]:
    """Read actual adapter settings, rather than a cached health response."""
    modes = {}
    for name, module_name in _ADAPTERS.items():
        module = importlib.import_module(module_name)
        use_mocks = getattr(module, "USE_MOCKS", os.getenv("TYPECAST_USE_MOCKS", "1") == "1")
        modes[name] = "mock" if use_mocks else "live"
    return modes


def create_context(thread_id=None, emit=None) -> RunContext:
    thread_id = state.validate_thread_id(thread_id or uuid4().hex[:12])
    mode = "mock" if all(value == "mock" for value in source_modes().values()) else "live"
    kwargs = {"thread_id": thread_id, "source_mode": mode}
    if emit is not None:
        kwargs["emit"] = emit
    return RunContext(**kwargs)


def available_engines() -> list[str]:
    engines = ["fixed"]
    available = getattr(deep, "is_available", None)
    if available is not None and available():
        engines.append("deep")
    return engines


def _check_source_mode(ctx: RunContext) -> None:
    modes = source_modes()
    requested = "mock" if os.getenv("TYPECAST_USE_MOCKS", "1") == "1" else "live"
    if any(mode != requested for mode in modes.values()):
        raise SourceModeError("Source adapters do not match TYPECAST_USE_MOCKS; restart after changing source mode.")
    ctx.source_mode = requested


def _deep_or_fixed(ctx: RunContext, req) -> ScoutResponse:
    cancelled = ThreadEvent()
    completed: Queue = Queue(maxsize=1)

    def emit(event):
        if not cancelled.is_set():
            ctx.emit(event)

    child = RunContext(thread_id=ctx.thread_id, emit=emit, engine="deep", source_mode=ctx.source_mode,
                       started_at=ctx.started_at, cancelled=cancelled)

    def work():
        try:
            with state.stage_writes(ctx.thread_id) as pending:
                response = deep.run_deep(child, req)
            completed.put((response, pending, None))
        except Exception as error:
            completed.put((None, {}, error))

    started = perf_counter()
    Thread(target=work, name=f"typecast-deep-{ctx.thread_id}", daemon=True).start()
    try:
        response, pending, error = completed.get(timeout=DEEP_TIMEOUT_SECONDS)
        if error is not None:
            raise error
        if not isinstance(response, ScoutResponse):
            raise TypeError("Deep engine returned an invalid response")
        state.commit(ctx.thread_id, pending)
        ctx.timings.update(child.timings)
        return response
    except Empty:
        reason = "Deep engine exceeded its time limit; continuing with the fixed engine."
    except Exception:
        reason = "Deep engine failed; continuing with the fixed engine."
    finally:
        cancelled.set()
        ctx.timings["deep_attempt_ms"] = (perf_counter() - started) * 1000
    ctx.engine = "fixed"
    ctx.event(Event(type="fallback", agent="runtime", text=reason))
    return pipeline.scout(ctx, req)


def _execute(ctx: RunContext, action) -> ScoutResponse:
    emitted: list[Event] = []
    downstream = ctx.emit

    def emit(event):
        emitted.append(event)
        downstream(event)

    ctx.emit = emit
    try:
        _check_source_mode(ctx)
        response = action()
        ctx.timings["total_ms"] = (perf_counter() - ctx.started_at) * 1000
        response.thread_id = ctx.thread_id
        response.engine = ctx.engine
        response.source_mode = ctx.source_mode
        response.events = list(emitted)
        response.timings = dict(ctx.timings)
        state.save(ctx.thread_id, "shortlist", response.picks)
        skeptic = "\n\n".join(f"## Pick {pick.rank}: {pick.property.address}\n" +
                                "\n".join(f"- {note}" for note in pick.skeptic_notes)
                                for pick in response.picks)
        state.save(ctx.thread_id, "skeptic", skeptic)
        state.record_run(ctx.thread_id, engine=ctx.engine, source_mode=ctx.source_mode, timings=ctx.timings)
        return response
    except Exception:
        ctx.event(Event(type="error", agent="runtime", text="Scouting failed. Please try again."))
        raise
    finally:
        ctx.emit = downstream


def run_scout(ctx: RunContext, scene=None, example_shot_id=None) -> ScoutResponse:
    state.validate_thread_id(ctx.thread_id)
    if not scene and not example_shot_id:
        raise ValueError("give scene or example_shot_id")
    engine = os.getenv("TYPECAST_ENGINE", "fixed").lower()
    if engine not in {"fixed", "deep"}:
        raise ValueError("TYPECAST_ENGINE must be fixed or deep")
    ctx.engine = engine

    def action():
        ctx.event(Event(type="plan", agent="runtime", text=f"Starting the {ctx.engine} scouting engine."))
        if example_shot_id:
            req = {"example_shot_id": example_shot_id}
        else:
            with timed(ctx, "parse"):
                req = parse.parse_scene(scene, emit=ctx.event)
        return _deep_or_fixed(ctx, req) if ctx.engine == "deep" else pipeline.scout(ctx, req)

    return _execute(ctx, action)


def run_refine(ctx: RunContext, message: str) -> ScoutResponse:
    saved = state.get_thread(ctx.thread_id)
    ctx.engine = "fixed"

    def action():
        ctx.event(Event(type="plan", agent="runtime", text="Refining the saved candidates with the fixed engine."))
        return pipeline.refine(ctx, saved, message)

    return _execute(ctx, action)
