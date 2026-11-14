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
