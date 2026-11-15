"""HTTP API, real progress events, and local inquiry drafts."""
import asyncio
import json
import os
import pathlib
import re
from threading import Event as ThreadEvent
from typing import Literal, Optional

from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env", override=False)

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from contracts.schemas import Pick, ScoutRequest, ScoutResponse
from agent import runtime, state, tracing

app = FastAPI(title="Typecast")

from index.production_integration import shared_router
app.include_router(shared_router())


@app.get("/api/aerial/{property_id}")
def aerial_metadata(property_id: str):
    """Small validated image extent for the viewer; general cache JSON stays private."""
    from agent.aerial_metadata import AerialMetadataUnavailable, read_aerial_metadata
    try:
        metadata = read_aerial_metadata(property_id, _ROOT / "cache")
    except AerialMetadataUnavailable:
        raise HTTPException(404, "Aerial metadata unavailable.",
                            headers={"Cache-Control": "no-store"}) from None
    return JSONResponse(metadata, headers={"Cache-Control": "no-store"})


class ObliqueSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    area: str = Field(pattern=r"^[a-z-]{1,40}$")


class ObliqueViewRequest(BaseModel):
    search_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    index: int = Field(ge=0, le=31)
    direction: Literal["north", "east", "south", "west"]


class ObliqueReimagineRequest(ObliqueViewRequest):
    message: str = Field(min_length=1, max_length=600)


@app.get("/api/oblique/areas")
def oblique_areas():
    from agent.oblique_search import AREAS, image_model
    model, quality = image_model()
    return {"areas": [{"id": key, "label": label, "city": city} for key, (label, city, *_rest) in AREAS.items()],
            "image_model": model, "image_quality": quality}


def _oblique_error(error: Exception) -> HTTPException:
    from data.vexcel_client import ProviderError
    if isinstance(error, (KeyError,)):
        return HTTPException(404, "Search not found. Run the search again.")
    if isinstance(error, ValueError):
        return HTTPException(400, str(error))
    if isinstance(error, ProviderError):
        return HTTPException(502, str(error))
    return HTTPException(500, "Oblique search failed.")


@app.post("/api/oblique/search")
def oblique_search(req: ObliqueSearchRequest):
    from agent import oblique_search as oblique
    try:
        return oblique.search(req.query, req.area)
    except Exception as error:  # noqa: BLE001 - sanitized below
        raise _oblique_error(error) from None


@app.post("/api/oblique/view")
def oblique_view(req: ObliqueViewRequest):
    from agent import oblique_search as oblique
    try:
        return {**oblique.view(req.search_id, req.index, req.direction),
                "chat": oblique.chat(req.search_id, req.index, req.direction)}
    except Exception as error:  # noqa: BLE001
        raise _oblique_error(error) from None


class ObliqueAskRequest(BaseModel):
    search_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    index: int = Field(ge=0, le=31)
    question: str = Field(min_length=1, max_length=500)


@app.post("/api/oblique/ask")
def oblique_ask(req: ObliqueAskRequest):
    """Answer a question about one found place with live Vexcel data via Vexcel's MCP server."""
    from agent import oblique_search as oblique
    from agent.vexcel_assistant import AssistantError, ask
    try:
        record = oblique._load(req.search_id)
        place = next(r for r in record["results"] if r["index"] == req.index)
        return ask(req.question, place, record["city"])
    except (KeyError, StopIteration):
        raise HTTPException(404, "Place not found. Run the search again.") from None
    except AssistantError as error:
        raise HTTPException(502, str(error)) from None
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    except Exception:  # noqa: BLE001 - model or network failures are reported generically
        raise HTTPException(502, "The assistant could not answer right now.") from None


@app.post("/api/oblique/reimagine")
def oblique_reimagine(req: ObliqueReimagineRequest):
    from agent import oblique_search as oblique
    try:
        return oblique.reimagine(req.search_id, req.index, req.direction, req.message)
    except Exception as error:  # noqa: BLE001
        raise _oblique_error(error) from None


