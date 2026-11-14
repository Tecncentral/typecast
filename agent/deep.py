"""A real Deep Agents director, source scouts, read-only skeptic and draft gate."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
import importlib.util
import json
import os
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agent import state
from agent.deep_tools import ToolSession, make_tools
from agent.interfaces import Requirements, RunContext, timed
from contracts.schemas import Event, Pick, ScoutResponse

PROMPTS = Path(__file__).with_name("prompts")
MAX_APPROVALS = 512


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_ids: list[str]


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: str
    objection: str = Field(min_length=1, max_length=1600)


class Reviews(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviews: list[Review]


def is_available() -> bool:
    provider = os.getenv("TYPECAST_LLM_PROVIDER", "openai").strip().lower()
    integration = {"openai": "langchain_openai", "anthropic": "langchain_anthropic"}.get(provider)
    return bool(integration and os.getenv("LLM_API_KEY", "").strip()
                and os.getenv("TYPECAST_LLM_MODEL", "").strip()
                and importlib.util.find_spec("deepagents") and importlib.util.find_spec(integration))


def _chat_model(*, scout: bool = False):
    """Create an independent director or delegate model with its own effort."""
    from langchain.chat_models import init_chat_model
    provider = os.getenv("TYPECAST_LLM_PROVIDER", "openai").strip().lower()
    model = os.getenv("TYPECAST_LLM_MODEL", "").strip()
    key = os.getenv("LLM_API_KEY", "").strip()
    if not model or not key or provider not in {"openai", "anthropic"}:
        raise RuntimeError("Deep engine needs a configured text provider and model")
    options: dict[str, Any] = {"api_key": key, "timeout": 15.0, "max_retries": 0}
    if provider == "openai":
        options.update(use_responses_api=True, store=False, include=["reasoning.encrypted_content"])
        setting, default = (("TYPECAST_SCOUT_REASONING_EFFORT", "low") if scout else
                            ("TYPECAST_REASONING_EFFORT", "medium"))
        options["reasoning"] = {"effort": os.getenv(setting, default).strip() or default}
    return init_chat_model(model, model_provider=provider, **options)


def _prompt(name: str) -> str:
    return (PROMPTS / f"deep_{name}.md").read_text(encoding="utf-8")


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(block.get("text", "") for block in content if isinstance(block, dict))


class _StreamEvents:
    """Translate actual LangGraph update messages; no synthetic scout progress."""
    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.tasks: dict[str, str] = {}
        self.completed: set[str] = set()
        self.seen: set[tuple[str, str]] = set()
        self.planned = False
        self.last_answer = ""
        self.reviews: Reviews | None = None

    def todo_update(self, todos):
        """Emit only todo values read from a real tool update or saved checkpoint."""
        self.ctx.event(Event(type="todo", agent="director", text=json.dumps(todos)))

    def update(self, chunk):
        namespace, update = chunk
        if namespace or not isinstance(update, dict):
            return
        from langchain_core.messages import AIMessage, ToolMessage
        for payload in update.values():
            if not isinstance(payload, dict):
                continue
            if "todos" in payload:
                self.todo_update(payload["todos"])
            messages = payload.get("messages", [])
            if not isinstance(messages, (list, tuple)):
                messages = [messages]
            for message in messages:
                if isinstance(message, AIMessage):
                    if not self.planned and (not message.tool_calls or message.tool_calls[0]["name"] != "write_todos"):
                        raise ValueError("Deep director must write its to-do plan before starting work")
                    if not message.tool_calls:
                        self.last_answer = _text(message.content)
                    for call in message.tool_calls:
                        marker = ("call", call["id"])
                        if marker in self.seen:
                            continue
                        self.seen.add(marker)
                        if call["name"] == "write_todos" and not self.planned:
                            self.planned = True
                            self.ctx.event(Event(type="plan", agent="director",
                                                 text=json.dumps(call["args"].get("todos", []))))
                        if call["name"] == "task":
                            name = call["args"].get("subagent_type", "")
                            self.tasks[call["id"]] = name
                            self.ctx.event(Event(type="subagent_start", agent=name,
                                                 text=call["args"].get("description", "")))
                if isinstance(message, ToolMessage):
                    marker = ("result", message.tool_call_id)
                    if marker in self.seen:
                        continue
                    self.seen.add(marker)
                    if message.status == "error":
                        raise RuntimeError(f"Deep tool failed: {message.name}")
                    name = self.tasks.get(message.tool_call_id)
                    if name:
                        content = _text(message.content)
                        self.completed.add(name)
                        self.ctx.event(Event(type="subagent_result", agent=name, text=content))
                        if name == "skeptic":
                            self.reviews = Reviews.model_validate_json(content)
                            for review in self.reviews.reviews:
                                self.ctx.event(Event(type="skeptic", agent="skeptic",
                                                     text=f"{review.property_id}: {review.objection}"))


def _build_graph(model, session: ToolSession):
    from deepagents import create_deep_agent
    from deepagents.backends import StateBackend
    from deepagents.middleware.filesystem import FilesystemMiddleware
    from langchain.agents.middleware import TodoListMiddleware
    from langgraph.checkpoint.memory import InMemorySaver
    tools = make_tools(session)
    specs = [
        ("market_scout", "Search and inspect CoStar source properties.", "market", ["search_costar", "get_property"]),
        ("interior_scout", "Retrieve, rerank and check Matterport camera views.", "interior",
         ["search_shots", "check_shot", "rerank_shots"]),
        ("logistics_scout", "Check Vexcel crew parking, walking distance and noise.", "logistics", ["plan_logistics"]),
        ("skeptic", "Read the verified shortlist and object to each pick using its evidence.", "skeptic", ["get_shortlist"]),
    ]
    subagents = [{"name": name, "description": description, "system_prompt": _prompt(prompt),
                  "model": _chat_model(scout=True), "tools": [tools[t] for t in names],
                  "middleware": [FilesystemMiddleware(tools=["read_file"])]}
                 for name, description, prompt, names in specs]
    return create_deep_agent(
        model=model, system_prompt=_prompt("director"), tools=[tools["build_shortlist"]],
        subagents=subagents, backend=StateBackend(), checkpointer=InMemorySaver(),
        middleware=[FilesystemMiddleware(tools=["read_file"]), TodoListMiddleware(
            system_prompt=("Track the source-backed scouting steps with write_todos, at most once per turn. "
                           "Combine each update with the next source task/tool calls. Keep todo content to "
                           "four words and task descriptions to 25 words. After the skeptic result, return "
                           "the final authoritative ids immediately without another tool call. The application "
                           "completes your persisted todo checkpoint only after validating those ids, every "
                           "review, and all staged draft approval checkpoints."),
            tool_description=("Replace the scouting todo list with content/status entries (pending, in_progress, "
                              "completed). Keep each content to four words. Mark only verified finished steps "
                              "completed. Call at most once per turn and alongside source work. Leave final "
                              "verification in_progress when delegating to the skeptic; the application "
                              "completes the checkpoint after validating the final answer and staging approvals."))],
        name="typecast_director")


def _complete_todos(graph, config, session: ToolSession, mapper: _StreamEvents) -> None:
    """Complete and verify the persisted plan after result validation and draft staging."""
    session.check_deadline()
    with _tracing()[0]:
        snapshot = graph.get_state(config)
        todos = snapshot.values.get("todos", [])
        if snapshot.next or not todos:
            raise ValueError("Deep plan is unfinished or has no persisted todos")
        completed = [{**todo, "status": "completed"} for todo in todos]
        # With no pending graph work, LangGraph infers the last completed node.
        # Specifying as_node="model" would incorrectly enqueue after-model hooks.
        checkpoint = graph.update_state(config, {"todos": completed})
        verified = graph.get_state(checkpoint)
        if verified.next or verified.values.get("todos") != completed:
            raise ValueError("Deep todo completion was not persisted")
    session.check_deadline()
    mapper.todo_update(verified.values["todos"])


@dataclass
class _Approval:
    graph: Any
    config: dict
    property_id: str
    expires: float
    ctx: RunContext
    result: dict | None = None


_approvals: OrderedDict[tuple[str, int], _Approval] = OrderedDict()
_approval_lock = RLock()


def _stage_draft(model, ctx: RunContext, pick: Pick) -> _Approval:
    """Seed an exact source-backed tool request at the graph's approval node."""
    from deepagents import create_deep_agent
    from deepagents.backends import StateBackend
    from deepagents.middleware.filesystem import FilesystemMiddleware
    from langchain_core.messages import AIMessage
    from langchain_core.tools import StructuredTool
    from langgraph.checkpoint.memory import InMemorySaver

    # Retain a small approval context, not the completed scouting worker's event
    # callback and accumulated response. /approve attaches its current callback.
    draft_ctx = RunContext(ctx.thread_id, engine="deep", source_mode=ctx.source_mode)

    def draft_inquiry(pick_rank: int) -> dict[str, Any]:
        """Save an approved inquiry to the local outbox. Never send any message."""
        if pick_rank != pick.rank:
            raise ValueError("Approved rank does not match the staged draft")
        note = (f"# Draft inquiry: {pick.property.address}\n\nHello,\n\n"
                "We are considering this property as a filming location. Could you confirm "
                "filming availability, permissions, and parking access?\n\n"
                f"Property: {pick.property.address}, {pick.property.city}\n\n"
                f"Scouting notes: {pick.reason}\n\n"
                "This is a local draft. No message has been sent.\n")
        with timed(draft_ctx, "draft_inquiry"):
            state.save_draft(draft_ctx.thread_id, pick_rank, note)
        return {"status": "draft_saved", "sent": False,
                "path": f"cache/outbox/{draft_ctx.thread_id}-{pick_rank}.md"}

    graph = create_deep_agent(
        model=model, tools=[StructuredTool.from_function(draft_inquiry)], backend=StateBackend(),
        middleware=[FilesystemMiddleware(tools=["read_file"])], checkpointer=InMemorySaver(),
        interrupt_on={"draft_inquiry": {"allowed_decisions": ["approve", "reject"]}},
        name="typecast_draft_approval")
    config = {"configurable": {"thread_id": f"{ctx.thread_id}-draft-{pick.rank}-{uuid4().hex}"}}
    # update_state(as_node="model") uses the real graph routing and HITL middleware,
    # but needs no extra model request to propose an already rendered local draft.
    with _tracing()[0]:
        graph.update_state(config, {"messages": [AIMessage(content="", tool_calls=[{
            "name": "draft_inquiry", "args": {"pick_rank": pick.rank},
            "id": f"draft-{pick.rank}", "type": "tool_call"}])]}, as_node="model")
        updates = list(graph.stream(None, config, stream_mode="updates"))
    if not any(chunk.get("__interrupt__") for chunk in updates):
        raise RuntimeError("Draft tool did not pause for approval")
    return _Approval(graph, config, pick.property.property_id, monotonic() + state.TTL_SECONDS, draft_ctx)


