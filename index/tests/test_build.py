import json
import numpy as np
import pytest
from PIL import Image
from index import build, store
from index.search import ShotRetrievalIndex, IndexUnavailableError


def test_private_import_index_and_query_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(build, 'ROOT', tmp_path)
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    cache = tmp_path / 'cache'
    cache.mkdir()
    Image.new('RGB', (32, 32), 'red').save(cache / 'sample.jpg')
    records = [dict(property_id='p1', model_id='m1', sweep_id='s1',
                    image_path='cache/sample.jpg', format='perspective', heading_deg=90)]
    (cache / 'input.json').write_text(json.dumps({'records': records}))
    shots = build.prepare('cache/input.json')
    assert len(shots) == 1
    assert shots[0].depth_m is None
    assert shots[0].measure_on_site
    assert shots[0].image_path.startswith('/cache/views/')
    store.save_index(shots, np.array([[3., 4.]], dtype=np.float32))
    idx = ShotRetrievalIndex.from_cache_dir(cache / 'shot-index',
        text_encoder=lambda _: np.array([3., 4.], dtype=np.float32))
    assert idx.search_shots(query_text='room')[0].score == pytest.approx(1)
    assert idx.check_shot(shots[0].shot_id).status == 'unknown'
    (cache / 'shot-index' / 'CURRENT').write_text('../escape')
    with pytest.raises(IndexUnavailableError, match='generation'):
        ShotRetrievalIndex.from_cache_dir(cache / 'shot-index')


def test_export_cannot_escape_private_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(build, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='cache'):
        build.cache_path('../outside.jpg')
