import numpy as np
from fastapi.testclient import TestClient
from contracts.schemas import Shot
from index import preview
from index.search import ShotRetrievalIndex, configure_index


def test_preview_serves_only_indexed_view_images(tmp_path, monkeypatch):
    monkeypatch.setattr(preview, 'ROOT', tmp_path)
    directory = tmp_path / 'cache/views'
    directory.mkdir(parents=True)
    (directory / 'view.jpg').write_bytes(b'fixture-image-bytes')
    (tmp_path / '.env').write_text('PRIVATE=do-not-serve')
    def shot(identity, path):
        return Shot(shot_id=identity, property_id='p', model_id='m', sweep_id='s',
                    heading_deg=0, image_path=path)
    index = ShotRetrievalIndex([shot('view', '/cache/views/view.jpg'), shot('bad', '.env')],
        np.array([[1, 0], [0, 1]], dtype=np.float32),
        text_encoder=lambda _: np.array([1, 0], dtype=np.float32))
    configure_index(index)
    try:
        client = TestClient(preview.app)
        assert client.get('/image/view').content == b'fixture-image-bytes'
        assert client.get('/image/bad').status_code == 404
        assert client.get('/image/missing').status_code == 404
        result = client.get('/api/search', params={'q': 'room'}).json()
        assert result['mode'] == 'live' and result['indexed_views'] == 2
        assert 'PRIVATE' not in str(result)
        assert client.get('/api/search', params={'example': 'view'}).status_code == 200
    finally:
        configure_index()


def test_fixture_preview_images_and_encoder_failure_are_honest(monkeypatch):
    import index.search as search
    configure_index(search.ShotRetrievalIndex.from_mocks())
    try:
        client = TestClient(preview.app)
        response = client.get('/api/search', params={'q': 'room'})
        data = response.json()
        assert data['mode'] == 'mock'
        assert client.get('/image/' + data['shots'][0]['shot_id']).status_code == 200
        def fail(**kwargs):
            raise RuntimeError('provider-private-detail')
        monkeypatch.setattr(preview, 'search_shots', fail)
        response = client.get('/api/search', params={'q': 'room'})
        assert response.status_code == 503 and 'provider-private-detail' not in response.text
    finally:
        configure_index()
