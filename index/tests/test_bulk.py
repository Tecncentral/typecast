import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from index import build, bulk, store


def test_selection_keeps_exact_csv_pair_even_when_catalog_disagrees():
    rows = [dict(property_id='p1', model_id='m1', city='Houston', type='Office',
                 available=True, availability_status='available', lat=1., lon=2.)]
    catalog = [dict(sid='m1', costar_property_id='different', pano_count='3')]
    selected = bulk.select_models(rows, catalog)
    assert len(selected) == 1
    assert selected[0]['property_id'] == 'p1'
    assert selected[0]['catalog_disagreement'] is True
    assert selected[0]['pano_count'] == 3


def test_selection_uses_alternate_after_recorded_model_failure():
    row = dict(property_id='p1', city='Houston', type='Multifamily', available=True,
               availability_status='available', lat=1., lon=2., year_built=1980, size_sqft=1000.)
    rows = [{**row, 'model_id': m} for m in ('m1', 'm2')]
    catalog = [dict(sid=m, costar_property_id='p1', pano_count=str(panos))
               for m, panos in [('m1', 24), ('m2', 8)]]
    selected = bulk.select_models(rows, catalog, multifamily_count=1, unavailable_models={'m1'})
    assert [r['model_id'] for r in selected] == ['m2']
    retried = bulk.select_models(rows, catalog, multifamily_count=1, unavailable_models=set())
    assert [r['model_id'] for r in retried] == ['m1']


def test_catalog_exclusions_distinguish_missing_panos_from_recorded_failures():
    assert bulk.catalog_exclusion_reason([None], set()) == 'catalog_missing'
    assert bulk.catalog_exclusion_reason([{'sid': 'm', 'pano_count': '0'}], set()) == 'catalog_has_no_panoramas'
    assert bulk.catalog_exclusion_reason([{'sid': 'm', 'pano_count': '8'}], {'m'}) == 'recorded_model_failures'


def test_incremental_encoding_reuses_shared_source_and_existing_vectors(tmp_path, monkeypatch):
    monkeypatch.setattr(build, 'ROOT', tmp_path)
    cache = tmp_path / 'cache'
    cache.mkdir()
    Image.new('RGB', (10, 10), 'red').save(cache / 'new.jpg')
    old = SimpleNamespace(shot_id='p1-m1-s1-0.000-digest', model_id='m1',
                          sweep_id='s1', heading_deg=0., image_path='/cache/missing.jpg')
    shared = SimpleNamespace(shot_id='p2-m1-s1-0.000-digest', model_id='m1',
                             sweep_id='s1', heading_deg=0., image_path='/cache/missing.jpg')
    new = SimpleNamespace(shot_id='p3-m2-s2-0.000-newdigest', model_id='m2',
                          sweep_id='s2', heading_deg=0., image_path='/cache/new.jpg')
    twin = SimpleNamespace(**{**vars(new), 'shot_id': 'p4-m2-s2-0.000-newdigest'})
    calls = []
    class Encoder:
        def encode(self, images, **kwargs):
            calls.append(len(images))
            return np.array([[0., 1.]], dtype=np.float32)
    monkeypatch.setattr(build, 'encoder', lambda _: Encoder())
    old_vector = np.array([[1., 0.]], dtype=np.float32)
    vectors = build.encode_incremental([shared, new, twin], previous_shots=[old], previous_vectors=old_vector)
    np.testing.assert_array_equal(vectors, [[1., 0.], [0., 1.], [0., 1.]])
    assert calls == [1]


def test_prepare_can_preserve_existing_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(build, 'ROOT', tmp_path)
    cache = tmp_path / 'cache'
    cache.mkdir()
    Image.new('RGB', (10, 10), 'blue').save(cache / 'new.jpg')
    (cache / 'view-provenance.json').write_text(json.dumps({'old': {'room_id': 'oldroom'}}))
    source = cache / 'new.json'
    source.write_text(json.dumps({'records': [dict(property_id='p', model_id='m',
        sweep_id='s', image_path='cache/new.jpg', format='perspective', heading_deg=0)]}))
    shots = build.prepare(source, preserve_provenance=True)
    provenance = json.loads((cache / 'view-provenance.json').read_text())
    assert provenance['old'] == {'room_id': 'oldroom'}
    assert shots[0].shot_id in provenance


