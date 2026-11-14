from fastapi.testclient import TestClient
from contracts.schemas import Shot
from index import lookbook, preview
from index.search import ShotRetrievalIndex, configure_index


def test_export_embeds_only_indexed_images_escapes_notes_and_omits_arbitrary_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(lookbook, 'ROOT', tmp_path)
    image = tmp_path / 'cache/views/a.jpg'
    image.parent.mkdir(parents=True)
    image.write_bytes(b'indexed-jpeg-fixture')
    shot = Shot(shot_id='a', model_id='m', property_id='p', sweep_id='s',
                heading_deg=0, image_path='/cache/views/a.jpg')
    import numpy as np
    configure_index(ShotRetrievalIndex([shot], np.array([[1,0]], dtype=np.float32)))
    try:
        client = TestClient(preview.app)
        body = {'picks': [{'shot_id':'a','scene':'<script>bad</script>',
            'notes':'<img src=x onerror=bad()>', 'setup':{'api_key':'do-not-export','focal_mm':24}}]}
        result = client.post('/api/lookbooks', json=body)
        assert result.status_code == 200
        book = client.get(result.json()['url'])
        assert book.status_code == 200 and 'attachment' in book.headers['content-disposition']
        assert 'data:image/jpeg;base64,' in book.text and '&lt;script&gt;' in book.text
        assert '<script>' not in book.text and 'do-not-export' not in book.text
        body['picks'][0]['shot_id'] = 'missing'
        assert client.post('/api/lookbooks', json=body).status_code == 400
        assert client.get('/lookbooks/invalid').status_code == 404
    finally:
        configure_index()
