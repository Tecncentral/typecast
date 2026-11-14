"""Offline integration with real Deep Agents graphs and a deterministic chat model."""
from __future__ import annotations

import json
from threading import Event as ThreadEvent, Lock, get_ident
from time import perf_counter, sleep
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from agent import deep, pipeline, state
from agent.interfaces import Requirements, RunContext
from agent.deep_tools import SUMMARY_BYTES, ToolSession, make_tools
from contracts.schemas import ScoutResponse


class DeterministicChat(BaseChatModel):
    """Actually executes the graph's tools and subagents without any provider calls."""
    bad_final: bool = False
    _steps: dict[str, int] = PrivateAttr(default_factory=dict)
    _history: list[str] = PrivateAttr(default_factory=list)
    _director_turns: list[tuple[str, ...]] = PrivateAttr(default_factory=list)
    _interior_turns: list[tuple[str, ...]] = PrivateAttr(default_factory=list)

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
            elif step == 1 and result("search_costar")["properties"]:
                answer = call("get_property", {"property_id": result("search_costar")["properties"][0]["property_id"]})
            else:
                answer = AIMessage(content=json.dumps({"properties": result("search_costar")}))
        elif role == "interior_scout":
            if step == 0:
                answer = call("search_shots")
            elif step == 1:
                answer = call("rerank_shots")
                if result("search_shots")["shots"]:
                    answer.tool_calls.extend(call("check_shot", {
                        "shot_id": result("search_shots")["shots"][0]["shot_id"]}).tool_calls)
                self._interior_turns.append(tuple(c["name"] for c in answer.tool_calls))
            else:
                answer = AIMessage(content=json.dumps({"property_ids": list(dict.fromkeys(
                    s["property_id"] for s in result("search_shots")["shots"]))}))
        elif role == "logistics_scout":
            if step == 0:
                answer = call("plan_logistics")
            else:
                answer = AIMessage(content="Checked the supplied candidate logistics.")
        elif role == "skeptic":
            if step == 0:
                answer = call("get_shortlist")
            else:
                answer = AIMessage(content=json.dumps({"reviews": [{"property_id": p["property"]["property_id"],
                    "objection": p["skeptic_notes"][0]} for p in result("get_shortlist")["picks"]]}))
        else:
            if step == 4:
                ids = [p["property"]["property_id"] for p in result("build_shortlist")["picks"]]
                answer = AIMessage(content=json.dumps({"property_ids": ["invented"] if self.bad_final else ids}))
            else:
                calls = [{"name": "write_todos", "args": {"todos": [{
                    "content": "Verify source evidence", "status": "in_progress"}]},
                    "id": f"director-{step}-todo", "type": "tool_call"}]
                for action in {0: ["market_scout"], 1: ["interior_scout", "logistics_scout"],
                               2: ["build_shortlist"], 3: ["skeptic"]}[step]:
                    args = {} if action == "build_shortlist" else {
                        "subagent_type": action, "description": "Inspect the complete market source pool."}
                    calls.append({"name": action if action == "build_shortlist" else "task", "args": args,
                                  "id": f"director-{step}-{action}", "type": "tool_call"})
                self._director_turns.append(tuple(c["args"].get("subagent_type", c["name"]) for c in calls))
                answer = AIMessage(content="", tool_calls=calls)
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
    monkeypatch.setattr(deep, "_chat_model", lambda **kwargs: model)
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
    assert response.trace_url is None
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
        "requirements.json", "sources.json", "candidates.json", "shortlist.json", "skeptic.md"}
    sources = json.loads((tmp_path / "threads/deep-test/sources.json").read_text())
    assert set(sources["properties"]) == set(sources["logistics"])
    assert sources["missing_logistics"] == []
    for pick in response.picks:
        pid = pick.property.property_id
        assert sources["properties"][pid] == pick.property.model_dump(mode="json")
        assert sources["logistics"][pid] == pick.logistics.model_dump(mode="json")
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
    events = []
    with pytest.raises(ValueError, match="authoritative"):
        deep.run_deep(RunContext("deep-invalid", emit=events.append), Requirements(scene="office"))
    assert not (tmp_path / "threads/deep-invalid").exists()
    assert not deep._approvals
    assert not any(all(todo["status"] == "completed" for todo in json.loads(e.text))
                   for e in events if e.type == "todo")


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


