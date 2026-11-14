import json, os, pathlib
import pytest
from contracts.schemas import Shot, Property, Logistics
from data.costar_tools import search_costar
from data.vexcel_tools import plan_logistics, spaces_from_area

M = pathlib.Path(__file__).resolve().parents[2] / "mocks"
MOCK_MODE = os.getenv("TYPECAST_USE_MOCKS", "1") == "1"


def test_mocks_match_contracts():
    for name, cls in (("shot", Shot), ("property", Property), ("logistics", Logistics)):
        rows = json.loads((M / f"{name}.json").read_text())
        assert rows and all(cls(**r) for r in rows)


def test_filters():
    if not MOCK_MODE:
        try:
            search_costar(available_only=False, limit=1)
        except RuntimeError as exc:
            pytest.skip(f"live mode needs a valid private cache/join.parquet: {exc}")
    assert all(p.available for p in search_costar())
    assert len(search_costar(available_only=False)) > len(search_costar())
    assert all(p.year_built <= 1992 for p in search_costar(year_max=1992))
    assert search_costar(city="Nowhere") == []


def test_logistics():
    assert spaces_from_area(900) == 30
    if not MOCK_MODE:
        pytest.skip("mock-p1 exists only in mocks/logistics.json; live mode has no fixtures")
    assert plan_logistics("mock-p1").truck_spaces == 4
