"""Team-local real-image retrieval preview. Run on 127.0.0.1, never expose credentials."""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from index.search import (ROOT, get_active_index, get_shot, search_shots,
                          IndexUnavailableError, ShotNotFoundError)

app = FastAPI(title='Typecast interior preview', docs_url=None, redoc_url=None)


@app.get('/api/search')
def search(q: str = Query(min_length=1, max_length=500), example: str | None = None):
    try:
        index = get_active_index()
        results = search_shots(query_text=None if example else q, query_shot_id=example, k=12)
    except (ValueError, IndexUnavailableError, ShotNotFoundError):
        raise HTTPException(503, 'Interior index unavailable or query invalid') from None
    metadata_path = ROOT / 'cache/view-provenance.json'
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        metadata = {}
    return {'mode': 'mock' if index.is_mock else 'live', 'indexed_views': len(index.shots),
            'properties': len({s.property_id for s in index.shots}),
            'shots': [{**s.model_dump(), 'context': metadata.get(s.shot_id, {})} for s in results]}


@app.get('/image/{shot_id}')
def image(shot_id: str):
    try:
        shot = get_shot(shot_id)
        path = (ROOT / shot.image_path.lstrip('/')).resolve()
        if not path.is_relative_to((ROOT / 'cache/views').resolve()) or not path.is_file():
            raise ValueError('Invalid image path')
    except (ValueError, IndexUnavailableError, ShotNotFoundError):
        raise HTTPException(404, 'View not found') from None
    return FileResponse(path, headers={'Cache-Control': 'private, no-store'})


@app.get('/', response_class=HTMLResponse)
def home():
    return (Path(__file__).parent / 'preview.html').read_text(encoding='utf-8')