def test_merge_shared_model_fans_out_property_ids_without_changing_old_records(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, 'ROOT', tmp_path)
    monkeypatch.setattr(bulk, 'CACHE', tmp_path / 'cache/matterport')
    directory = bulk.CACHE / 'bulk/m1'
    directory.mkdir(parents=True)
    row = dict(shot_id='m1__s1__f1', model_id='m1', property_id='p1',
               sweep_id='s1', image_path='images/m1/s1.jpg', provenance={})
    (directory / 'source_manifest.json').write_text(json.dumps({'records': [row]}))
    old = {'shot_id': 'old', 'property_id': 'oldp', 'model_id': 'oldm', 'ceiling_m': 3.}
    selection = [dict(property_id=p, model_id='m1', catalog_disagreement=False) for p in ('p1', 'p2')]
    records, added, _ = bulk.merge_records({'records': [old]}, selection, {'m1'})
    assert records[0] == old
    assert {r['property_id'] for r in added} == {'p1', 'p2'}
    assert len({r['shot_id'] for r in records}) == 3
    assert len({r['image_path'] for r in added}) == 1


def test_index_can_preserve_existing_normalized_vector_bits(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    shot = SimpleNamespace(shot_id='s', model_dump=lambda: {'shot_id': 's'})
    vector = np.array([[.6, .8]], dtype=np.float32)
    store.save_index([shot], vector, already_normalized=True)
    directory = store.index_dir()
    generation = (directory / 'CURRENT').read_text()
    saved = np.load(directory / generation / 'embeddings.npy')
    np.testing.assert_array_equal(saved, vector)


def test_store_loads_pinned_generation_without_current_pointer(tmp_path, monkeypatch):
    from contracts.schemas import Shot
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    shot = Shot(shot_id='s', property_id='p', model_id='m', sweep_id='scan',
                heading_deg=0., image_path='/cache/views/s.jpg')
    store.save_index([shot], np.array([[1., 0.]], dtype=np.float32))
    directory = store.index_dir()
    generation = directory / (directory / 'CURRENT').read_text()
    monkeypatch.setenv('TYPECAST_INDEX_DIR', str(generation))
    shots, vectors, model = store.load_index()
    assert [s.shot_id for s in shots] == ['s']
    np.testing.assert_array_equal(vectors, [[1., 0.]])
    assert model == store.DEFAULT_MODEL


def test_partial_model_is_retried_instead_of_marked_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, 'CACHE', tmp_path / 'cache/matterport')
    calls = []
    def fake_ingest(**kwargs):
        directory = kwargs['output_dir']
        Image.new('RGB', (10, 10), 'red').save(directory / 'image.jpg')
        calls.append(1)
        return {'records': [{'image_path': 'image.jpg'}]}, SimpleNamespace(
            shots_failed=1 if len(calls) == 1 else 0, sweeps_skipped=0,
            shots_written=1, shots_resumed=0)
    def fail_rooms(*args, **kwargs):
        raise RuntimeError('controlled missing room evidence')
    monkeypatch.setattr(bulk, 'ingest_matterport', fake_ingest)
    monkeypatch.setattr(bulk, 'fetch_model_record', fail_rooms)
    kwargs = dict(auth=('synthetic', 'synthetic'), max_sweeps=8, timeout=1)
    first = bulk.ingest_one('m1', 'p1', **kwargs)
    directory = bulk.CACHE / 'bulk/m1'
    assert first['usable'] and not first['ok']
    assert not (directory / 'completed.json').exists()
    assert (directory / 'partial.json').exists()
    assert bulk.ingest_one('m1', 'p1', **kwargs)['ok']
    assert bulk.ingest_one('m1', 'p1', **kwargs)['resumed']
    assert len(calls) == 2


