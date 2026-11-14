"""Owner 3. HTTP API. Run: uvicorn agent.app:app --reload"""
import os
from fastapi import FastAPI, HTTPException
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
