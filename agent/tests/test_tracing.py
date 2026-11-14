"""Offline tracing acceptance: real graph hierarchy and verified client URLs."""
import json
import socket
from threading import Event, Lock
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agent import deep, runtime, state, tracing
from agent.interfaces import Requirements
from agent.tests.test_deep import DeterministicChat


class FakeClient:
    def __init__(self, **options):
        self.options = options
        self.otel_exporter = None
        self.runs = {}
        self.created = []
        self.calls = []
        self.lock = Lock()
        self.failure = None
        self.release = Event()
        self.finished = Event()
        self.url = "https://smith.example/client-returned-real-run"

    def create_run(self, name, inputs, run_type, **fields):
        if self.failure == "slow_create":
            self.release.wait(2)
        if self.failure == "create":
            raise RuntimeError("private credential and source data")
        record = self.options["process_buffered_run_ops"]([
            dict(fields, name=name, inputs=inputs, run_type=run_type)])[0]
        with self.lock:
            self.created.append(record)
            self.runs[str(record["id"])] = record

    def update_run(self, run_id, **fields):
        if self.failure == "update":
            raise RuntimeError("private credential and source data")
        record = self.options["process_buffered_run_ops"]([fields])[0]
        with self.lock:
            self.runs[str(run_id)].update(record)

    def flush(self, timeout=None):
        self.calls.append(("flush", timeout))
        if self.failure == "flush":
            raise RuntimeError("private credential and source data")
        if self.failure == "slow_flush":
            self.release.wait(2)

    def read_run(self, run_id):
        self.calls.append(("read", str(run_id)))
        if self.failure == "read":
            raise RuntimeError("private credential and source data")
        record = self.runs[str(run_id)]
        return SimpleNamespace(id=uuid4() if self.failure == "wrong_id" else run_id,
                               trace_id=record["trace_id"], parent_run_id=record.get("parent_run_id"),
                               end_time=None if self.failure == "unfinished" else record.get("end_time"))

    def get_run_url(self, *, run, project_name):
        self.calls.append(("url", str(run.id), project_name))
        if self.failure == "url":
            raise RuntimeError("private credential and source data")
        return self.url

    def close(self, timeout=None):
        self.calls.append(("close", timeout))
        self.finished.set()


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    for key, value in {"LANGSMITH_API_KEY": "test-only-tracing-key", "LANGSMITH_TRACING": "true",
                       "TYPECAST_USE_MOCKS": "1", "TYPECAST_ENGINE": "fixed",
                       "TYPECAST_ENABLE_MODEL_PARSE": "0", "TYPECAST_ENABLE_VISION_RERANK": "0",
                       "LLM_API_KEY": "", "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.setattr(state, "CACHE_ROOT", tmp_path)
    monkeypatch.setattr(runtime.parse, "parse_scene", lambda scene, **kw: Requirements(scene=scene))
    monkeypatch.setattr(socket.socket, "connect", lambda *args, **kw: pytest.fail("unexpected network"))
    state._memory.clear()
    state._expires.clear()
    deep._approvals.clear()
    yield
    state._memory.clear()
    state._expires.clear()
    deep._approvals.clear()


@pytest.fixture
def client(monkeypatch):
    instances = []
    def build(**kwargs):
        obj = FakeClient(**kwargs)
        instances.append(obj)
        return obj
    monkeypatch.setattr(tracing, "Client", build)
    return instances


@pytest.mark.parametrize("engine", ["fixed", "deep"])
def test_both_runtime_engines_read_completed_root_before_returning_client_url(monkeypatch, client, engine):
    monkeypatch.setenv("TYPECAST_ENGINE", engine)
    model = DeterministicChat()
    monkeypatch.setattr(deep, "_chat_model", lambda **kwargs: model)
    original = deep.run_deep
    errors = []
    def invoke(*args):
        try:
            return original(*args)
        except Exception as exc:
            errors.append(repr(exc))
            raise
    monkeypatch.setattr(deep, "run_deep", invoke)
    response = runtime.run_scout(runtime.create_context(f"trace-{engine}"), "private scene must stay local")
    assert not errors
    assert response.engine == engine and response.picks
    assert response.trace_url == client[0].url
    assert len(client) == 1
    roots = [run for run in client[0].created if not run.get("parent_run_id")]
    assert len(roots) == 1 and roots[0]["name"] == "typecast.scout"
    root = roots[0]
    assert root["session_name"] == "typecast"
    assert [(c[0]) for c in client[0].calls] == ["flush", "read", "url", "close"]
    assert client[0].calls[1][1] == str(root["id"])
    finished = client[0].runs[str(root["id"])]
    assert finished["end_time"] and finished["extra"]["metadata"]["pick_count"] == len(response.picks)
    assert finished["extra"]["metadata"]["tool_count"] > 0
    assert finished["extra"]["metadata"]["tool_timings_ms"]
    assert "private scene" not in json.dumps(list(client[0].runs.values()), default=str)
    if engine == "deep":
        nested = [run for run in client[0].created if run.get("parent_run_id")]
        assert nested and any(run["run_type"] == "llm" for run in nested)
        assert any(run["run_type"] == "tool" for run in nested)
        assert all(str(run["trace_id"]) == str(root["id"]) for run in nested)
        assert any(str(run["parent_run_id"]) == str(root["id"]) for run in nested)


@pytest.mark.parametrize("key,enabled", [("", "true"), ("  ", "true"), ("test-key", "false")])
def test_missing_key_and_explicit_optout_send_nothing(monkeypatch, client, key, enabled):
    monkeypatch.setenv("LANGSMITH_API_KEY", key)
    monkeypatch.setenv("LANGSMITH_TRACING", enabled)
    response = runtime.run_scout(runtime.create_context("trace-offline"), "office")
    assert response.picks and response.trace_url is None and client == []
    assert not any(event.type == "trace" for event in response.events)


@pytest.mark.parametrize("failure", ["create", "update", "flush", "read", "url", "wrong_id", "unfinished"])
def test_tracing_failures_preserve_scouting_and_never_publish_unverified_url(monkeypatch, client, failure):
    original = tracing.Client
    def broken(**kwargs):
        obj = original(**kwargs)
        obj.failure = failure
        return obj
    monkeypatch.setattr(tracing, "Client", broken)
    response = runtime.run_scout(runtime.create_context("trace-failure"), "office")
    assert response.picks and response.engine == "fixed" and response.trace_url is None
    assert "private credential" not in response.model_dump_json()
    assert not any(event.type == "fallback" and event.agent == "runtime" for event in response.events)
    assert any(event.type == "trace" and event.agent == "langsmith" for event in response.events)
    if failure in {"read", "wrong_id", "unfinished"}:
        assert not any(call[0] == "url" for call in client[0].calls)


def test_slow_flush_is_bounded_and_cannot_set_late_response_url(monkeypatch, client):
    monkeypatch.setattr(tracing, "TRACE_VERIFY_TIMEOUT_SECONDS", 0.02)
    original = tracing.Client
    def slow(**kwargs):
        obj = original(**kwargs)
        obj.failure = "slow_flush"
        return obj
    monkeypatch.setattr(tracing, "Client", slow)
    started = perf_counter()
    response = runtime.run_scout(runtime.create_context("trace-slow"), "office")
    assert perf_counter() - started < 0.3
    assert response.picks and response.trace_url is None
    client[0].release.set()
    assert client[0].finished.wait(1)
    assert response.trace_url is None


def test_slow_start_is_bounded_and_no_trace_url_is_invented(monkeypatch, client):
    monkeypatch.setattr(tracing, "TRACE_START_TIMEOUT_SECONDS", 0.02)
    original = tracing.Client
    def slow(**kwargs):
        obj = original(**kwargs)
        obj.failure = "slow_create"
        return obj
    monkeypatch.setattr(tracing, "Client", slow)
    started = perf_counter()
    response = runtime.run_scout(runtime.create_context("trace-start"), "office")
    assert perf_counter() - started < 0.3
    assert response.picks and response.trace_url is None
    client[0].release.set()
    assert client[0].finished.wait(1)


def test_client_constructor_failure_preserves_scouting(monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("private credential and source data")
    monkeypatch.setattr(tracing, "Client", fail)
    response = runtime.run_scout(runtime.create_context("trace-constructor"), "office")
    assert response.picks and response.trace_url is None
    assert "private credential" not in response.model_dump_json()


def test_custom_project_and_refinement_are_traced(monkeypatch, client):
    monkeypatch.setenv("LANGSMITH_PROJECT", "typecast-test-project")
    runtime.run_scout(runtime.create_context("trace-refine"), "office")
    response = runtime.run_refine(runtime.create_context("trace-refine"), "need parking for 5 trucks")
    assert response.trace_url == client[1].url
    assert client[1].created[0]["name"] == "typecast.refine"
    assert client[1].created[0]["session_name"] == "typecast-test-project"


def test_payload_redaction_retains_only_aggregate_metadata():
    raw = {"id": uuid4(), "name": "safe-tool", "inputs": {"scene": "private"},
           "outputs": {"property": "licensed source"}, "error": "credential-secret",
           "events": [{"text": "source record"}], "serialized": {"prompt": "private"},
           "attachments": {"frame": "licensed image"},
           "extra": {"invocation_params": {"key": "secret"}, "metadata": {
               "engine": "deep", "source_mode": "live", "operation": "scout", "pick_count": 3,
               "scene": "private", "source": "licensed", "elapsed_ms": float("inf")}}}
    clean = tracing._safe_runs([raw])[0]
    assert clean["inputs"] == clean["outputs"] == {}
    assert clean["extra"] == {"metadata": {"engine": "deep", "source_mode": "live", "operation": "scout", "pick_count": 3}}
    assert not any(word in json.dumps(clean, default=str) for word in ("private", "licensed", "secret"))