@app.get("/api/vexcel3d/place")
def vexcel3d_place(lat: float, lon: float):
    """Vexcel 3D Cities tiles around a point; tile URLs point at this server's proxy."""
    from urllib.parse import urlencode
    from data.vexcel_3d import City3D
    from data.vexcel_client import ProviderError
    if not (-85 <= lat <= 85 and -180 <= lon <= 180):
        raise HTTPException(400, "Invalid coordinates.")
    try:
        place = City3D().place(lat, lon)
    except ProviderError as error:
        raise HTTPException(502, str(error)) from None
    place["tiles"] = [f"/api/vexcel3d/tile?{urlencode(t)}" for t in place["tiles"]]
    return {**place, "center": [lat, lon]}


@app.get("/api/vexcel3d/tile")
def vexcel3d_tile(zoom: int, x: int = Query(alias="tile-x"), y: int = Query(alias="tile-y"),
                  child_aoi: str = Query(alias="childAOI")):
    from fastapi.responses import Response
    from data.vexcel_3d import City3D, tile_params
    from data.vexcel_client import ProviderError
    try:
        params = tile_params(zoom, x, y, child_aoi)  # validate before any client or key is touched
    except ValueError:
        raise HTTPException(400, "Invalid 3D tile reference.") from None
    try:
        content = City3D().tile(params)
    except ProviderError as error:
        raise HTTPException(502, str(error)) from None
    return Response(content, media_type="model/gltf-binary", headers={"Cache-Control": "private, max-age=86400"})


class RefineRequest(BaseModel):
    thread_id: str = Field(pattern=state.THREAD_ID_PATTERN)
    message: str


class ApproveRequest(BaseModel):
    thread_id: str = Field(pattern=state.THREAD_ID_PATTERN)
    pick_rank: int = Field(ge=1)
    decision: str


class ViewerConfig(BaseModel):
    mode: Literal["mock", "live", "mixed"]
    engine: Literal["fixed", "deep"]
    tracing: bool
    matterport_sdk_key: str | None


def _viewer_sdk_key() -> str | None:
    # Matterport documents applicationKey in browser imports/iframes and a
    # domain allow list: https://developers.matterport.com/embed-sdk/
    sdk_key = os.getenv("MATTERPORT_SDK_KEY", "").strip()
    if not sdk_key:
        return None
    # Fail closed if someone accidentally copied a server credential here.
    for name, value in os.environ.items():
        if name != "MATTERPORT_SDK_KEY" and name.endswith(("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")):
            private_value = value.strip()
            if private_value and private_value in sdk_key:
                return None
    return sdk_key


@app.get("/config", response_model=ViewerConfig)
def viewer_config():
    """Allow-listed browser settings; engine is configured choice, not a run result."""
    modes = set(runtime.source_modes().values())
    mode = next(iter(modes)) if len(modes) == 1 and modes <= {"mock", "live"} else "mixed"
    engine = os.getenv("TYPECAST_ENGINE", "fixed").lower()
    if engine not in {"fixed", "deep"}:
        raise HTTPException(503, "TYPECAST_ENGINE must be fixed or deep")
    return {"mode": mode, "engine": engine, "tracing": tracing.configured(),
            "matterport_sdk_key": _viewer_sdk_key()}


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


_SHOT_ID = re.compile(r"[A-Za-z0-9._-]{1,440}")


