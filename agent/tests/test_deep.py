"""Offline integration with real Deep Agents graphs and a deterministic chat model."""
from __future__ import annotations

import json
from threading import Event as ThreadEvent, get_ident
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from agent import deep, pipeline, state
from agent.interfaces import Requirements, RunContext
from contracts.schemas import ScoutResponse


class DeterministicChat(BaseChatModel):
    """Actually executes the graph's tools and subagents without any provider calls."""
    bad_final: bool = False
    _steps: dict[str, int] = PrivateAttr(default_factory=dict)
    _history: list[str] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "typecast-offline-tool-chat"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        system = deep._text(messages[0].content)
        role = next((r for r in ["market_scout", "interior_scout", "logistics_scout", "skeptic"]
                     if system.startswith(f"You are {r}") or system.startswith("You are the read-only skeptic") and r == "skeptic"), "director")
        step = self._steps.get(role, 0)
        self._steps[role] = step + 1
        self._history.append(role)

        def call(name, args=None):
            return AIMessage(content="", tool_calls=[{"name": name, "args": args or {},
                              "id": f"{role}-{step}-{name}", "type": "tool_call"}])

        def result(name):
            found = [m for m in messages if isinstance(m, ToolMessage) and m.name == name]
            return json.loads(deep._text(found[-1].content))

        if role == "market_scout":
            if step == 0:
                answer = call("search_costar")
            elif step == 1 and result("search_costar"):
                answer = call("get_property", {"property_id": result("search_costar")[0]["property_id"]})
            else:
                answer = AIMessage(content=json.dumps({"properties": result("search_costar")}))
        elif role == "interior_scout":
            if step == 0:
                answer = call("search_shots")
            elif step == 1:
                answer = call("rerank_shots")
            elif step == 2 and result("search_shots"):
                answer = call("check_shot", {"shot_id": result("search_shots")[0]["shot_id"]})
            else:
                answer = AIMessage(content=json.dumps({"property_ids": list(dict.fromkeys(
                    s["property_id"] for s in result("search_shots")))}))
        elif role == "logistics_scout":
            ids = json.loads(deep._text(messages[-1].content)).get("property_ids", []) if step == 0 else []
            if ids:
                answer = AIMessage(content="", tool_calls=[{"name": "plan_logistics", "args": {"property_id": pid},
                    "id": f"logistics-{pid}", "type": "tool_call"} for pid in ids])
            else:
                answer = AIMessage(content="Checked the supplied candidate logistics.")
        elif role == "skeptic":
            if step == 0:
                answer = call("get_shortlist")
            else:
                answer = AIMessage(content=json.dumps({"reviews": [{"property_id": p["property"]["property_id"],
                    "objection": p["skeptic_notes"][0]} for p in result("get_shortlist")["picks"]]}))
        else:
            sequence = ["todo", "market_scout", "todo", "interior_scout", "todo", "logistics_scout",
                        "todo", "build_shortlist", "todo", "skeptic", "todo", "final"]
            action = sequence[step]
            if action == "todo":
                answer = call("write_todos", {"todos": [{"content": "Verify source evidence and shortlist", "status":
                                                        "completed" if step == 10 else "in_progress"}]})
            elif action == "build_shortlist":
                answer = call(action)
            elif action == "final":
                ids = [p["property"]["property_id"] for p in result("build_shortlist")["picks"]]
                answer = AIMessage(content=json.dumps({"property_ids": ["invented"] if self.bad_final else ids}))
            else:
                description = "Inspect source evidence and report results."
                if action == "logistics_scout":
                    description = next(deep._text(m.content) for m in reversed(messages)
                                       if isinstance(m, ToolMessage) and m.name == "task")
                answer = call("task", {"subagent_type": action, "description": description})
        return ChatResult(generations=[ChatGeneration(message=answer)])


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    for key in ["LLM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LANGSMITH_API_KEY"]:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("TYPECAST_ENABLE_VISION_RERANK", "0")
    monkeypatch.setenv("TYPECAST_USE_MOCKS", "1")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setattr(state, "CACHE_ROOT", tmp_path)
    state._memory.clear()
    state._expires.clear()
    deep._approvals.clear()
    yield
    state._memory.clear()
    state._expires.clear()
    deep._approvals.clear()