def test_old_index_model_without_bulk_checkpoint_does_not_imply_new_pair_success(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, 'ROOT', tmp_path)
    monkeypatch.setattr(bulk, 'CACHE', tmp_path / 'cache/matterport')
    bulk.CACHE.mkdir(parents=True)
    previous = {'records': [dict(property_id='oldp', model_id='oldm')]}
    selected = [dict(property_id='newp', model_id='oldm', catalog_disagreement=False)]
    records, added, _ = bulk.merge_records(previous, selected, set())
    assert records == previous['records']
    assert added == []


def test_published_partial_pair_is_scheduled_again(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, 'CACHE', tmp_path / 'cache/matterport')
    directory = bulk.CACHE / 'bulk/m1'
    directory.mkdir(parents=True)
    (directory / 'partial.json').write_text(json.dumps({'shots_failed': 1}))
    selection = [dict(property_id='p1', model_id='m1', pano_count=8)]
    indexed = [SimpleNamespace(property_id='p1', model_id='m1')]
    # Even a pair with eight sweeps must retry a recorded failed face.
    source = [dict(property_id='p1', model_id='m1', sweep_id=f's{s}', heading_deg=h)
              for s in range(8) for h in (0, 90, 180, 270)]
    assert bulk.model_tasks(selection, indexed, source, 8) == {'m1': 'p1'}


def test_source_published_before_index_is_prepared_on_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, 'CACHE', tmp_path / 'cache/matterport')
    bulk.CACHE.mkdir(parents=True)
    row = dict(property_id='p1', model_id='m1', sweep_id='s1', heading_deg=0.)
    records, added, _ = bulk.merge_records({'records': [row]},
        [dict(property_id='p1', model_id='m1')], set(), indexed_shots=[])
    assert records == [row]
    assert added == [row]


def test_partial_fanout_adds_only_missing_views(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, 'ROOT', tmp_path)
    monkeypatch.setattr(build, 'ROOT', tmp_path)
    monkeypatch.setattr(bulk, 'CACHE', tmp_path / 'cache/matterport')
    directory = bulk.CACHE / 'bulk/m1'
    directory.mkdir(parents=True)
    Image.new('RGB', (10, 10), 'red').save(tmp_path / 'cache/old.jpg')
    old = dict(shot_id='old', property_id='p1', model_id='m1', sweep_id='s1',
               heading_deg=0., image_path='old.jpg', provenance={'old': 'kept'})
    new = {**old, 'shot_id': 'new', 'heading_deg': 90.}
    (directory / 'source_manifest.json').write_text(json.dumps({'records': [old, new]}))
    indexed = [SimpleNamespace(property_id='p1', model_id='m1', sweep_id='s1',
                               heading_deg=0., image_path='/cache/old.jpg')]
    records, added, _ = bulk.merge_records({'records': [old]},
        [dict(property_id='p1', model_id='m1', catalog_disagreement=False)], {'m1'}, indexed)
    assert len(records) == 2
    assert records[0] == old
    assert len(added) == 1 and added[0]['heading_deg'] == 90.


def test_larger_requested_scan_count_schedules_growth(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk, 'CACHE', tmp_path / 'cache/matterport')
    directory = bulk.CACHE / 'bulk/m1'
    directory.mkdir(parents=True)
    (directory / 'completed.json').write_text(json.dumps({'max_sweeps': 8, 'records': 32}))
    source = [dict(property_id='p1', model_id='m1', sweep_id=f's{s}', heading_deg=h)
              for s in range(8) for h in (0, 90, 180, 270)]
    indexed = [SimpleNamespace(property_id='p1', model_id='m1')]
    selected = [dict(property_id='p1', model_id='m1', pano_count=12)]
    assert bulk.model_tasks(selected, indexed, source, 12) == {'m1': 'p1'}


def test_deadline_prevents_new_requests_and_clips_timeout(monkeypatch):
    calls = []
    class Client:
        def get(self, url, **kwargs):
            calls.append(kwargs)
            return 'ok'
    monkeypatch.setattr(bulk.time, 'monotonic', lambda: 10.)
    with pytest.raises(bulk.MatterportIngestionError, match='deadline'):
        bulk._DeadlineClient(Client(), 9.).get('https://example.test', timeout=15)
    assert calls == []
    assert bulk._DeadlineClient(Client(), 12.).get('https://example.test', timeout=15) == 'ok'
    assert calls[0]['timeout'] == 2.