@pytest.mark.parametrize("director_effort,scout_effort,expected", [
    (None, None, ["medium", "low", "low", "low", "low"]),
    ("high", "minimal", ["high", "minimal", "minimal", "minimal", "minimal"]),
])
def test_subagent_model_override_gets_independent_effort(monkeypatch, director_effort, scout_effort, expected):
    import deepagents
    import langchain.chat_models
    created, captured = [], {}

    def init(model, **options):
        instance = object()
        created.append((instance, options["reasoning"]["effort"]))
        return instance

    def create(**options):
        captured.update(options)
        return object()

    monkeypatch.setattr(langchain.chat_models, "init_chat_model", init)
    monkeypatch.setattr(deepagents, "create_deep_agent", create)
    monkeypatch.setenv("TYPECAST_LLM_MODEL", "offline-configured-model")
    monkeypatch.setenv("TYPECAST_LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "offline-test-key")
    for name, value in [("TYPECAST_REASONING_EFFORT", director_effort),
                        ("TYPECAST_SCOUT_REASONING_EFFORT", scout_effort)]:
        monkeypatch.delenv(name, raising=False) if value is None else monkeypatch.setenv(name, value)
    director = deep._chat_model()
    deep._build_graph(director, ToolSession(RunContext("efforts"), Requirements(scene="office")))
    assert [effort for _, effort in created] == expected
    assert captured["model"] is director
    assert [spec["model"] for spec in captured["subagents"]] == [model for model, _ in created[1:]]
    assert len({id(model) for model, _ in created}) == 5


def test_real_graph_parallel_scouts_overlap_sleeping_source_tools(monkeypatch):
    model = fake_model(monkeypatch)
    intervals = {"interior": [], "logistics": []}
    lock = Lock()

    def sleeping(role, function):
        def invoke(*args, **kwargs):
            span = [perf_counter(), None]
            with lock:
                intervals[role].append(span)
            try:
                sleep(0.18)
                return function(*args, **kwargs)
            finally:
                span[1] = perf_counter()
        return invoke

    monkeypatch.setattr(pipeline, "search_shots", sleeping("interior", pipeline.search_shots))
    monkeypatch.setattr(pipeline, "plan_logistics", sleeping("logistics", pipeline.plan_logistics))
    emitted = []
    response = deep.run_deep(RunContext("deep-parallel", emit=emitted.append), Requirements(scene="office"))
    interior = intervals["interior"][0]
    logistics = min(intervals["logistics"], key=lambda span: span[0])
    assert max(interior[0], logistics[0]) < min(interior[1], logistics[1])
    assert ("write_todos", "interior_scout", "logistics_scout") in model._director_turns
    assert len(model._director_turns) == 4
    assert model._interior_turns == [("rerank_shots", "check_shot")]
    assert model._history.count("director") == 5
    assert model._history.count("interior_scout") == 3
    assert len(intervals["interior"]) == 1
    assert len(intervals["logistics"]) == len(pipeline.search_costar(city="Los Angeles", available_only=False))
    assert response.engine == "deep" and response.picks
    assert any(e.type == "tool" and e.agent == "plan_logistics" for e in emitted)
    start = min(interior[0], logistics[0])
    print("parallel source timing (ms): interior "
          f"{(interior[0] - start) * 1000:.2f}–{(interior[1] - start) * 1000:.2f}; logistics "
          f"{(logistics[0] - start) * 1000:.2f}–{(logistics[1] - start) * 1000:.2f}")


def test_logistics_uses_market_pool_and_shortlist_reuses_full_cache(monkeypatch):
    session = ToolSession(RunContext("deep-tool-cache"), Requirements(scene="office", trucks=3, cars=30))
    tools = make_tools(session)
    calls = []
    source = pipeline.plan_logistics

    def load(pid, trucks, cars):
        calls.append(pid)
        return source(pid, trucks, cars)

    monkeypatch.setattr(pipeline, "plan_logistics", load)
    outputs = [tools["search_costar"].invoke({})]
    assert not session.shots
    outputs.append(tools["plan_logistics"].invoke({}))
    assert set(session.logistics) == set(session.properties)
    assert len(calls) == len(session.properties)
    outputs.append(tools["get_property"].invoke({"property_id": next(iter(session.properties))}))
    outputs.append(tools["search_shots"].invoke({}))
    outputs.append(tools["rerank_shots"].invoke({}))
    outputs.append(tools["check_shot"].invoke({"shot_id": session.shots[0].shot_id}))
    outputs.append(tools["build_shortlist"].invoke({}))
    outputs.append(tools["get_shortlist"].invoke({}))
    assert len(calls) == len(session.properties)
    assert session.picks and all(p.logistics is session.logistics[p.property.property_id] for p in session.picks)
    assert all(isinstance(output, str) and len(output.encode()) <= SUMMARY_BYTES for output in outputs)
    for output in outputs[-2:]:
        summary = json.loads(output)
        assert summary["omitted"] == 0
        assert [p["property"]["property_id"] for p in summary["picks"]] == [p.property.property_id for p in session.picks]


def test_compact_pool_summaries_keep_full_source_records(monkeypatch):
    template = pipeline.search_costar(city="Los Angeles", available_only=False)[0]
    shot = pipeline.search_shots(query_text="office", property_ids=[template.property_id])[0]
    properties = [template.model_copy(update={"property_id": f"source-{i}", "contact": "private" * 1000})
                  for i in range(50)]
    shots = [shot.model_copy(update={"shot_id": f"view-{i}", "property_id": p.property_id,
                                     "reason": "full source reason" * 1000}) for i, p in enumerate(properties)]
    monkeypatch.setattr(pipeline, "search_costar", lambda **kwargs: properties)
    monkeypatch.setattr(pipeline, "search_shots", lambda **kwargs: shots)
    monkeypatch.setattr(pipeline, "_rerank", lambda ctx, req, views: list(views))
    session = ToolSession(RunContext("deep-summary"), Requirements(scene="office"))
    tools = make_tools(session)
    for name in ["search_costar", "search_shots", "rerank_shots"]:
        output = tools[name].invoke({})
        summary = json.loads(output)
        assert len(output.encode()) <= SUMMARY_BYTES
        assert summary["count"] == 50 and summary["omitted"] > 0
        assert "private" not in output and "full source reason" not in output
    assert list(session.properties.values()) == properties
    assert session.shots == shots and session.shots[-1].reason == shots[-1].reason


def test_shortlist_requires_logistics_for_every_retrieved_property():
    session = ToolSession(RunContext("deep-missing-logistics"), Requirements(scene="office"))
    tools = make_tools(session)
    tools["search_costar"].invoke({})
    tools["get_property"].invoke({"property_id": next(iter(session.properties))})
    tools["search_shots"].invoke({})
    tools["rerank_shots"].invoke({})
    tools["check_shot"].invoke({"shot_id": session.shots[0].shot_id})
    first = session.shots[0].property_id
    tools["plan_logistics"].invoke({"property_id": first})
    assert set(session.logistics) == {first}
    with pytest.raises(ValueError, match="Complete logistics_scout"):
        tools["build_shortlist"].invoke({})


def test_todos_complete_in_real_checkpoint_only_after_validation_and_approval_staging(monkeypatch):
    model = fake_model(monkeypatch)
    staged, captured, events = [], {}, []
    original_stage = deep._stage_draft
    original_complete = deep._complete_todos

    def stage(*args):
        result = original_stage(*args)
        staged.append(result)
        return result

    def complete(graph, config, session, mapper):
        before = graph.get_state(config)
        assert before.next == ()
        assert any(todo["status"] == "in_progress" for todo in before.values["todos"])
        assert len(staged) == len(session.picks)
        assert deep.Decision.model_validate_json(mapper.last_answer).property_ids == [
            pick.property.property_id for pick in session.picks]
        assert {review.property_id for review in mapper.reviews.reviews} == {
            pick.property.property_id for pick in session.picks}
        history = list(model._history)
        original_complete(graph, config, session, mapper)
        after = graph.get_state(config)
        assert after.next == ()
        assert [todo["content"] for todo in after.values["todos"]] == [
            todo["content"] for todo in before.values["todos"]]
        assert all(todo["status"] == "completed" for todo in after.values["todos"])
        assert after.config != before.config
        assert model._history == history
        captured["todos"] = after.values["todos"]

    monkeypatch.setattr(deep, "_stage_draft", stage)
    monkeypatch.setattr(deep, "_complete_todos", complete)
    response = deep.run_deep(RunContext("deep-checkpoint-todos", emit=events.append), Requirements(scene="office"))
    todos = [event for event in events if event.type == "todo"]
    assert response.picks and captured["todos"] == json.loads(todos[-1].text)
    assert events.index(todos[-1]) > max(i for i, event in enumerate(events)
                                       if event.type == "subagent_result")
    assert len(model._director_turns) == 4 and model._history.count("director") == 5
