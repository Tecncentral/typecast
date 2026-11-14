"""Prove early SSE delivery, cached refinement and local-only approval on mocks."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from threading import Event
from time import perf_counter
from unittest.mock import patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.eval.harness import mock_app

SCENE = ("INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling. "
         "Parking for 3 trucks and 30 crew cars.")


@dataclass
class StreamEvent:
    name: str
    data: dict
    arrived_ms: float


async def _stream(app, entered: Event, release: Event, completed: Event):
    """Capture real ASGI send calls; HTTPX/TestClient buffers complete SSE bodies."""
    queue = asyncio.Queue()
    request_received = False
    started = perf_counter()

    async def receive():
        nonlocal request_received
        if not request_received:
            request_received = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Event().wait()

    async def send(message):
        await queue.put((dict(message), (perf_counter() - started) * 1000))

    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "http_version": "1.1", "method": "GET", "scheme": "http",
             "path": "/scout/stream", "raw_path": b"/scout/stream", "root_path": "",
             "query_string": urlencode({"scene": SCENE}).encode(), "headers": [],
             "server": ("testserver", 80), "client": ("in-process", 1)}
    task = asyncio.create_task(app(scope, receive, send))
    events, pending = [], ""
    tool_pending_at_first_event = False
    try:
        assert await asyncio.to_thread(entered.wait, 5), "Scout never entered the instrumented search call"
        while True:
            message, arrived_ms = await asyncio.wait_for(queue.get(), 10)
            if message["type"] == "http.response.start":
                assert message["status"] == 200, f"SSE HTTP {message['status']}"
                continue
            if message["type"] != "http.response.body":
                continue
            pending += message.get("body", b"").decode("utf-8")
            while "\n\n" in pending:
                block, pending = pending.split("\n\n", 1)
                fields = {}
                for line in block.splitlines():
                    key, separator, value = line.partition(":")
                    if separator:
                        fields[key] = value.lstrip()
                if "event" not in fields:
                    continue
                event = StreamEvent(fields["event"], json.loads(fields["data"]), arrived_ms)
                events.append(event)
                if len(events) == 1:
                    assert event.name == "agent", "Result arrived before any progress event"
                    tool_pending_at_first_event = not completed.is_set() and not release.is_set()
                    assert tool_pending_at_first_event, "First progress was buffered until search completed"
                    release.set()
            if not message.get("more_body", False):
                break
        await asyncio.wait_for(task, 10)
        assert not pending.strip(), "Truncated SSE frame"
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert events and events[-1].name == "result", "Stream ended without a result"
    assert not any(event.name == "error" for event in events), "Stream returned an error"
    assert events[0].arrived_ms < events[-1].arrived_ms, "First event did not arrive before result"
    return events, tool_pending_at_first_event


def run_e2e() -> dict:
    with mock_app() as app:
        from fastapi.testclient import TestClient
        from agent import pipeline, state
        from contracts.schemas import ScoutResponse

        calls = {"search_shots": 0, "search_costar": 0}
        entered, release, completed = Event(), Event(), Event()
        original_shots, original_costar = pipeline.search_shots, pipeline.search_costar

        def counted_costar(*args, **kwargs):
            calls["search_costar"] += 1
            entered.set()
            assert release.wait(5), "Early SSE delivery was not observed before the search timeout"
            result = original_costar(*args, **kwargs)
            completed.set()
            return result

        def counted_shots(*args, **kwargs):
            calls["search_shots"] += 1
            return original_shots(*args, **kwargs)

        # Patch the names the pipeline actually invokes, not just adapter modules.
        with patch.object(pipeline, "search_costar", counted_costar), patch.object(pipeline, "search_shots", counted_shots):
            events, tool_pending = asyncio.run(_stream(app, entered, release, completed))
            scout = ScoutResponse.model_validate(events[-1].data)
            assert scout.engine == "fixed" and scout.source_mode == "mock"
            assert scout.picks, "Mock scene returned no picks"
            before_refine = dict(calls)
            assert before_refine == {"search_shots": 1, "search_costar": 1}, before_refine
            with TestClient(app) as client:
                started = perf_counter()
                response = client.post("/refine", json={"thread_id": scout.thread_id, "message": "need parking for 5 trucks"})
                refine_ms = (perf_counter() - started) * 1000
                response.raise_for_status()
                refined = ScoutResponse.model_validate(response.json())
                assert refined.thread_id == scout.thread_id, "Refinement changed thread_id"
                assert calls == before_refine, f"Refinement made a fresh search: {before_refine} -> {calls}"
                assert state.load(scout.thread_id, "requirements").trucks == 5
                assert refined.picks, "Refinement returned no approvable draft candidate"
                started = perf_counter()
                approved = client.post("/approve", json={"thread_id": refined.thread_id,
                    "pick_rank": refined.picks[0].rank, "decision": "yes"})
                approve_ms = (perf_counter() - started) * 1000
                approved.raise_for_status()
                approval = approved.json()
                assert approval["sent"] is False, "Approval claimed to send a message"
                assert approval["status"] == "draft_saved"
                draft = state.CACHE_ROOT / "outbox" / f"{scout.thread_id}-{refined.picks[0].rank}.md"
                assert draft.is_file() and "No message has been sent" in draft.read_text(encoding="utf-8")
        return {"first_event_ms": events[0].arrived_ms, "result_ms": events[-1].arrived_ms,
                "refine_ms": refine_ms, "approve_ms": approve_ms, "event_count": len(events),
                "tool_pending_at_first_event": tool_pending, "thread_id": scout.thread_id,
                "refined_thread_id": refined.thread_id, "search_calls_before_refine": before_refine,
                "search_calls_after_refine": dict(calls), "approval": approval,
                "engine": scout.engine, "source_mode": scout.source_mode}


def main() -> int:
    result = run_e2e()
    print("Mock E2E (fixed engine; model calls, tracing and network disabled)")
    print("Stage                 elapsed ms")
    for title, key in (("First SSE event", "first_event_ms"), ("SSE result", "result_ms"),
                       ("Refine request", "refine_ms"), ("Approve request", "approve_ms")):
        print(f"{title:<22}{result[key]:>10.2f}")
    print(f"Search calls before/after refine: {result['search_calls_before_refine']} / {result['search_calls_after_refine']}")
    print("PASS: progress arrived while search was blocked; refine reused the thread and cached candidates; yes approval saved a draft with sent=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