def _sweep_provenance():
    root = pathlib.Path(__file__).resolve().parents[1]
    try:
        data = json.loads((root / "cache/view-provenance.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _cube_face(shot, provenance):
    """Only known, indexed, square horizon cube images are renderer inputs."""
    context = provenance.get(shot.shot_id, {})
    if not isinstance(context, dict):
        return None
    face = context.get("cube_face_index")
    if type(face) is not int or face not in (1, 2, 3, 4):
        return None
    heading = (face - 1) * 90
    if shot.heading_deg != heading or not _SHOT_ID.fullmatch(shot.shot_id):
        return None
    expected = f"/cache/views/{shot.shot_id}.jpg"
    if shot.image_path != expected:
        return None
    root = pathlib.Path(__file__).resolve().parents[1]
    path = (root / expected.lstrip("/")).resolve()
    if not path.is_relative_to((root / "cache/views").resolve()):
        return None
    try:
        from PIL import Image
        with Image.open(path) as image:
            if image.width != image.height or image.width < 1:
                return None
    except (OSError, ValueError):
        return None
    return heading


@app.get("/api/sweep/{shot_id}")
def sweep_faces(shot_id: str):
    """Known horizon cube faces at an indexed scan point; headings are scan-relative."""
    if not _SHOT_ID.fullmatch(shot_id):
        raise HTTPException(422, "Invalid shot id")
    from index.search import get_active_index
    try:
        index = get_active_index()
        shot = index.get_shot(shot_id)
    except KeyError:
        raise HTTPException(404, "Unknown shot") from None
    except Exception:
        raise HTTPException(503, "Shot index unavailable") from None
    provenance = _sweep_provenance()
    if _cube_face(shot, provenance) is None:
        raise HTTPException(422, "This view has no verified horizon cube geometry")
    faces = {}
    for candidate in index.shots:
        if (candidate.property_id, candidate.model_id, candidate.sweep_id) != (shot.property_id, shot.model_id, shot.sweep_id):
            continue
        heading = _cube_face(candidate, provenance)
        if heading is not None:
            faces.setdefault(heading, candidate)
    return {
        "shot_id": shot.shot_id,
        "model_id": shot.model_id,
        "sweep_id": shot.sweep_id,
        "property_id": shot.property_id,
        "heading_deg": shot.heading_deg,
        "heading_reference": "scan-relative; not compass or SDK orientation",
        "projection": "horizon-cube-90deg",
        "room_area_m2": shot.room_area_m2,
        "ceiling_m": shot.ceiling_m,
        "depth_m": shot.depth_m,
        "measure_on_site": shot.measure_on_site,
        "faces": [{"heading_deg": heading, "image_path": face.image_path, "shot_id": face.shot_id}
                  for heading, face in sorted(faces.items())],
    }


@app.get("/api/dressed/{shot_id}")
def dressed_set(shot_id: str):
    """An AI-dressed version of the shot's scan point, if one was generated with World Labs Atlas.

    The dressed frames keep the real room's geometry (depth-guided restyle) but are AI-imagined;
    the label travels with every response so the viewer can never present them as the real room.
    """
    if os.getenv("TYPECAST_ENABLE_DRESSED", "1") == "0":
        raise HTTPException(404, "Dressed sets are disabled")
    if not _SHOT_ID.fullmatch(shot_id):
        raise HTTPException(422, "Invalid shot id")
    from index.search import get_active_index
    from worlds.dress import load_dressed
    try:
        shot = get_active_index().get_shot(shot_id)
    except KeyError:
        raise HTTPException(404, "Unknown shot") from None
    except Exception:
        raise HTTPException(503, "Shot index unavailable") from None
    try:
        record = load_dressed(shot.model_id, shot.sweep_id)
    except Exception:
        record = None
    if not record:
        raise HTTPException(404, "No dressed set for this scan point")
    base = record["dir"]
    splat = record["splat"]
    room = record["room"]
    # Everything below was validated by load_dressed. The cached label and generation
    # prompt are deliberately not forwarded: the label is always the canonical one.
    return {
        "shot_id": shot.shot_id,
        "scene_id": record["scene_id"],
        "scene": record["scene"],
        "label": record["label"],
        "created_at": record["created_at"],
        "faces": [{"yaw_deg": f["yaw_deg"], "pitch_deg": f["pitch_deg"], "tan_h": f["tan_h"], "tan_v": f["tan_v"],
                   "source_heading_deg": f["source_heading_deg"],
                   "dressed_url": f"{base}/{f['dressed']}",
                   "real_url": f"{base}/{f['real']}" if f["real"] else None}
                  for f in record["faces"]],
        "splat_url": f"{base}/{splat['file']}" if splat else None,
        # Walkable reconstruction of the dressed frames; `eye` is the scan point in the splat's world.
        # A whole-room set was built at Matterport's measured cameras, so its scale is known and
        # its floor is the scan's floor. One-point sets leave those fields out.
        "splat": {"url": f"{base}/{splat['file']}", "mode": splat["mode"], "splat_count": splat["splat_count"],
                  "eye": splat["eye"],
                  **({"units_per_m": room["units_per_m"], "floor_y": 0.0,
                      "scan_points": room["scan_point_positions"]} if room else {})} if splat else None,
        "room": {"scan_points": room["scan_points"], "views": room["views"]} if room else None,
    }


@app.get("/api/walkable")
def walkable_sets():
    """Frames whose scan point has a walkable AI-dressed set, so a card can offer to walk it.

    One list for the whole page: cards ask once instead of probing every frame.
    """
    if os.getenv("TYPECAST_ENABLE_DRESSED", "1") == "0":
        return {"sets": []}
    from index.search import get_active_index
    from worlds.dress import walkable_scan_points
    try:
        points = {(p["model_id"], p["sweep_id"]): {"shot_ids": [], "mode": p["mode"], "room": p["room"]}
                  for p in walkable_scan_points()}
        if points:
            for shot in get_active_index().shots:
                entry = points.get((shot.model_id, shot.sweep_id))
                if entry is not None and _SHOT_ID.fullmatch(shot.shot_id) and len(entry["shot_ids"]) < 16:
                    entry["shot_ids"].append(shot.shot_id)
    except Exception:
        return {"sets": []}
    return {"sets": [entry for entry in points.values() if entry["shot_ids"]]}


@app.get("/api/strike/{shot_id}")
def struck_frames(shot_id: str):
    """AI furniture removal for the shot's scan point, if it was precomputed with `python -m strike`.

    Each face was blended back into the real scan and checked with the Decisions API; only accepted
    faces carry a URL. The label is canonical, never taken from the cache.
    """
    if os.getenv("TYPECAST_ENABLE_STRIKE", "1") == "0":
        raise HTTPException(404, "Strike is disabled")
    if not _SHOT_ID.fullmatch(shot_id):
        raise HTTPException(422, "Invalid shot id")
    from index.search import get_active_index
    from strike.core import load_strike
    try:
        shot = get_active_index().get_shot(shot_id)
    except KeyError:
        raise HTTPException(404, "Unknown shot") from None
    except Exception:
        raise HTTPException(503, "Shot index unavailable") from None
    record = load_strike(shot.model_id, shot.sweep_id)
    if not record or not any(f["struck_url"] for f in record["faces"]):
        # Most frames have nothing to strike; that is an answer, not an error (no console noise per card).
        return {"shot_id": shot.shot_id, "label": None, "face": None, "faces": []}
    heading = round(shot.heading_deg) % 360
    face = next((f for f in record["faces"] if f["heading_deg"] == heading), None)
    return {"shot_id": shot.shot_id, "heading_deg": heading, "label": record["label"],
            "method": "AI image edit, blended into the real scan, checked by a decision model",
            "edit_model": record["edit_model"], "created_at": record["created_at"],
            "face": face, "faces": record["faces"]}


def _servable_cache_path(path: str) -> bool:
    """Images anywhere in cache/; Gaussian splats only from generated worlds."""
    pure = pathlib.PurePosixPath(path)
    suffix = pure.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}:
        return True
    return suffix == ".spz" and pure.parts[:1] == ("worlds",)


class CachedImages(StaticFiles):
    """Only cached imagery is a viewer asset; working memory stays private."""
    async def check_config(self):
        # A fresh checkout has no cache yet. Missing assets should return 404,
        # and images arriving later must work without restarting the API.
        if self.directory is not None and not pathlib.Path(self.directory).exists():
            return
        await super().check_config()

    async def get_response(self, path, scope):
        if not _servable_cache_path(path):
            raise HTTPException(404)
        if set(pathlib.PurePosixPath(path).parts) & {"threads", "outbox"}:
            raise HTTPException(404)
        return await super().get_response(path, scope)


class ViewerFiles(StaticFiles):
    """Viewer modules always revalidate (cheap 304s), so an update never runs
    new modules against a stale cached import such as utils.js."""
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _url, _dir, _cls in (("/mocks", "mocks", StaticFiles), ("/cache", "cache", CachedImages)):
    if _dir == "cache" or (_ROOT / _dir).is_dir():
        app.mount(_url, _cls(directory=_ROOT / _dir, check_dir=False), name=_dir)
if (_ROOT / "web" / "index.html").exists():
    app.mount("/app", ViewerFiles(directory=_ROOT / "web", html=True), name="web")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/app/" if (_ROOT / "web" / "index.html").exists() else "/docs")
