"""Owner 3. HTTP API. Run: uvicorn agent.app:app --reload"""
import asyncio, os, pathlib
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contracts.schemas import ScoutRequest, ScoutResponse
from agent import pipeline

app = FastAPI(title="Typecast")
_drafts: dict[str, dict] = {}


class RefineRequest(BaseModel):
    thread_id: str
    message: str


class ApproveRequest(BaseModel):
    thread_id: str
    pick_rank: int
    decision: str   # "yes" or "no"


@app.get("/health")
def health():
    return {"ok": True, "mocks": os.getenv("TYPECAST_USE_MOCKS", "1") == "1"}


@app.post("/scout", response_model=ScoutResponse)
def scout(req: ScoutRequest):
    try:
        return pipeline.scout(req.scene, req.example_shot_id, req.thread_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/scout/stream")
async def scout_stream(scene: Optional[str] = None, example_shot_id: Optional[str] = None,
                       thread_id: Optional[str] = None):
    """Server-sent events: one `agent` event per step, then one `result` event with the full response."""
    try:
        res = pipeline.scout(scene, example_shot_id, thread_id)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))
    delay = float(os.getenv("TYPECAST_EVENT_DELAY", "0.35"))

    async def gen():
        for e in res.events:
            yield f"event: agent\ndata: {e.model_dump_json()}\n\n"
            await asyncio.sleep(delay)
        yield f"event: result\ndata: {res.model_dump_json()}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/refine", response_model=ScoutResponse)
def refine(req: RefineRequest):
    if req.thread_id not in pipeline._threads:
        raise HTTPException(404, "unknown thread")
    return pipeline.refine(req.thread_id, req.message)


@app.post("/approve")
def approve(req: ApproveRequest):
    """The owner note is only ever released to the team inbox, and only on an explicit yes."""
    if req.decision.strip().lower() != "yes":
        return {"sent": False, "to": None}
    inbox = os.getenv("TEAM_INBOX")
    if not inbox:
        raise HTTPException(400, "TEAM_INBOX is not set")
    # TODO Owner 3/4: deliver the drafted note to TEAM_INBOX. Never to a real owner.
    return {"sent": False, "to": inbox, "note": "delivery not implemented yet"}


# Static files: the viewer at /app, fake images at /mocks, cached real images at /cache.
_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _url, _dir in (("/mocks", "mocks"), ("/cache", "cache")):
    if (_ROOT / _dir).is_dir():
        app.mount(_url, StaticFiles(directory=_ROOT / _dir), name=_dir)
if (_ROOT / "web" / "index.html").exists():
    app.mount("/app", StaticFiles(directory=_ROOT / "web", html=True), name="web")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/app/" if (_ROOT / "web" / "index.html").exists() else "/docs")
