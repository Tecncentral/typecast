import pytest
from fastapi.testclient import TestClient
from index import labeling, preview
from index.search import ShotRetrievalIndex, configure_index


def test_labels_stay_empty_until_complete_attributed_review(tmp_path, monkeypatch):
    monkeypatch.setattr(labeling, 'ROOT', tmp_path)
    configure_index(ShotRetrievalIndex.from_mocks())
    try:
        client = TestClient(preview.app)
        scenes = client.get('/api/evaluation/scenes').json()['scenes']
        assert len(scenes) == 20 and sum(s['split'] == 'test' for s in scenes) == 15
        assert not any(s['reviewed'] for s in scenes)
        pool = client.get('/api/evaluation/pool/interior-01').json()
        assert pool['mode'] == 'mock' and 'score' not in pool
        label = dict(scene_id='interior-01', reviewer='Fixture reviewer', reviewer_kind='ai',
                     reviewed_shot_ids=pool['shot_ids'], relevant_shot_ids=[pool['shot_ids'][0]])
        assert client.post('/api/evaluation/labels', json=label).status_code == 200
        report = client.get('/api/evaluation/report').json()
        assert report['labelled_scenes'] == 1 and report['human_labelled'] == 0
        assert report['labels'][0]['mode'] == 'mock'
        label['relevant_shot_ids'] = ['invented']
        assert client.post('/api/evaluation/labels', json=label).status_code == 400
        label['reviewer_kind'] = 'verified-human'
        assert client.post('/api/evaluation/labels', json=label).status_code == 422
    finally:
        configure_index()