def fake_model(monkeypatch, **kwargs):
    model = DeterministicChat(**kwargs)
    monkeypatch.setattr(deep, "_chat_model", lambda: model)
    return model


def test_real_graph_delegates_streams_validates_and_matches_fixed(monkeypatch, tmp_path):
    model = fake_model(monkeypatch)
    emitted = []
    save_threads = []
    original_save = state.save

    def save(*args):
        save_threads.append(get_ident())
        original_save(*args)

    monkeypatch.setattr(state, "save", save)
    req = Requirements(scene="large open office", trucks=3, cars=30)
    response = deep.run_deep(RunContext("deep-test", emit=emitted.append), req)
    assert ScoutResponse.model_validate(response.model_dump()).engine == "deep"
    assert response.picks and response.events == emitted
    assert all(event.engine == "deep" for event in emitted)
    assert {"director", "market_scout", "interior_scout", "logistics_scout", "skeptic"} <= set(model._history)
    starts = [(i, e.agent) for i, e in enumerate(emitted) if e.type == "subagent_start"]
    assert [name for _, name in starts] == ["market_scout", "interior_scout", "logistics_scout", "skeptic"]
    for index, name in starts:
        result_index = next(i for i, e in enumerate(emitted) if e.type == "subagent_result" and e.agent == name)
        assert index < result_index < len(emitted) - 1
    assert emitted[0].type == "plan" and emitted[-1].type == "final"
    assert any(e.type == "todo" for e in emitted)
    assert [e.ts for e in emitted] == sorted(e.ts for e in emitted)
    assert set(save_threads) == {get_ident()}
    assert {p.name for p in (tmp_path / "threads/deep-test").iterdir()} == {
        "requirements.json", "candidates.json", "shortlist.json", "skeptic.md"}
    assert not (tmp_path / "outbox").exists()
    fixed = pipeline.scout(RunContext("fixed-compare"), req)
    assert [p.model_dump() for p in response.picks] == [p.model_dump() for p in fixed.picks]
    assert response.gave_up == fixed.gave_up
    for pick in response.picks:
        assert {e.source for e in pick.evidence} == {"costar", "matterport", "vexcel"}


def test_tool_failure_emits_error_and_raises_without_memory(monkeypatch, tmp_path):
    fake_model(monkeypatch)
    def fail(**kwargs):
        raise RuntimeError("private provider payload")
    monkeypatch.setattr(pipeline, "search_costar", fail)
    emitted = []
    with pytest.raises(RuntimeError):
        deep.run_deep(RunContext("deep-error", emit=emitted.append), Requirements(scene="office"))
    errors = [e for e in emitted if e.type == "error"]
    assert errors and errors[0].agent == "search_costar"
    assert "private provider" not in json.dumps([e.model_dump() for e in emitted])
    assert not (tmp_path / "threads/deep-error").exists()


def test_invented_final_records_fail_closed(monkeypatch, tmp_path):
    fake_model(monkeypatch, bad_final=True)
    with pytest.raises(ValueError, match="authoritative"):
        deep.run_deep(RunContext("deep-invalid"), Requirements(scene="office"))
    assert not (tmp_path / "threads/deep-invalid").exists()
    assert not deep._approvals


def test_actual_approval_interrupt_resumes_local_draft_once(monkeypatch, tmp_path):
    model = fake_model(monkeypatch)
    response = deep.run_deep(RunContext("deep-approve"), Requirements(scene="office"))
    pick = response.picks[0]
    path = tmp_path / f"outbox/deep-approve-{pick.rank}.md"
    assert not path.exists()
    staged = deep._approvals[("deep-approve", pick.rank)]
    snapshot = staged.graph.get_state(staged.config)
    assert snapshot.tasks[0].interrupts[0].value["action_requests"][0]["name"] == "draft_inquiry"
    calls = list(model._history)
    result = deep.approve_draft(RunContext("deep-approve", engine="deep"), pick.rank, "yes")
    assert result == {"status": "draft_saved", "sent": False,
                      "path": f"cache/outbox/deep-approve-{pick.rank}.md"}
    assert "No message has been sent" in path.read_text()
    assert model._history == calls  # approval does not ask a model to regenerate the draft
    assert deep.approve_draft(RunContext("deep-approve"), pick.rank, "yes") == result


