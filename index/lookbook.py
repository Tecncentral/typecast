"""Self-contained local lookbooks with validated indexed images and escaped notes."""
import base64
import html
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from index.search import ROOT, get_shot, get_active_index

router = APIRouter()


class Pick(BaseModel):
    shot_id: str = Field(max_length=200)
    scene: str = Field(max_length=1000)
    notes: str = Field(default='', max_length=5000)
    setup: dict | None = None


class Book(BaseModel):
    picks: list[Pick] = Field(min_length=1, max_length=24)


def render_book(book):
    cards = []
    for pick in book.picks:
        shot = get_shot(pick.shot_id)
        path = (ROOT / shot.image_path.lstrip('/')).resolve()
        root = ROOT / ('mocks/img' if get_active_index().is_mock else 'cache/views')
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('View unavailable')
        mime = 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'
        image = base64.b64encode(path.read_bytes()).decode('ascii')
        setup = pick.setup or {}
        # A strict allowlist prevents unexpected data (including keys) entering the export.
        facts = {key: setup[key] for key in ('focal_mm', 'sensor_width_mm', 'frame_width_m',
            'horizontal_fov_deg', 'camera_distance_m', 'heading_deg', 'forward_m', 'backward_m')
            if isinstance(setup.get(key), (int, float))}
        cards.append(f'<article><h2>{html.escape(pick.scene)}</h2><img alt="Selected interior view" '
            f'src="data:{mime};base64,{image}"><p>{html.escape(pick.notes)}</p><p>'
            f'Property {html.escape(shot.property_id)} · Model {html.escape(shot.model_id)} · '
            f'Scan {html.escape(shot.sweep_id)}</p><p>Area {shot.room_area_m2} m² · '
            f'Ceiling {shot.ceiling_m} m (provider estimates)</p><pre>{html.escape(json.dumps(facts, indent=2))}'
            '</pre><p>Manual floor-plan heading. Physical fit and image-heading alignment unverified.</p></article>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Typecast scene lookbook</title>'
        '<style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;'
        'background:#111719;color:#eaf0ed}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}'
        'article{border:1px solid #567;padding:18px;break-inside:avoid}img{width:100%}'
        'p{white-space:pre-wrap;font-size:13px}pre{white-space:pre-wrap;font-size:12px}'
        '@media print{body{background:white;color:black}main{display:block}article{margin:20px 0}}</style>'
        '<h1>Typecast / Scene lookbook</h1><p>Created '+datetime.now(timezone.utc).isoformat()+
        '. '+('MOCK fixture' if get_active_index().is_mock else 'LIVE indexed')+
        ' views. Estimates require verification of walls, access, obstructions and rigging on site.</p><main>'
        + ''.join(cards) + '</main></html>')


@router.post('/api/lookbooks')
def create_book(book: Book):
    try:
        content = render_book(book)
    except Exception:
        raise HTTPException(400, 'A selected view is unavailable') from None
    identity = uuid.uuid4().hex
    target = ROOT / 'cache/lookbooks' / (identity+'.html')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
    return {'url': '/lookbooks/'+identity, 'views': len(book.picks)}


@router.get('/lookbooks/{identity}')
def get_book(identity: str):
    if len(identity) != 32 or any(c not in '0123456789abcdef' for c in identity):
        raise HTTPException(404, 'Lookbook not found')
    path = ROOT / 'cache/lookbooks' / (identity+'.html')
    if not path.is_file():
        raise HTTPException(404, 'Lookbook not found')
    return FileResponse(path, media_type='text/html', filename='typecast-lookbook.html',
                        headers={'Cache-Control': 'private, no-store'})
