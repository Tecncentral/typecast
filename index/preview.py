"""Team-local real-image retrieval preview. Run on 127.0.0.1, never expose credentials."""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from index.search import (ROOT, get_active_index, get_shot, search_shots,
                          IndexUnavailableError, ShotNotFoundError)

app = FastAPI(title='Typecast interior preview', docs_url=None, redoc_url=None)
from index.labeling import router as evaluation_router
app.include_router(evaluation_router)


@app.get('/evaluate', response_class=HTMLResponse)
def evaluation_page():
    return Path(__file__).with_name('labeling.html').read_text(encoding='utf-8')


@app.get('/api/viewer-config')
def viewer_config():
    import os
    from dotenv import dotenv_values
    values = {**dotenv_values(ROOT / '.env'), **os.environ}
    key = (values.get('MATTERPORT_SDK_KEY') or '').strip()
    private = [v for name, v in values.items() if name != 'MATTERPORT_SDK_KEY'
               and name.endswith(('_KEY', '_TOKEN', '_SECRET', '_PASSWORD')) and v]
    return {'sdk_key': key if key and not any(v in key for v in private) else None}


def provenance():
    try:
        return json.loads((ROOT / 'cache/view-provenance.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


@app.get('/api/plan/{shot_id}')
def plan(shot_id: str, heading: float = Query(default=0, ge=0, lt=360),
         focal: float = Query(default=24, ge=8, le=200),
         sensor: float = Query(default=24.9, ge=10, le=70),
         width: float = Query(default=3, ge=.1, le=30)):
    from index.planning import plan_camera
    try:
        shot = get_shot(shot_id)
    except (IndexUnavailableError, ShotNotFoundError):
        raise HTTPException(404, 'View not found') from None
    context = provenance().get(shot_id, {})
    try:
        rooms = json.loads((ROOT / 'cache/matterport/room-plans.json').read_text(encoding='utf-8'))
        matches = [r for r in rooms.get(shot.model_id, [])
                   if r['room_id'] == context.get('room_id') and r['floor_id'] == context.get('floor_id')]
    except (OSError, ValueError, KeyError, TypeError):
        matches = []
    result = plan_camera(matches[0] if len(matches) == 1 else None,
        context.get('position_m'), heading_deg=heading, focal_mm=focal,
        sensor_width_mm=sensor, frame_width_m=width)
    return {**result, 'shot_id': shot_id, 'ceiling_m': shot.ceiling_m,
            'room_id': context.get('room_id'), 'floor_id': context.get('floor_id')}


@app.get('/studio.js')
def studio_script():
    return FileResponse(Path(__file__).parent / 'studio.js', media_type='text/javascript')


@app.get('/api/search')
def search(q: str | None = Query(default=None, min_length=1, max_length=500), example: str | None = None,
           diverse: bool = True, mood: str = Query(default='', max_length=100),
           lighting: str = Query(default='', max_length=100), materials: str = Query(default='', max_length=100)):
    if not q and not example:
        raise HTTPException(400, 'Describe a scene or choose an example')
    try:
        index = get_active_index()
        from index.cinematic import diverse_results, query_brief
        brief = query_brief(q, mood, lighting, materials) if q and not example else None
        results = search_shots(query_text=brief, query_shot_id=example, k=120 if diverse else 12)
        if diverse:
            vectors = None if index.embeddings is None else {
                s.shot_id: index.embeddings[index._id_to_idx[s.shot_id]] for s in results}
            results = diverse_results(results, vectors)
    except Exception:
        raise HTTPException(503, 'Interior index unavailable or query invalid') from None
    metadata_path = ROOT / 'cache/view-provenance.json'
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        metadata = {}
    return {'mode': 'mock' if index.is_mock else 'live', 'query_brief': brief,
            'ranking': 'diverse' if diverse else 'cosine', 'indexed_views': len(index.shots),
            'properties': len({s.property_id for s in index.shots}),
            'shots': [{**s.model_dump(), 'context': metadata.get(s.shot_id, {})} for s in results]}


@app.get('/image/{shot_id}')
def image(shot_id: str):
    try:
        shot = get_shot(shot_id)
        path = (ROOT / shot.image_path.lstrip('/')).resolve()
        allowed = ROOT / ('mocks/img' if get_active_index().is_mock else 'cache/views')
        if not path.is_relative_to(allowed.resolve()) or not path.is_file():
            raise ValueError('Invalid image path')
    except (ValueError, IndexUnavailableError, ShotNotFoundError):
        raise HTTPException(404, 'View not found') from None
    return FileResponse(path, headers={'Cache-Control': 'private, no-store'})


@app.get('/', response_class=HTMLResponse)
def home():
    return (Path(__file__).parent / 'preview.html').read_text(encoding='utf-8')
