"""Payload-free LangSmith roots, verified before returning a bounded trace URL."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from math import isfinite
import os
from queue import Queue
from threading import Event as ThreadEvent, Thread
from time import perf_counter, sleep
from typing import Any

from langsmith import Client, tracing_context
from langsmith.run_trees import RunTree
from urllib3.util.retry import Retry

from agent.interfaces import RunContext
from contracts.schemas import Event

TRACE_VERIFY_TIMEOUT_SECONDS = 2.0
TRACE_START_TIMEOUT_SECONDS = 0.25
TRACE_FLUSH_TIMEOUT_SECONDS = 0.5
TRACE_REQUEST_TIMEOUT_MS = (300, 700)
_TOOL_NAMES = {"parse", "parse_scene", "search_costar", "get_property", "search_shots", "get_shot",
               "check_shot", "rerank_shots", "plan_logistics", "build_shortlist", "get_shortlist",
               "state.save.requirements", "state.save.candidates", "state.save.shortlist", "state.save.skeptic"}
_active: ContextVar[bool] = ContextVar("typecast_trace_active", default=False)


def configured() -> bool:
    """Require an application key and respect explicit tracing opt-out."""
    enabled = os.getenv("LANGSMITH_TRACING", "").strip().lower()
    return bool(os.getenv("LANGSMITH_API_KEY", "").strip()) and enabled not in {"false", "0", "no", "off"}


def _safe_metadata(metadata: dict) -> dict:
    """Allow aggregate application facts, never arbitrary graph metadata."""
    safe = {}
    for key, choices in (("engine", {"fixed", "deep"}), ("source_mode", {"mock", "live"}),
                         ("operation", {"scout", "refine"})):
        if isinstance(metadata.get(key), str) and metadata[key] in choices:
            safe[key] = metadata[key]
    for key in ("pick_count", "tool_count", "elapsed_ms"):
        value = metadata.get(key)
        if type(value) in (int, float) and isfinite(value) and value >= 0:
            safe[key] = value
    timings = metadata.get("tool_timings_ms")
    if isinstance(timings, dict):
        safe["tool_timings_ms"] = {key: value for key, value in timings.items() if key in _TOOL_NAMES
                                   and type(value) in (int, float) and isfinite(value) and value >= 0}
    return safe


def _safe_runs(runs) -> list[dict]:
    # Also remove payloads carried by prompts, events, attachments, exception
    # details and invocation parameters outside inputs/outputs.
    allowed = {"id", "name", "run_type", "start_time", "end_time", "trace_id",
               "parent_run_id", "dotted_order", "session_name", "session_id", "address"}
    cleaned = []
    for run in runs:
        record = {key: value for key, value in run.items() if key in allowed}
        record.update(inputs={}, outputs={})
        record["extra"] = {"metadata": _safe_metadata((run.get("extra") or {}).get("metadata") or {})}
        if run.get("error"):
            record["error"] = "Execution failed; details retained locally."
        cleaned.append(record)
    return cleaned


def _client() -> Client:
    # Construction is local and writes are buffered. Disable retry sleeps.
    return Client(
        api_key=os.environ["LANGSMITH_API_KEY"].strip(),
        timeout_ms=TRACE_REQUEST_TIMEOUT_MS,
        retry_config=Retry(total=0, connect=0, read=0, redirect=0, status=0,
                           respect_retry_after_header=False),
        auto_batch_tracing=True, hide_inputs=True, hide_outputs=True,
        hide_metadata=_safe_metadata,
        anonymizer=lambda value: {"error": "Execution failed; details retained locally."}
        if "error" in value else {},
        omit_traced_runtime_info=True, process_buffered_run_ops=_safe_runs,
        run_ops_buffer_size=1000, run_ops_buffer_timeout_ms=1000,
        tracing_mode="langsmith", disable_prompt_cache=True,
    )


@contextmanager
def graph_tracing():
    """Inherit the safe runtime client; disable standalone ambient tracing."""
    if _active.get() and configured():
        yield
    else:
        with tracing_context(enabled=False, parent=False):
            yield


@dataclass
class RunTrace:
    ctx: RunContext
    operation: str
    client: Any = None
    root: Any = None
    project: str = "typecast"
    trace_url: str | None = None
    error: bool = False
    pick_count: int = 0
    tool_count: int = 0

    def start(self) -> None:
        completed: Queue = Queue(maxsize=1)
        abandoned = ThreadEvent()

        def work():
            client = root = None
            handed_off = False
            try:
                client = _client()
                root = RunTree(name=f"typecast.{self.operation}", run_type="chain", inputs={},
                               project_name=self.project, client=client,
                               extra={"metadata": {"engine": self.ctx.engine,
                                     "source_mode": self.ctx.source_mode, "operation": self.operation}})
                root.post()
                if not abandoned.is_set():
                    completed.put((client, root))
                    handed_off = True
            except Exception:
                completed.put((None, None))
            finally:
                if client is not None and (abandoned.is_set() or not handed_off):
                    try:
                        if root is not None:
                            root.end(error="Tracing setup exceeded its time budget.")
                            root.patch()
                    except Exception:
                        pass
                    try:
                        client.close(timeout=0)
                    except Exception:
                        pass

        try:
            Thread(target=work, name="typecast-trace-start", daemon=True).start()
            self.client, self.root = completed.get(timeout=TRACE_START_TIMEOUT_SECONDS)
        except Exception:
            abandoned.set()

    def complete(self, response) -> None:
        self.pick_count = len(response.picks)
        self.tool_count = sum(event.type == "tool" for event in response.events)

    def _finish(self) -> str | None:
        try:
            self.root.add_metadata({"engine": self.ctx.engine, "source_mode": self.ctx.source_mode,
                                    "operation": self.operation, "pick_count": self.pick_count,
                                    "tool_count": self.tool_count,
                                    "tool_timings_ms": dict(self.ctx.timings),
                                    "elapsed_ms": (perf_counter() - self.ctx.started_at) * 1000})
            self.root.end(error="Execution failed; details retained locally." if self.error else None)
            self.root.patch()
            self.client.flush(timeout=TRACE_FLUSH_TIMEOUT_SECONDS)
            # Upload may briefly precede query visibility. The daemon wait also
            # bounds SDK internals, including synchronous flush/drain work.
            for attempt in range(3):
                try:
                    stored = self.client.read_run(self.root.id)
                    if (str(stored.id) != str(self.root.id) or stored.end_time is None
                            or str(stored.trace_id) != str(self.root.id)
                            or stored.parent_run_id is not None):
                        raise ValueError("LangSmith has not returned the completed root")
                    url = self.client.get_run_url(run=stored, project_name=self.project)
                    return url if isinstance(url, str) and url.startswith(("https://", "http://")) else None
                except Exception:
                    if attempt < 2:
                        sleep(0.05 * (attempt + 1))
        except Exception:
            pass
        finally:
            # close() can itself drain buffers: keep it on this worker too.
            try:
                self.client.close(timeout=0)
            except Exception:
                pass
        return None

    def finish(self) -> None:
        if self.root is None:
            return
        completed: Queue = Queue(maxsize=1)

        def work():
            completed.put(self._finish())

        try:
            Thread(target=work, name="typecast-trace-verify", daemon=True).start()
            self.trace_url = completed.get(timeout=TRACE_VERIFY_TIMEOUT_SECONDS)
        except Exception:
            self.trace_url = None


@contextmanager
def run_trace(ctx: RunContext, operation: str):
    """Trace a request without turning tracing failures into scouting errors."""
    trace = RunTrace(ctx, operation)
    enabled = configured()
    if enabled:
        trace.project = os.getenv("LANGSMITH_PROJECT", "").strip() or "typecast"
        trace.start()
    context = tracing_context(enabled=trace.root is not None, parent=trace.root or False,
                              client=trace.client if trace.root else None,
                              project_name=trace.project if trace.root else None)
    token = _active.set(trace.root is not None)
    try:
        with context:
            try:
                yield trace
            except BaseException:
                trace.error = True
                raise
    finally:
        _active.reset(token)
        trace.finish()
        if enabled and trace.trace_url is None:
            try:
                ctx.event(Event(type="trace", agent="langsmith",
                                text="Trace link unavailable; LangSmith verification did not complete."))
            except Exception:
                pass