def test_declined_approval_never_runs_draft(monkeypatch, tmp_path):
    fake_model(monkeypatch)
    response = deep.run_deep(RunContext("deep-decline"), Requirements(scene="office"))
    result = deep.approve_draft(RunContext("deep-decline"), response.picks[0].rank, "no")
    assert result == {"status": "cancelled", "sent": False}
    assert not (tmp_path / "outbox").exists()


def test_http_approval_resumes_real_graph_without_model_calls(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from agent import runtime
    from agent.app import app
    model = fake_model(monkeypatch)
    monkeypatch.setenv("TYPECAST_ENGINE", "deep")
    monkeypatch.setattr(runtime.parse, "parse_scene", lambda scene, **kwargs: Requirements(scene=scene))
    response = runtime.run_scout(runtime.create_context("deep-http"), "office")
    assert response.engine == "deep"
    calls = list(model._history)
    assert not (tmp_path / "outbox").exists()
    with TestClient(app) as client:
        approved = client.post("/approve", json={"thread_id": "deep-http", "pick_rank": 1, "decision": "yes"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "draft_saved" and approved.json()["sent"] is False
    assert approved.json()["engine"] == "deep" and approved.json()["source_mode"] == "mock"
    assert (tmp_path / "outbox/deep-http-1.md").is_file()
    assert model._history == calls


def test_empty_pool_still_calls_all_scouts_and_skeptic(monkeypatch):
    model = fake_model(monkeypatch)
    monkeypatch.setattr(pipeline, "search_costar", lambda **kwargs: [])
    response = deep.run_deep(RunContext("deep-empty"), Requirements(scene="office"))
    assert response.picks == []
    assert {"market_scout", "interior_scout", "logistics_scout", "skeptic"} <= set(model._history)


def test_deadline_raises_before_any_source_work(monkeypatch):
    fake_model(monkeypatch)
    monkeypatch.setattr(deep.ToolSession, "check_deadline", lambda self: (_ for _ in ()).throw(TimeoutError("90 seconds")))
    with pytest.raises(TimeoutError):
        deep.run_deep(RunContext("deep-timeout"), Requirements(scene="office"))


def test_cancellation_cannot_publish_late_approval_checkpoints(monkeypatch, tmp_path):
    fake_model(monkeypatch)
    cancelled = ThreadEvent()
    ctx = RunContext("deep-cancel", cancelled=cancelled)
    original = deep._stage_draft

    def cancel_after_stage(*args):
        staged = original(*args)
        cancelled.set()
        return staged

    monkeypatch.setattr(deep, "_stage_draft", cancel_after_stage)
    with state.stage_writes(ctx.thread_id):
        with pytest.raises(TimeoutError):
            deep.run_deep(ctx, Requirements(scene="office"))
    assert not deep._approvals
    assert not (tmp_path / "threads/deep-cancel").exists()


def test_configured_model_is_not_hard_coded(monkeypatch):
    import langchain.chat_models
    seen = {}
    def init(model, **kwargs):
        seen.update(model=model, **kwargs)
        return object()
    monkeypatch.setattr(langchain.chat_models, "init_chat_model", init)
    monkeypatch.setenv("TYPECAST_LLM_MODEL", "configured-model-id")
    monkeypatch.setenv("TYPECAST_LLM_PROVIDER", "openai")
    monkeypatch.setenv("TYPECAST_REASONING_EFFORT", "high")
    monkeypatch.setenv("LLM_API_KEY", "test-only-key")
    deep._chat_model()
    assert seen["model"] == "configured-model-id" and seen["model_provider"] == "openai"
    assert seen["reasoning"] == {"effort": "high"}
    assert seen["store"] is False and seen["max_retries"] == 0
