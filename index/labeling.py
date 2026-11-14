"""Local pooled relevance labeling. No accuracy claim exists before review."""
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from index.search import ROOT, get_active_index, search_shots
from index.matterport import atomic_write_json

router = APIRouter()
_lock = threading.Lock()


def scenes():
    return json.loads(Path(__file__).with_name('evaluation-scenes.json').read_text())


def labels_path():
    return ROOT / 'cache/evaluation/interior-labels.json'


def read_labels():
    path = labels_path()
    return json.loads(path.read_text()) if path.exists() else {}


class Label(BaseModel):
    scene_id: str
    reviewer: str = Field(min_length=1, max_length=100)
    reviewer_kind: str = Field(pattern='^(human|ai)$')
    relevant_shot_ids: list[str] = Field(max_length=40)
    reviewed_shot_ids: list[str] = Field(min_length=1, max_length=40)


@router.get('/api/evaluation/scenes')
def list_scenes():
    labels = read_labels()
    return {'scenes': [{**s, 'reviewed': s['id'] in labels} for s in scenes()],
            'note': '15 held-out scenes and 5 tuning scenes. Labels are empty until reviewed.'}


@router.get('/api/evaluation/pool/{scene_id}')
def pool(scene_id: str):
    case = next((s for s in scenes() if s['id'] == scene_id), None)
    if not case:
        raise HTTPException(404, 'Unknown evaluation scene')
    try:
        candidates = search_shots(query_text=case['scene'], k=40)
    except Exception:
        raise HTTPException(503, 'Evaluation index unavailable') from None
    ids = [s.shot_id for s in candidates]
    ids.sort(key=lambda sid: hashlib.sha256((scene_id+sid).encode()).hexdigest())
    return {**case, 'mode': 'mock' if get_active_index().is_mock else 'live', 'shot_ids': ids,
            'note': 'Candidate order is blinded. Labels cover this retrieval pool, not the whole catalog.'}


@router.post('/api/evaluation/labels')
def save_labels(label: Label):
    case = pool(label.scene_id)
    reviewed, relevant = set(label.reviewed_shot_ids), set(label.relevant_shot_ids)
    if reviewed != set(case['shot_ids']) or not relevant <= reviewed:
        raise HTTPException(400, 'Review the complete current pool; relevant IDs must belong to it')
    with _lock:
        labels = read_labels()
        labels[label.scene_id] = {**label.model_dump(), 'scene': case['scene'],
            'split': case['split'], 'mode': case['mode'],
            'labelled_at': datetime.now(timezone.utc).isoformat()}
        atomic_write_json(labels_path(), labels)
    return {'saved': True, 'reviewed': len(reviewed), 'relevant': len(relevant)}


@router.get('/api/evaluation/report')
def report():
    labels = read_labels()
    return {'labelled_scenes': len(labels), 'human_labelled': sum(
        x['reviewer_kind'] == 'human' for x in labels.values()),
        'labels': list(labels.values()),
        'note': 'Pooled relevance only. Do not report mock or AI labels as human-held-out accuracy.'}


@router.get('/api/evaluation/metrics')
def metrics():
    """Keep test/tune, mock/live, human/AI results separate; empty gold is explicit."""
    from index.cinematic import diverse_results
    groups = {}
    index = get_active_index()
    mode = 'mock' if index.is_mock else 'live'
    for case in read_labels().values():
        if case['mode'] != mode:
            continue
        key = '/'.join((case['reviewer_kind'], mode, case['split']))
        group = groups.setdefault(key, {'labelled': 0, 'no_relevant_in_pool': 0,
            'cosine_recalls': [], 'diverse_recalls': []})
        group['labelled'] += 1
        gold = set(case['relevant_shot_ids'])
        if not gold:
            group['no_relevant_in_pool'] += 1
            continue
        candidates = search_shots(query_text=case['scene'], k=120)
        vectors = None if index.embeddings is None else {
            s.shot_id: index.embeddings[index._id_to_idx[s.shot_id]] for s in candidates}
        diverse = diverse_results(candidates, vectors, k=10)
        group['cosine_recalls'].append(len(gold & {s.shot_id for s in candidates[:10]})/len(gold))
        group['diverse_recalls'].append(len(gold & {s.shot_id for s in diverse})/len(gold))
    for group in groups.values():
        for ranking in ('cosine', 'diverse'):
            values = group.pop(ranking+'_recalls')
            group[ranking+'_pooled_recall_at_10'] = sum(values)/len(values) if values else None
    return {'groups': groups, 'scope': 'Judged top-40 cosine pool; not exhaustive catalog recall.',
            'note': 'Test labels must be frozen before tuning. AI and mock scores are separate.'}