def approve_draft(ctx: RunContext, pick_rank: int, decision: str) -> dict:
    """Resume the actual HITL checkpoint from /approve; produce only a local file."""
    from langgraph.types import Command
    saved = state.get_thread(ctx.thread_id)
    picks = [p if isinstance(p, Pick) else Pick.model_validate(p) for p in saved.get("shortlist", [])]
    pick = next((p for p in picks if p.rank == pick_rank), None)
    with _approval_lock:
        staged = _approvals.get((ctx.thread_id, pick_rank))
        if not pick or not staged or staged.expires <= monotonic() or staged.property_id != pick.property.property_id:
            raise ValueError("Deep approval checkpoint is absent or expired; run a new scout first")
        if staged.result is not None:
            return dict(staged.result)
        staged.ctx.emit = ctx.emit
        staged.ctx.timings = ctx.timings
        staged.ctx.started_at = ctx.started_at
        approve = decision.strip().lower() == "yes"
        response = {"decisions": [{"type": "approve"} if approve else
                                  {"type": "reject", "message": "User declined this local draft."}]}
        # Stop after the tool node: approval never needs another language-model turn.
        with _tracing()[0]:
            updates = list(staged.graph.stream(Command(resume=response), staged.config,
                                                stream_mode="updates", interrupt_after=["tools"],
                                                interrupt_before=["model"]))
        if not approve:
            staged.result = {"status": "cancelled", "sent": False}
        else:
            messages = [m for chunk in updates for payload in chunk.values() if isinstance(payload, dict)
                        for m in payload.get("messages", []) if getattr(m, "name", None) == "draft_inquiry"]
            if not messages or getattr(messages[-1], "status", None) == "error":
                raise RuntimeError("Approved draft tool failed")
            staged.result = json.loads(_text(messages[-1].content))
        return dict(staged.result)


