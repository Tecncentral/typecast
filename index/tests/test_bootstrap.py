"""Offline unit tests for index/bootstrap.py catalog selection pure function."""
from __future__ import annotations

import pytest

from index.bootstrap import BootstrapError, select_catalog_models


def test_select_catalog_models_filters_city_panos_dedupes_property_and_sorts_sid() -> None:
    csv_text = "\n".join(
        [
            "sid,city,costar_property_id,pano_count",
            "m_z_03,Los Angeles,prop_a,12",
            "m_a_01,los angeles,prop_a,10",
            "m_b_02,Los Angeles,prop_b,8",
            "m_low_04,Los Angeles,prop_c,7",
            "m_nyc_05,New York,prop_d,20",
            "m_c_06,Los Angeles,prop_e,15",
        ]
    )

    selected = select_catalog_models(csv_text, city="Los Angeles", max_models=2)
    assert selected == [
        {"model_id": "m_a_01", "property_id": "prop_a"},
        {"model_id": "m_b_02", "property_id": "prop_b"},
    ]


def test_select_catalog_models_rejects_bad_headers_and_empty_matches() -> None:
    bad_header_csv = "model_id,city,property_id,panos\nm1,Los Angeles,p1,10\n"
    with pytest.raises(BootstrapError, match="Invalid CSV headers"):
        select_catalog_models(bad_header_csv)

    no_match_csv = "sid,city,costar_property_id,pano_count\nm1,Los Angeles,p1,4\n"
    with pytest.raises(BootstrapError, match="No eligible models"):
        select_catalog_models(no_match_csv)


def test_official_catalog_extra_columns_and_missing_counts_are_supported():
    data = 'sid,name,city,costar_property_id,pano_count\nm0,unknown,Los Angeles,p0,\nm1,room,Los Angeles,p1,8\n'
    assert select_catalog_models(data) == [{'model_id': 'm1', 'property_id': 'p1'}]


def test_explicit_large_bootstrap_preserves_room_evidence_on_fetch_failure(tmp_path, monkeypatch):
    import json
    from argparse import Namespace
    from types import SimpleNamespace
    from index import bootstrap, build
    cache = tmp_path / 'cache/matterport'
    cache.mkdir(parents=True)
    monkeypatch.setattr(bootstrap, 'ROOT', tmp_path)
    monkeypatch.setattr(build, 'ROOT', tmp_path)
    monkeypatch.setattr(bootstrap, 'CACHE_DIR', cache)
    monkeypatch.setattr(bootstrap, 'load_matterport_credentials', lambda _: ('synthetic', 'synthetic'))
    models = cache / 'models.json'
    models.write_text(json.dumps([{'model_id': 'm1', 'property_id': 'p1'}]))
    old = dict(shot_id='m1__s1__f1', property_id='p1', model_id='m1', sweep_id='s1',
               heading_deg=0., room_id='room1', ceiling_m=3., provenance={'floor_id': 'floor1'})
    (cache / 'source_manifest.json').write_text(json.dumps({'records': [old]}))
    refreshed = {**old, 'room_id': None, 'ceiling_m': None,
                 'provenance': {'ingest_status': 'resumed_local'}}
    monkeypatch.setattr(bootstrap, 'ingest_matterport', lambda **_: (
        {'records': [refreshed]}, SimpleNamespace(models_succeeded=1, shots_written=0, shots_resumed=1)))
    def fail_rooms(*args, **kwargs):
        raise RuntimeError('controlled failure')
    monkeypatch.setattr(bootstrap, 'fetch_model_record', fail_rooms)
    monkeypatch.setattr(bootstrap, 'prepare', lambda _: [SimpleNamespace()])
    result = bootstrap.run_bootstrap(Namespace(max_models=40, max_sweeps=8,
        models='cache/matterport/models.json', prepare_only=True))
    saved = json.loads((cache / 'source_manifest.json').read_text())
    assert saved['records'] == [old]
    assert result['room_failures'] == 1
