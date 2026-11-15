import base64
import io
from types import SimpleNamespace
import pytest
from PIL import Image
from fastapi import HTTPException
from index import scene_customization as custom
from index.production import SceneCustomizationRequest
from pydantic import ValidationError


def test_image_upload_requires_explicit_consent():
    with pytest.raises(ValidationError):
        SceneCustomizationRequest(shot_id='shot1',instruction='Add a desk',confirm_image_upload=False)


def test_disabled_upload_and_mock_frames_are_never_sent(monkeypatch):
    monkeypatch.setenv('TYPECAST_ALLOW_VISION_UPLOAD','0')
    with pytest.raises(HTTPException) as err: custom.render_scene('s','desk')
    assert err.value.status_code==503
    monkeypatch.setenv('TYPECAST_ALLOW_VISION_UPLOAD','1')
    monkeypatch.setattr(custom,'get_active_index',lambda:SimpleNamespace(is_mock=True))
    with pytest.raises(HTTPException) as err: custom.render_scene('s','desk')
    assert err.value.status_code==409


def test_image_edit_is_separate_stamped_and_source_unchanged(tmp_path,monkeypatch):
    from strike import core
    monkeypatch.setenv('TYPECAST_ALLOW_VISION_UPLOAD','1')
    monkeypatch.setattr(custom,'ROOT',tmp_path)
    source=tmp_path/'cache/views/source.png'; source.parent.mkdir(parents=True)
    Image.new('RGB',(1024,768),'blue').save(source)
    before=source.read_bytes()
    monkeypatch.setattr(custom,'get_active_index',lambda:SimpleNamespace(is_mock=False))
    monkeypatch.setattr(custom,'get_shot',lambda _:SimpleNamespace(image_path='cache/views/source.png'))
    buffer=io.BytesIO(); Image.new('RGB',(1024,1024),'red').save(buffer,'PNG')
    calls=[]
    class FakeClient:
        def _post(self,path,**kw):
            calls.append((path,kw))
            return {'data':[{'b64_json':base64.b64encode(buffer.getvalue()).decode()}]}
    monkeypatch.setattr(core,'OpenAIClient',FakeClient)
    response=custom.render_scene('s','Add a desk and two characters with red lights')
    token=response['image_url'].split('/')[-1][:-4]
    saved=custom.image_path(token)
    assert source.read_bytes()==before
    assert response['geometry_verified'] is False
    with Image.open(saved) as image:
        assert image.getpixel((0,0))==(16,18,18)
        assert image.getpixel((0,50))==(255,0,0)
    assert 'Add a desk' in calls[0][1]['data']['prompt']
    assert calls[0][0]=='/images/edits'


def test_preview_path_rejects_traversal():
    with pytest.raises(HTTPException): custom.image_path('../private')


def test_unreadable_indexed_frame_is_a_404(tmp_path, monkeypatch):
    from strike import core
    monkeypatch.setenv('TYPECAST_ALLOW_VISION_UPLOAD', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-not-real')
    monkeypatch.setattr(custom, 'ROOT', tmp_path)
    source = tmp_path / 'cache/views/bad.png'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'not an image')
    before = source.read_bytes()
    monkeypatch.setattr(custom, 'get_active_index', lambda: SimpleNamespace(is_mock=False))
    monkeypatch.setattr(custom, 'get_shot', lambda _: SimpleNamespace(image_path='cache/views/bad.png'))
    posts = []

    class Client:
        def __init__(self):
            pass

        def _post(self, *args, **kwargs):
            posts.append(args)
            raise AssertionError('unreadable frame was uploaded')

    monkeypatch.setattr(core, 'OpenAIClient', Client)
    with pytest.raises(HTTPException) as err:
        custom.render_scene('s', 'Add a desk')
    assert err.value.status_code == 404
    assert posts == []
    assert source.read_bytes() == before
    assert not (tmp_path / 'cache/customizations').exists()


def test_gemini_provider_setting_routes_the_edit_to_gemini(tmp_path, monkeypatch):
    from agent import image_edit
    from strike import core
    monkeypatch.setenv('TYPECAST_ALLOW_VISION_UPLOAD', '1')
    monkeypatch.setenv('TYPECAST_IMAGE_PROVIDER', 'gemini')
    monkeypatch.setattr(custom, 'ROOT', tmp_path)
    source = tmp_path / 'cache/views/source.png'; source.parent.mkdir(parents=True)
    Image.new('RGB', (1024, 768), 'blue').save(source)
    monkeypatch.setattr(custom, 'get_active_index', lambda: SimpleNamespace(is_mock=False))
    monkeypatch.setattr(custom, 'get_shot', lambda _: SimpleNamespace(image_path='cache/views/source.png'))
    monkeypatch.setattr(core, 'OpenAIClient', lambda: pytest.fail('OpenAI must not be called when Gemini is selected'))
    buffer = io.BytesIO(); Image.new('RGB', (1024, 1024), 'green').save(buffer, 'PNG')
    calls = []
    monkeypatch.setattr(image_edit, '_gemini', lambda png, prompt, size, model: calls.append((prompt, size)) or buffer.getvalue())
    response = custom.render_scene('s', 'Add a desk')
    assert calls and 'Add a desk' in calls[0][0] and calls[0][1] == '1024x1024'
    with Image.open(custom.image_path(response['image_url'].split('/')[-1][:-4])) as image:
        assert image.getpixel((0, 50)) == (0, 128, 0)
    monkeypatch.setattr(image_edit, '_gemini', lambda *a: (_ for _ in ()).throw(image_edit.ImageEditError('Gemini HTTP 500')))
    with pytest.raises(HTTPException) as err:
        custom.render_scene('s', 'Add a desk')
    assert err.value.status_code == 502