def _tracing():
    from agent.tracing import graph_tracing
    return graph_tracing(), None


def run_deep(ctx: RunContext, req: Requirements | dict) -> ScoutResponse:
    """Run the graph and validate only tool-backed picks; raise for runtime fallback."""
    from deepagents.backends.utils import create_file_data
    ctx.engine = "deep"
    events: list[Event] = []
    downstream = ctx.emit

    def emit(event):
        events.append(event)
        downstream(event)

    ctx = replace(ctx, emit=emit)
    example = req.get("example_shot_id") if isinstance(req, dict) else None
    if example:
        req = Requirements(scene=f"spaces like shot {example}")
    elif not isinstance(req, Requirements):
        req = Requirements.model_validate(req)
    session = ToolSession(ctx, req, example_shot_id=example)
    mapper = _StreamEvents(ctx)
    try:
        model = _chat_model()
        graph = _build_graph(model, session)
        config: dict[str, Any] = {"configurable": {"thread_id": f"{ctx.thread_id}-{uuid4().hex}"},
                                  "recursion_limit": 100}
        tracing, _ = _tracing()
        with tracing:
            payload = {"messages": [{"role": "user", "content": json.dumps({
                "requirements": req.model_dump(mode="json"), "example_shot_id": example})}],
                       "files": {"/requirements.json": create_file_data(req.model_dump_json())}}
            for chunk in graph.stream(payload, config, stream_mode="updates", subgraphs=True):
                session.check_deadline()
                mapper.update(chunk)
                if session.failures:
                    raise RuntimeError("A deep source tool failed")
        required_agents = {"market_scout", "interior_scout", "logistics_scout", "skeptic"}
        if not mapper.planned or not required_agents.issubset(mapper.completed):
            raise ValueError("Deep director did not complete its plan and four required delegates")
        if "build_shortlist" not in session.calls or mapper.reviews is None:
            raise ValueError("Deep director omitted the verified shortlist or skeptic review")
        decision = Decision.model_validate_json(mapper.last_answer)
        expected = [p.property.property_id for p in session.picks]
        if decision.property_ids != expected:
            raise ValueError("Deep director's final ids differ from the authoritative shortlist")
        reviews = mapper.reviews.reviews
        if len(reviews) != len(expected) or {r.property_id for r in reviews} != set(expected):
            raise ValueError("Skeptic did not review every actual pick exactly once")
        objections = {r.property_id: r.objection.strip() for r in reviews}
        for pick in session.picks:
            note = objections[pick.property.property_id]
            if note != "No objection.":
                pick.skeptic_notes = [n for n in pick.skeptic_notes if n != "No objection."]
                if note not in pick.skeptic_notes:
                    pick.skeptic_notes.append(note)
        # Only this main worker writes working memory: raw LangGraph tool threads
        # do not inherit runtime's state.stage_writes ContextVar.
        for name, obj in (("requirements", req),
                          ("sources", {"properties": session.properties, "logistics": session.logistics,
                                       "missing_logistics": sorted(session.missing_logistics)}),
                          ("candidates", session.shots),
                          ("shortlist", session.picks),
                          ("skeptic", "\n\n".join(f"## Pick {p.rank}: {p.property.address}\n" +
                              "\n".join(f"- {n}" for n in p.skeptic_notes) for p in session.picks))):
            with timed(ctx, f"state.save.{name}"):
                state.save(ctx.thread_id, name, obj)
        pending = {}
        for pick in session.picks:
            session.check_deadline()
            pending[(ctx.thread_id, pick.rank)] = _stage_draft(model, ctx, pick)
        _complete_todos(graph, config, session, mapper)
        with _approval_lock:
            session.check_deadline()
            for key in list(_approvals):
                if key[0] == ctx.thread_id or _approvals[key].expires <= monotonic():
                    del _approvals[key]
            _approvals.update(pending)
            while len(_approvals) > MAX_APPROVALS:
                _approvals.popitem(last=False)
        ctx.event(Event(type="final", agent="director", text=f"{len(session.picks)} source-backed picks reviewed by the skeptic."))
        return ScoutResponse(thread_id=ctx.thread_id, picks=session.picks, gave_up=session.gave_up,
                             events=events, engine="deep", source_mode=ctx.source_mode,
                             trace_url=None, timings=dict(ctx.timings))
    except Exception as exc:
        if not session.failures:
            ctx.event(Event(type="error", agent="director",
                            text=f"Deep scouting failed ({type(exc).__name__}); fixed fallback is required."))
        raise
