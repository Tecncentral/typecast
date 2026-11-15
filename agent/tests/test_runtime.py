"""Offline runtime regression checks."""
import os
for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "LANGSMITH_API_KEY"):
    os.environ[name] = ""
os.environ.update(TYPECAST_USE_MOCKS="1", TYPECAST_ENABLE_MODEL_PARSE="0", TYPECAST_ENABLE_VISION_RERANK="0", LANGSMITH_TRACING="false", TYPECAST_ENGINE="fixed")
import threading
import pytest
from agent import runtime, state
from agent.interfaces import Requirements
from contracts.schemas import Event, ScoutResponse

@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "CACHE_ROOT", tmp_path)
    monkeypatch.setattr(runtime.parse, "parse_scene", lambda scene, **kw: Requirements(scene=scene))
    for name, value in {"TYPECAST_USE_MOCKS": "1", "TYPECAST_ENGINE": "fixed", "TYPECAST_ENABLE_MODEL_PARSE": "0", "TYPECAST_ENABLE_VISION_RERANK": "0", "LANGSMITH_TRACING": "false"}.items():
        monkeypatch.setenv(name, value)
    state._memory.clear()
    state._expires.clear()
    yield
    state._memory.clear()
    state._expires.clear()

def test_metadata_and_working_memory(tmp_path):
    response = runtime.run_scout(runtime.create_context("runtime-test"), "open room")
    assert response.engine == "fixed" and response.source_mode == "mock"
    assert response.events[0].ts < response.events[-1].ts < response.timings["total_ms"] / 1000
    assert {p.name for p in (tmp_path / "threads/runtime-test").iterdir()} == {"requirements.json", "candidates.json", "shortlist.json", "skeptic.md"}
    assert state.load("runtime-test", "req").scene == "open room"

@pytest.mark.parametrize("thread_id", ["../escape", "ABCD", "abc", "a" * 41, "safe/../unsafe"])
def test_ids_reject_path_tricks(thread_id):
    with pytest.raises(ValueError):
        state.save(thread_id, "requirements", {})

def test_expired_thread():
    runtime.run_scout(runtime.create_context("expired-test"), "open room")
    state._expires["expired-test"] = 0
    with pytest.raises(state.UnknownThread):
        runtime.run_refine(runtime.create_context("expired-test"), "more cars")

def test_deep_error_fallback(monkeypatch):
    monkeypatch.setenv("TYPECAST_ENGINE", "deep")
    def fail(ctx, req):
        raise RuntimeError("private provider details")
    monkeypatch.setattr(runtime.deep, "run_deep", fail)
    response = runtime.run_scout(runtime.create_context("fallback-test"), "open room")
    assert response.engine == "fixed" and response.picks
    assert any(e.type == "fallback" and "fixed" in e.text for e in response.events)
    assert "private provider" not in response.model_dump_json()

def test_timeout_discards_late_writes_and_events(monkeypatch):
    monkeypatch.setenv("TYPECAST_ENGINE", "deep")
    monkeypatch.setattr(runtime, "DEEP_TIMEOUT_SECONDS", 0.01)
    release, finished = threading.Event(), threading.Event()
    events = []
    def late(ctx, req):
        release.wait(1)
        state.save(ctx.thread_id, "requirements", Requirements(scene="late overwrite"))
        ctx.event(Event(type="plan", text="late event"))
        finished.set()
        return ScoutResponse(thread_id=ctx.thread_id, picks=[])
    monkeypatch.setattr(runtime.deep, "run_deep", late)
    response = runtime.run_scout(runtime.create_context("timeout-test", events.append), "open room")
    release.set()
    assert finished.wait(1)
    assert response.engine == "fixed" and state.load("timeout-test", "requirements").scene == "open room"
    assert not any(e.text == "late event" for e in events)

def test_live_env_rejects_imported_mocks(monkeypatch):
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "0")
    with pytest.raises(runtime.SourceModeError):
        runtime.run_scout(runtime.create_context("mismatch-test"), "open room")


def test_deep_rate_limit_stops_without_fixed_fallback(monkeypatch):
    monkeypatch.setenv("TYPECAST_ENGINE", "deep")
    runtime.models.reset_rate_limit()

    def fail(ctx, req):
        runtime.models.mark_rate_limit()
        # LangGraph can wrap a failed tool; the latch still prevents retrying.
        raise RuntimeError("wrapped tool error")

    monkeypatch.setattr(runtime.deep, "run_deep", fail)
    monkeypatch.setattr(runtime.pipeline, "scout", lambda *args: pytest.fail("Rate limit retried fixed engine"))
    try:
        with pytest.raises(runtime.models.ModelRateLimitError):
            runtime.run_scout(runtime.create_context("rate-limit-test"), "open room")
    finally:
        runtime.models.reset_rate_limit()


def test_parser_rate_limit_does_not_continue_with_regex_fallback(monkeypatch):
    runtime.models.reset_rate_limit()

    def stopped(scene, **kwargs):
        runtime.models.mark_rate_limit()
        return Requirements(scene=scene)

    monkeypatch.setattr(runtime.parse, "parse_scene", stopped)
    monkeypatch.setattr(runtime.pipeline, "scout", lambda *args: pytest.fail("Rate limit continued scouting"))
    try:
        with pytest.raises(runtime.models.ModelRateLimitError):
            runtime.run_scout(runtime.create_context("parser-rate-test"), "open room")
    finally:
        runtime.models.reset_rate_limit()
