"""HTTP API, real progress events, and local inquiry drafts."""
import asyncio
import json
import os
import pathlib
from threading import Event as ThreadEvent
from typing import Optional

from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env", override=False)

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from contracts.schemas import Pick, ScoutRequest, ScoutResponse
from agent import runtime, state

app = FastAPI(title="Typecast")


class RefineRequest(BaseModel):
    thread_id: str = Field(pattern=state.THREAD_ID_PATTERN)
    message: str


class ApproveRequest(BaseModel):
    thread_id: str = Field(pattern=state.THREAD_ID_PATTERN)
    pick_rank: int = Field(ge=1)
    decision: str


@app.get("/health")
def health():
    modes = runtime.source_modes()
    mock = all(mode == "mock" for mode in modes.values())
    return {"ok": True, "mocks": mock, "source_modes": modes,
            "engines_available": runtime.available_engines(),
            "langsmith_configured": bool(os.getenv("LANGSMITH_API_KEY")),
            "engine": "fixed", "source_mode": "mock" if mock else "live", "timings": {}}


def _context(thread_id=None, emit=None):
    try:
        return runtime.create_context(thread_id, emit)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


def _unknown_thread():
    return HTTPException(404, "Unknown or expired thread; run a new scout first.")


@app.post("/scout", response_model=ScoutResponse)
def scout(req: ScoutRequest):
    if not req.scene and not req.example_shot_id:
        raise HTTPException(400, "give scene or example_shot_id")
    ctx = _context(req.thread_id)
    try:
        return runtime.run_scout(ctx, req.scene, req.example_shot_id)
    except runtime.SourceModeError as error:
        raise HTTPException(503, str(error)) from None
    except Exception:
        raise HTTPException(502, "Scouting failed. Please try again.") from None


@app.get("/scout/stream")
async def scout_stream(scene: Optional[str] = None, example_shot_id: Optional[str] = None,
                       thread_id: Optional[str] = None):
    """Run in a worker and forward each progress event as soon as it is emitted."""
    if not scene and not example_shot_id:
        raise HTTPException(400, "give scene or example_shot_id")
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    closed = ThreadEvent()

    def push(kind, payload):
        if not closed.is_set():
            loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))

    ctx = _context(thread_id, lambda event: push("agent", event))

    def work():
        try:
            push("result", runtime.run_scout(ctx, scene, example_shot_id))
        except Exception:
            push("error", {"message": "Scouting failed. Please try again.", "engine": ctx.engine,
                           "source_mode": ctx.source_mode, "timings": dict(ctx.timings)})

    async def gen():
        worker = asyncio.create_task(asyncio.to_thread(work))
        try:
            while True:
                kind, payload = await queue.get()
                data = payload.model_dump_json() if hasattr(payload, "model_dump_json") else json.dumps(payload)
                yield f"event: {kind}\ndata: {data}\n\n"
                if kind in {"result", "error"}:
                    break
        finally:
            closed.set()
            if not worker.done():
                worker.cancel()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/refine", response_model=ScoutResponse)
def refine(req: RefineRequest):
    ctx = _context(req.thread_id)
    try:
        return runtime.run_refine(ctx, req.message)
    except state.UnknownThread:
        raise _unknown_thread() from None
    except runtime.SourceModeError as error:
        raise HTTPException(503, str(error)) from None
    except Exception:
        raise HTTPException(502, "Refinement failed. Please try again.") from None


@app.post("/approve")
def approve(req: ApproveRequest):
    """Approval saves a local draft; it never sends a message."""
    try:
        saved = state.get_thread(req.thread_id)
    except state.UnknownThread:
        raise _unknown_thread() from None
    shortlist = [pick if isinstance(pick, Pick) else Pick.model_validate(pick)
                 for pick in saved.get("shortlist", [])]
    pick = next((pick for pick in shortlist if pick.rank == req.pick_rank), None)
    if pick is None:
        raise HTTPException(422, "pick_rank is not present in this thread's shortlist")
    metadata = saved.get("runtime", {"engine": "fixed", "source_mode": "mock", "timings": {}})
    if metadata["engine"] == "deep":
        from agent import deep
        ctx = _context(req.thread_id)
        ctx.engine = "deep"
        try:
            result = deep.approve_draft(ctx, req.pick_rank, req.decision)
        except ValueError:
            raise HTTPException(422, "No pending draft approval for this pick; run a new scout first.") from None
        except Exception:
            raise HTTPException(502, "Draft approval failed. No message was sent.") from None
        return {**result, **metadata}
    if req.decision.strip().lower() != "yes":
        return {"status": "cancelled", "sent": False, **metadata}
    note = (f"# Draft inquiry: {pick.property.address}\n\n"
            "Hello,\n\nWe are considering this property as a filming location. "
            "Could you confirm filming availability, permissions, and parking access?\n\n"
            f"Property: {pick.property.address}, {pick.property.city}\n\n"
            f"Scouting notes: {pick.reason}\n\n"
            "This is a local draft. No message has been sent.\n")
    state.save_draft(req.thread_id, req.pick_rank, note)
    path = f"cache/outbox/{req.thread_id}-{req.pick_rank}.md"
    return {"status": "draft_saved", "sent": False, "path": path, **metadata}


class CachedImages(StaticFiles):
    """Only cached imagery is a viewer asset; working memory stays private."""
    async def check_config(self):
        # A fresh checkout has no cache yet. Missing assets should return 404,
        # and images arriving later must work without restarting the API.
        if self.directory is not None and not pathlib.Path(self.directory).exists():
            return
        await super().check_config()

    async def get_response(self, path, scope):
        if pathlib.PurePosixPath(path).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}:
            raise HTTPException(404)
        if set(pathlib.PurePosixPath(path).parts) & {"threads", "outbox"}:
            raise HTTPException(404)
        return await super().get_response(path, scope)


_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _url, _dir, _cls in (("/mocks", "mocks", StaticFiles), ("/cache", "cache", CachedImages)):
    if _dir == "cache" or (_ROOT / _dir).is_dir():
        app.mount(_url, _cls(directory=_ROOT / _dir, check_dir=False), name=_dir)
if (_ROOT / "web" / "index.html").exists():
    app.mount("/app", StaticFiles(directory=_ROOT / "web", html=True), name="web")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/app/" if (_ROOT / "web" / "index.html").exists() else "/docs")
